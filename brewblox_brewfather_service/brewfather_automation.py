"""
Integration of mash automation based on Brewfather recipes
In order to get started, load_recipe(self, recipe_id: str) should be called and then start_mash()
"""

import asyncio
import re
from datetime import datetime, timedelta

from aiohttp import web
from aiohttp_apispec import docs
from brewblox_service import brewblox_logger, features, mqtt, repeater
from brewblox_spark_api.blocks_api import BlocksApi
from brewblox_brewfather_service.api.brewfather_api_client import \
    BrewfatherClient
from brewblox_brewfather_service.datastore import DatastoreClient
from brewblox_brewfather_service.schemas import (AutomationState,
                                                 AutomationStage, CurrentState,
                                                 CurrentStateSchema, Device,
                                                 MashAutomation, MashStepSchema,
                                                 Settings, Timer)

LOGGER = brewblox_logger(__name__)

routes = web.RouteTableDef()


class BrewfatherFeature(repeater.RepeaterFeature):

    def __init__(self, app: web.Application):
        super().__init__(app)

    async def prepare(self):
        LOGGER.info(f'Starting {self}')

        # Get values from config
        LOGGER.info(self.app['config'])

        self.bfclient = features.get(self.app, BrewfatherClient)
        self.spark_client = features.get(self.app, BlocksApi)
        self.finished = False
        self.spark_connected = False

        config = self.app['config']
        service_id = config['mash_service_id']
        setpoint_device_id = config['mash_setpoint_device']
        setpoint_device = Device(service_id, setpoint_device_id)
        self.settings = Settings(MashAutomation(setpoint_device))
        self.datastore_client = DatastoreClient(self.app)
        self.timer_task = None

        asyncio.create_task(self.finish_init())
        self.spark_client.on_blocks_change(self.spark_blocks_changed)

        self.name = self.app['config']['name']
        self.topic = f'brewcast/state/{self.name}'

        await mqtt.listen(self.app, 'brewcast/state/#', self.on_message)
        await mqtt.subscribe(self.app, 'brewcast/state/#')

    async def finish_init(self):
        if not self.finished:
            await self.spark_client.is_ready.wait()
            LOGGER.info(f'Finishing {self} init')
            await self.datastore_client.store_settings(self.settings)
            await self.restore_timer()
            self.finished = True

    async def run(self):
        await asyncio.sleep(10)

        if not self.spark_client.is_ready.is_set():
            if self.spark_connected:
                LOGGER.warn('Spark is not reachable, waiting to reconnect')
                self.spark_connected = False
            return
        if not self.bfclient.brewtracker_data:
            return

        if not self.spark_connected:
            LOGGER.warn('Spark connection re-established, waiting to reconnect')
            self.spark_connected = True
            await self.restore_timer()

    async def before_shutdown(self, app: web.Application):
        if self.timer_task is not None:
            self.timer_task.cancel()
        return await super().before_shutdown(app)

    async def restore_timer(self):
        """ restores timer if need be. This can happen in several situations when we loose connection or power """
        state = await self.get_state()
        if state.automation_state == AutomationState.REST and self.timer_task is None:
            LOGGER.warn('missing a timer for rest state. Recreating one from currently known state.')

            if state.timer is None or state.timer.expected_end_time is None:
                raise ValueError('inconsistent state')

            if state.timer.expected_end_time < datetime.utcnow():
                LOGGER.warn('Timer was supposed to time out in the past. Proceeding to next step.')
                await self.proceed_to_next_step()
                return

            # we don't modify state and just restore timer
            self.__schedule_wake_up(state.timer.expected_end_time)
            log_msg = f'Restoring timer for REST step @({state.step.value}°C), '
            log_msg += f'expected end time: {state.timer.expected_end_time}'
            LOGGER.info(log_msg)

    async def get_state(self) -> CurrentStateSchema:
        state = await self.datastore_client.load_state()
        return state

    async def get_batches(self, status: str = None) -> dict:
        batches = await self.bfclient.batches(status)
        return batches

    async def load_batch(self, batch_id: str):
        """load a batch brewtracker from Brewfather, and get ready for automation"""
        LOGGER.info(f'Loading brewtracker for batch {batch_id}')
        batch = await self.bfclient.batch(batch_id)
        recipe_name = batch['recipe']['name']
        LOGGER.info(f'Recipe name {recipe_name}')

        brewtracker = await self.bfclient.brewtracker(batch_id)

        # sanity check
        if len(brewtracker['stages']) == 0:
            raise ValueError('Brewtracker contains no stage. At least one stage is expected.')
        for stage in brewtracker['stages']:
            if len(stage['steps']) == 0:
                raise ValueError(f'Stage {stage["name"]} contains empty steps array.')

        # Cancel any timer task before goin any further
        if self.timer_task is not None:
            self.timer_task.cancel()

        state = CurrentState(AutomationStage.MASH, batch_id, '', recipe_name, brewtracker)
        await self.datastore_client.store_state(state)

        await self.publish_state(state, 'Batch brewtracker loaded')
        return state

    async def publish_state(self, state: CurrentState, log_msg: str):
        schema = CurrentStateSchema()
        state_str = schema.dump(state)

        LOGGER.info(log_msg)
        await mqtt.publish(self.app,
                           self.topic,
                           {
                               'type': 'brewfather.state',
                               'key': self.name,
                               'data': {
                                   'status_msg': log_msg,
                                   'state': state_str
                               }
                           }, retain=True)

    async def start_automated_mash(self):
        """
        Starts automation from the previously loaded recipe.
        """
        state = await self.get_state()
        state.mash_start_time = datetime.utcnow()
        state.stage_index = 0
        await self.datastore_client.store_state(state)

        await self.publish_state(state, '== Starting mash ==')
        await self.proceed_to_next_step()

    async def proceed_to_next_step(self):
        """
        load recipe next temperature step
        and adjust mash temperature (heat) setpoint according to recipe next step
        """
        state = await self.get_state()
        LOGGER.debug(f'Proceeding to next step from current state: {state}')

        stage_index = state.stage_index
        state.step_index += 1
        stage = state.brewtracker['stages'][stage_index]

        if self.timer_task is not None:
            self.timer_task.cancel()

        try:
            schema = MashStepSchema()
            step = schema.load(stage['steps'][state.step_index])
            state.step = step

            if step.pauseBefore is not None:
                if not step.pauseBefore:
                    # pauseBefore explicitly set to false
                    # We shall not pause: auto-proceed to next step"""
                    await self.publish_state(state, f'Step: {step.name} complete, proceeding to next step.')
                    await self.datastore_client.store_state(state)
                    await self.proceed_to_next_step()
                else:
                    # pauseBefore explicitly set to True
                    # we must pause,
                    # it could be that we have to heat or wait for brewer to manually operate
                    description = step.description
                    matched = None
                    if step.tooltip is not None:
                        matched = re.match(r'^.* (\d*[.,]?\d*) °([C|F]).*$', step.tooltip)

                    if matched is not None:
                        # paused because we need to heat
                        state.automation_state = AutomationState.HEAT
                        target_temp = float(matched.group(1))
                        # here we are overriding value because of a small bug
                        # in Brewfather value field for strike temp
                        state.step.value = target_temp
                        await self.__adjust_mash_setpoint(target_temp)
                        log_msg = f'heating to {target_temp} °C'
                    else:
                        # paused waiting for user
                        state.automation_state = AutomationState.STANDBY
                        log_msg = f'mash automation paused: {description}'
                    await self.datastore_client.store_state(state)
                    await self.publish_state(state, log_msg)
                return
            else:
                if step.duration is not None:
                    duration = step.duration
                    # duration is not 0, we should start a timer
                    await self.datastore_client.store_state(state)
                    await self.__start_timer(duration)
                else:
                    log_msg = 'Brewfather step does not state if we should pause or not '
                    log_msg += f'and no duration is set to schedule a timer. Step: {step}'
                    LOGGER.error(log_msg)
                    raise ValueError(log_msg)
        except IndexError:
            LOGGER.warn('current recipe has no more mash steps')

    async def __adjust_mash_setpoint(self, target_temp):
        try:
            block = await asyncio.wait_for(self.spark_client.read(self.settings.mashAutomation.setpointDevice.id),
                                           timeout=5.0)
            previous_temp = block['data']['storedSetting']['value']
            block['data']['storedSetting']['value'] = target_temp
            returned_block = await asyncio.wait_for(
                self.spark_client.patch(self.settings.mashAutomation.setpointDevice.id, block['data']),
                timeout=5.0)
            new_temp = returned_block['data']['storedSetting']['value']
            LOGGER.info(f'mash setpoint changed from {previous_temp} to {new_temp}')
        except asyncio.TimeoutError as error:
            raise asyncio.TimeoutError('Failed to communicate with spark in a timely manner') from error

    async def __start_timer(self, duration: int):
        state = await self.get_state()
        state.automation_state = AutomationState.REST
        timer_start_time = datetime.utcnow()
        timer_expected_end_time = timer_start_time + timedelta(seconds=duration)
        timer = Timer(timer_start_time, duration, timer_expected_end_time)
        state.timer = timer

        self.__schedule_wake_up(timer_expected_end_time)
        await self.datastore_client.store_state(state)

        log_msg = f'Starting timer {state.timer.duration} seconds ({state.step.value}°C), '
        log_msg += f'expected end time: {state.timer.expected_end_time}'
        await self.publish_state(state, log_msg)

    def __schedule_wake_up(self, end_time: datetime):
        loop = asyncio.get_event_loop()
        # cancel any previously scheduled event
        if self.timer_task is not None:
            self.timer_task.cancel()
        now = datetime.utcnow()
        if now > end_time:
            LOGGER.error('Attempting to schedule a timer in the past')
            raise ValueError('Attempting to schedule a timer in the past')
        delay = end_time - now

        self.timer_task = loop.call_later(delay.total_seconds(), asyncio.create_task, self.__end_timer())

    async def __end_timer(self):
        state = await self.get_state()
        log_msg = f'{state.timer.duration} seconds timer ({state.step.value}°C) is over, proceeding to next step'
        state.timer = None
        await self.datastore_client.store_state(state)
        await self.publish_state(state, log_msg)
        await self.proceed_to_next_step()

    async def on_message(self, topic: str, message: dict):
        """ nothing to do yet"""

    async def spark_blocks_changed(self, blocks):
        state = await self.get_state()
        if state.automation_state == AutomationState.HEAT:
            try:
                expected_temp = state.step.value
                setpoint_dev_id = self.settings.mashAutomation.setpointDevice.id
                temp_device_block = next((block for block in blocks if block['id'] == setpoint_dev_id))
                updated_temp = temp_device_block['data']['value']['value']
                LOGGER.info(f'--> updated_temp: {updated_temp}, expected: {expected_temp}')
                if updated_temp >= expected_temp:
                    await self.proceed_to_next_step()
            except IndexError:
                LOGGER.warn('attempting to reach mash step while it does not exist')


@docs(
    tags=['Brewfather'],
    summary='fetch recipes from Brewfather. You can paginate by using offset and limit query parameters.',
    description='Both parameters are optional. Offset defaults to 0 and limit to 10',
)
@routes.get('/recipes')
async def get_recipes(request: web.Request) -> web.json_response:
    LOGGER.debug('REST API: get recipes')
    params = request.rel_url.query

    try:
        offset = params['offset']
    except KeyError:
        offset = 0

    try:
        limit = params['limit']
    except KeyError:
        limit = 10

    recipes = await BrewfatherClient(request.app).recipes(offset, limit)
    recipes_name_list = [
        {'id': recipe['_id'], 'name': recipe['name']} for recipe in recipes
    ]

    return web.json_response(recipes_name_list)


@docs(
    tags=['Brewfather'],
    summary='fetch one recipe from Brewfather',
)
@routes.get('/recipe/{recipe_id}')
async def get_recipe(request: web.Request) -> web.json_response:
    LOGGER.debug('REST API: get recipe')
    recipe = await BrewfatherClient(request.app).recipe(request.match_info['recipe_id'])
    return web.json_response(recipe)


@docs(
    tags=['Brewfather'],
    summary='start mash automation',
)
@routes.get('/startmash')
async def start_mash_automation(request: web.Request) -> web.json_response:
    LOGGER.info('REST API: starting mash')
    feature = fget_brewfather(request.app)
    await feature.start_automated_mash()
    return web.json_response()


@docs(
    tags=['Brewfather'],
    summary='proceed to next step',
)
@routes.get('/proceed')
async def proceed_to_next_step(request: web.Request) -> web.json_response:
    LOGGER.info('REST API: proceeding to next step')
    feature = fget_brewfather(request.app)
    await feature.proceed_to_next_step()
    return web.json_response()


@docs(
    tags=['Brewfather'],
    summary='get automation state',
)
@routes.get('/state')
async def get_state(request: web.Request) -> web.json_response:
    LOGGER.debug('REST API: get state')
    feature = fget_brewfather(request.app)
    state = await feature.get_state()
    schema = CurrentStateSchema()
    state_str = schema.dump(state)
    return web.json_response(state_str)


@docs(
    tags=['Brewfather'],
    summary='load batches',
    parameters=[
        {
            'in': 'query',
            'name': 'status',
            'schema': {'type': 'string'},
            'description': 'batch status, can be Planning, Brewing or Fermenting. Defaults to Planning'
        }
    ]
)
@routes.get('/batches')
async def get_batches(request: web.Request) -> web.json_response:
    LOGGER.debug('REST API: getting batches')
    params = request.rel_url.query
    try:
        status = params['status']
    except KeyError:
        status = None

    feature = fget_brewfather(request.app)
    batches = await feature.get_batches(status)
    return web.json_response(batches)


@docs(
    tags=['Brewfather'],
    summary='load batch and get ready for automating the mash.',
    description='Once done if brewblox is master, you can call startmash endpoint'
)
@routes.get('/load/{batch_id}')
async def load_batch(request: web.Request) -> web.json_response:
    LOGGER.debug(f'REST API: loading batch {request.match_info["batch_id"]}')

    feature = fget_brewfather(request.app)
    state = await feature.load_batch(request.match_info['batch_id'])
    schema = CurrentStateSchema()
    state_str = schema.dump(state)
    return web.json_response(state_str)


def setup(app: web.Application):
    app.router.add_routes(routes)
    features.add(app, BlocksApi(app, 'spark-one'))
    features.add(app, BrewfatherClient(app))
    features.add(app, BrewfatherFeature(app))


def fget_brewfather(app: web.Application) -> BrewfatherFeature:
    return features.get(app, BrewfatherFeature)


def fget_blocksapi(app: web.Application) -> BlocksApi:
    return features.get(app, BlocksApi)


def fget_brewfatherapi(app: web.Application) -> BrewfatherClient:
    return features.get(app, BrewfatherClient)
