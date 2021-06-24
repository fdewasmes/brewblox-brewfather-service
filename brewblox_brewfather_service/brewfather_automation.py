"""
A Brewfather API client
"""

import asyncio
from datetime import datetime, timedelta

from aiohttp import web
from aiohttp_apispec import docs
from brewblox_service import brewblox_logger, features, mqtt

from brewblox_brewfather_service.schemas import (AutomationState, AutomationType,
                                                 Device, MashAutomation, CurrentState, Settings)
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

        # TODO get these from service configuration
        setpoint_device = Device('spark-one', 'HERMS MT Setpoint')
        self.settings = Settings(MashAutomation(setpoint_device))
        await self.datastore_client.store_settings(self.settings)

        self.spark_client.on_blocks_change(self.spark_blocks_changed)

        await mqtt.listen(app, 'brewcast/state/#', self.on_message)
        await mqtt.subscribe(app, 'brewcast/state/#')

    async def shutdown(self, app: web.Application):
        """ do nothing yet"""

    async def get_recipes(self) -> list:
        recipes = await self.bfclient.recipes()
        return recipes

    async def get_recipe(self, recipe_id: str) -> dict:
        recipe = await self.bfclient.recipe(recipe_id)
        return recipe

    async def load_recipe(self, recipe_id: str):
        """load a recipe, and get ready to start automation"""
        mash_data = await self.get_mash_data(recipe_id)
        schema = schemas.MashSchema()
        mash = schema.load(mash_data)

        number_of_steps = len(mash.steps)
        if number_of_steps == 0:
            raise ValueError

        await self.datastore_client.store_mash_steps(mash_data)

    async def start_automated_mash(self):
        state = CurrentState(AutomationType.MASH, -1, None)
        await self.datastore_client.store_state(state)
        await self.proceed_to_next_step()

    async def proceed_to_next_step(self):

        mash = await self.datastore_client.load_mash()
        state = await self.datastore_client.load_state()

        LOGGER.info(f'Proceeding to next step from current state: {state}')
        current_step = state.step_index
        current_step += 1
        try:
            step = mash.steps[current_step]
            state.step = step
            state.step_index = current_step
            state.automation_state = AutomationState.HEAT
            target_temp = step.stepTemp
            await self.adjust_mash_setpoint(target_temp)
            LOGGER.info(f'current state: {state}')
            await self.datastore_client.store_state(state)
        except IndexError:
            LOGGER.warn('current recipe has no more mash steps')

    async def adjust_mash_setpoint(self, target_temp):
        try:
            block = await asyncio.wait_for(self.spark_client.read(self.settings.mashAutomation.setpointDevice.id),
                                           timeout=5.0)
            previous_temp = block['data']['storedSetting']['value']
            block['data']['storedSetting']['value'] = target_temp
            returned_block = await asyncio.wait_for(self.spark_client.patch(self.settings.mashAutomation.setpointDevice.id, block['data']),
                                                    timeout=5.0)
            new_temp = returned_block['data']['storedSetting']['value']
            LOGGER.info(f'mash setpoint changed from {previous_temp} to {new_temp}')
        except asyncio.TimeoutError as error:
            raise asyncio.TimeoutError('Failed to communicate with spark in a timely manner') from error

    async def get_mash_data(self, recipe_id: str) -> dict:
        recipe = await self.get_recipe(recipe_id)
        mash_data = recipe['mash']
        return mash_data

    async def on_message(self, topic: str, message: dict):
        """ nothing to do yet"""

    async def start_timer(self):
        state = await self.datastore_client.load_state()
        state.automation_state = AutomationState.REST
        state.step_start_time = datetime.utcnow()
        state.step_end_time = state.step_start_time + timedelta(minutes=state.step.stepTime)
        LOGGER.info(f'Starting timer duration {state.step.stepTime} for step {state.step.name}, expected end time: {state.step_end_time}')
        loop = asyncio.get_event_loop()
        loop.call_later(state.step.stepTime*60, asyncio.create_task, self.end_timer())
        await self.datastore_client.store_state(state)

    async def end_timer(self):
        LOGGER.info('Timer is over, proceeding to next step')
        await self.proceed_to_next_step()

    async def spark_blocks_changed(self, blocks):
        state = await self.datastore_client.load_state()
        step = state.step
        if state.automation_state == AutomationState.HEAT:
            try:
                expected_temp = step.stepTemp
                temp_device_block = next((block for block in blocks if block['id'] == self.settings.mashAutomation.setpointDevice.id))
                updated_temp = temp_device_block['data']['value']['value']
                LOGGER.info(f'--> updated_temp: {updated_temp}, expected: {expected_temp}')
                if updated_temp >= expected_temp:
                    await self.start_timer()
            except IndexError:
                LOGGER.warn('attempting to reach mash step while it does not exist')


@docs(
    tags=['Brewfather'],
    summary='fetch recipes',
)
@routes.get('/recipes')
async def get_recipes(request: web.Request) -> web.json_response:
    recipes = await BrewfatherClient(request.app).recipes()
    recipes_name_list = []
    for recipe in recipes:
        recipes_name_list.append({'id': recipe['_id'], 'name': recipe['name']})
    return web.json_response(recipes_name_list)


@docs(
    tags=['Brewfather'],
    summary='fetch one recipe',
)
@routes.get('/recipe/{recipe_id}')
async def get_recipe(request: web.Request) -> web.json_response:
    recipe = await BrewfatherClient(request.app).recipe(request.match_info['recipe_id'])
    return web.json_response(recipe)


@docs(
    tags=['Brewfather'],
    summary='start mash automation',
)
@routes.get('/startmash')
async def start_mash_automation(request: web.Request) -> web.json_response:
    LOGGER.info('starting mash')
    feature = fget(request.app)
    await feature.start_automated_mash()
    return web.json_response()


@docs(
    tags=['Brewfather'],
    summary='load recipe',
)
@routes.get('/recipe/{recipe_id}/load')
async def load_recipe(request: web.Request) -> web.json_response:
    LOGGER.info(f'loading recipe {request.match_info["recipe_id"]}')
    feature = fget(request.app)
    LOGGER.info(feature)

    await feature.load_recipe(request.match_info['recipe_id'])
    return web.json_response()


def setup(app: web.Application):
    app.router.add_routes(routes)
    features.add(app, BlocksApi(app, 'spark-one'))
    features.add(app, BrewfatherFeature(app))


def fget(app: web.Application) -> BrewfatherFeature:
    return features.get(app, BrewfatherFeature)
