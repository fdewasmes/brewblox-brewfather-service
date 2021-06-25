"""
Integration of mash automation based on Brewfather recipes
In order to get started, load_recipe(self, recipe_id: str) should be called and then start_mash()
"""

import asyncio
from datetime import datetime, timedelta

from aiohttp import web
from aiohttp_apispec import docs
from brewblox_service import brewblox_logger, features, mqtt

from brewblox_brewfather_service.schemas import (AutomationState, AutomationType, CurrentStateSchema,
                                                 Device, MashAutomation, CurrentState, MashStep, Settings)
from brewblox_brewfather_service.datastore import DatastoreClient
from brewblox_brewfather_service import schemas
from brewblox_brewfather_service.api.brewfather_api_client import BrewfatherClient
from brewblox_spark_api.blocks_api import BlocksApi

LOGGER = brewblox_logger(__name__)

routes = web.RouteTableDef()


class BrewfatherFeature(features.ServiceFeature):

    async def startup(self, app: web.Application):
        LOGGER.info(f'Starting {self}')

        # Get values from config
        LOGGER.info(self.app['config'])

        self.bfclient = BrewfatherClient(self.app)
        self.spark_client = features.get(app, BlocksApi)
        self.datastore_client = DatastoreClient(self.app)

        config = app['config']
        service_id = config['mash_service_id']
        setpoint_device_id = config['mash_setpoint_device']

        self.name = self.app['config']['name']
        self.topic = f'brewcast/state/{self.name}'

        setpoint_device = Device(service_id, setpoint_device_id)
        self.settings = Settings(MashAutomation(setpoint_device))
        await self.datastore_client.store_settings(self.settings)

        self.spark_client.on_blocks_change(self.spark_blocks_changed)

        await mqtt.listen(app, 'brewcast/state/#', self.on_message)
        await mqtt.subscribe(app, 'brewcast/state/#')

    async def shutdown(self, app: web.Application):
        """ do nothing yet"""
        LOGGER.info(f'Shutting down {self}')

    async def load_recipe(self, recipe_id: str):
        """load a recipe from Brewfather, and get ready for automation"""
        recipe = await self.bfclient.recipe(recipe_id)

        LOGGER.debug(f'Loaded recipe from Brewfather: {recipe}')

        mash_data = recipe['mash']
        schema = schemas.MashSchema()
        mash = schema.load(mash_data)

        number_of_steps = len(mash.steps)
        if number_of_steps == 0:
            raise ValueError('Recipe contains no mash step')

        await self.datastore_client.store_mash_steps(mash_data)
        LOGGER.info(f'Loaded recipe {mash.name} from Brewfather containing {len(mash.steps)} mash steps')
        for step in mash.steps:
            LOGGER.info(f'step: {step.name} - {step.stepTemp}°C - {step.stepTime} minutes')

    async def start_automated_mash(self):
        """
        Starts automation from the previously loaded recipe.
        """
        state = CurrentState(AutomationType.MASH, -1, None)
        await self.datastore_client.store_state(state)
        schema = CurrentStateSchema()
        state_str = schema.dump(state)
        log_msg = '== Starting mash =='
        LOGGER.info(log_msg)
        await mqtt.publish(self.app,
                           self.topic,
                           {
                               'key': self.name,
                               'data': {
                                   'status_msg': log_msg,
                                   'state': state_str
                               }
                           })
        await self.__proceed_to_next_step()

    async def __proceed_to_next_step(self):
        """
        load recipe next temperature step
        and adjust mash temperature (heat) setpoint according to recipe next step
        """
        mash = await self.datastore_client.load_mash()
        state = await self.datastore_client.load_state()

        LOGGER.debug(f'Proceeding to next step from current state: {state}')
        current_step = state.step_index
        current_step += 1
        try:
            step = mash.steps[current_step]
            state.step = step
            state.step_index = current_step
            state.automation_state = AutomationState.HEAT
            target_temp = step.stepTemp
            await self.__adjust_mash_setpoint(target_temp)
            LOGGER.debug(f'new state: {state}')
            await self.datastore_client.store_state(state)
            log_msg = f'{state.step.name}: heating to {state.step.stepTemp}°C'
            LOGGER.info(log_msg)

            # let others know we procedeed to next step
            schema = CurrentStateSchema()
            state_str = schema.dump(state)
            await mqtt.publish(self.app,
                               self.topic,
                               {
                                    'key': self.name,
                                    'data': {
                                        'status_msg': log_msg,
                                        'state': state_str
                                    }
                               })
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

    async def __start_timer(self):
        state = await self.datastore_client.load_state()
        state.automation_state = AutomationState.REST
        state.step_start_time = datetime.utcnow()
        state.step_end_time = state.step_start_time + timedelta(minutes=state.step.stepTime)

        loop = asyncio.get_event_loop()
        loop.call_later(state.step.stepTime*60, asyncio.create_task, self.__end_timer(state.step))
        await self.datastore_client.store_state(state)

        log_msg = f'{state.step.name}: Starting timer {state.step.stepTime} minutes ({state.step.stepTemp}°C), '
        log_msg += f'expected end time: {state.step_end_time}'
        LOGGER.info(log_msg)

        schema = CurrentStateSchema()
        state_str = schema.dump(state)
        await mqtt.publish(self.app,
                           self.topic,
                           {
                                'key': self.name,
                                'data': {
                                    'status_msg': log_msg,
                                    'state': state_str
                                }
                           })

    async def __end_timer(self, step: MashStep):
        state = await self.datastore_client.load_state()

        log_msg = f'{step.name}: {step.stepTime} minutes timer ({step.stepTemp}°C) is over, proceeding to next step'
        LOGGER.info(log_msg)

        schema = CurrentStateSchema()
        state_str = schema.dump(state)

        await mqtt.publish(self.app,
                           self.topic,
                           {
                                'key': self.name,
                                'data': {
                                    'status_msg': log_msg,
                                    'state': state_str
                                }
                           })
        await self.__proceed_to_next_step()

    async def on_message(self, topic: str, message: dict):
        """ nothing to do yet"""

    async def spark_blocks_changed(self, blocks):
        state = await self.datastore_client.load_state()
        step = state.step
        if state.automation_state == AutomationState.HEAT:
            try:
                expected_temp = step.stepTemp
                setpoint_dev_id = self.settings.mashAutomation.setpointDevice.id
                temp_device_block = next((block for block in blocks if block['id'] == setpoint_dev_id))
                updated_temp = temp_device_block['data']['value']['value']
                LOGGER.info(f'--> updated_temp: {updated_temp}, expected: {expected_temp}')
                if updated_temp >= expected_temp:
                    await self.__start_timer()
            except IndexError:
                LOGGER.warn('attempting to reach mash step while it does not exist')


@docs(
    tags=['Brewfather'],
    summary='fetch recipes from Brewfather. You can paginate by using offset and limit query parameters. Both parameters are optional. Offset defaults to 0 and limit to 10',
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
    recipes_name_list = []
    for recipe in recipes:
        recipes_name_list.append({'id': recipe['_id'], 'name': recipe['name']})
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
    LOGGER.debug('REST API: starting mash')
    feature = fget(request.app)
    await feature.start_automated_mash()
    return web.json_response()


@docs(
    tags=['Brewfather'],
    summary='load recipe and get ready for automating the mash. Once done you can call startmash endpoint',
)
@routes.get('/recipe/{recipe_id}/load')
async def load_recipe(request: web.Request) -> web.json_response:
    LOGGER.debug(f'REST API: loading recipe {request.match_info["recipe_id"]}')
    feature = fget(request.app)
    await feature.load_recipe(request.match_info['recipe_id'])
    return web.json_response()


def setup(app: web.Application):
    app.router.add_routes(routes)
    features.add(app, BlocksApi(app, 'spark-one'))
    features.add(app, BrewfatherFeature(app))


def fget(app: web.Application) -> BrewfatherFeature:
    return features.get(app, BrewfatherFeature)
