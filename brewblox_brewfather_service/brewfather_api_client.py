"""
A Brewfather API client
"""
from os import getenv

import json

from aiohttp import web, BasicAuth
from aiohttp_apispec import docs
from brewblox_service import brewblox_logger, features, http, mqtt
from brewblox_brewfather_service import datastore, schemas

LOGGER = brewblox_logger(__name__)

userid = getenv('BREWFATHER_USER_ID')
token = getenv('BREWFATHER_TOKEN')
bfclient = None
routes = web.RouteTableDef()


class BrewfatherFeature(features.ServiceFeature):

    async def startup(self, app: web.Application):
        LOGGER.info(f'Starting {self}')

        # Get values from config
        LOGGER.info(self.app['config'])

        self.userid = getenv('BREWFATHER_USER_ID')
        self.token = getenv('BREWFATHER_TOKEN')
        self.bfclient = BrewfatherClient(self.userid, self.token, self.app)
        self.spark_client = SparkServiceClient(self.app)
        self.datastore_client = DatastoreClient(self.app)

        # TODO get these from service configuration
        self.setpoint_device = datastore.Device('spark-one', 'HERMS MT Setpoint')
        self.temp_device = datastore.Device('spark-one', 'HERMS MT Sensor')

        await mqtt.listen(app, 'brewcast/history/#', self.on_message)
        await mqtt.subscribe(app, 'brewcast/history/#')

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

        configuration = datastore.ConfigurationDatastore(
            datastore.Settings(datastore.MashAutomation(self.setpoint_device, self.temp_device)),
            datastore.CurrentState('mash', -1),
            mash)

        self.datastore_client.store_configuration(configuration)

    async def start_automated_mash(self, recipe_id: str):
        configuration = self.datastore_client.load_configuration()
        current_step = configuration.current_state.step
        current_step += 1
        try:
            target_temp = configuration.mash.steps[current_step].stepTemp
            await self.adjust_mash_setpoint(target_temp)
            configuration.current_state.step = current_step
            self.datastore_client.store_configuration(configuration)
        except IndexError:
            LOGGER.warn('current recipe has no mash steps')

    async def adjust_mash_setpoint(self, target_temp):
        obj = {'serviceId': self.setpoint_device.serviceId, 'id': self.setpoint_device.id}
        block = await self.spark_client.read_block(obj)
        block['data']['storedSetting'] = target_temp
        data = await self.spark_client.patch_block(block)
        LOGGER.info(data)

    async def get_mash_data(self, recipe_id: str) -> dict:
        recipe = await self.get_recipe(recipe_id)
        mash_data = recipe['mash']
        return mash_data

    async def on_message(self, topic: str, message: dict):
        configuration = self.datastore_client.load_configuration()
        step = configuration.current_state.step
        try:
            mash_step = configuration.mash.steps[step]
            expected_temp = mash_step.stepTemp
            updated_temp = message['data'][self.temp_device.id]
            LOGGER.info(f'--> updated_temp: {updated_temp}, expected: {expected_temp}')
        except IndexError:
            LOGGER.warn('attempting to reach mash step whil it does not exist')


class BrewfatherClient:
    BREWFATHER_HOST = 'https://api.brewfather.app'
    BREWFATHER_API_VERSION = '/v1'
    BASE_URL = BREWFATHER_HOST + BREWFATHER_API_VERSION

    def __init__(self, user_id, token, app):
        self.userid = user_id
        self.token = token
        self.app = app

    async def recipes(self) -> list:
        url = self.BASE_URL + '/recipes'
        session = http.session(self.app)
        response = await session.get(url, auth=BasicAuth(self.userid, self.token))
        all_recipes = await response.json()
        return all_recipes

    async def recipe(self, recipe_id: str) -> dict:
        url = self.BASE_URL + '/recipes' + '/' + recipe_id
        session = http.session(self.app)
        response = await session.get(url, auth=BasicAuth(self.userid, self.token))
        recipe = await response.json()
        return recipe


class MashStep:
    def __init__(self, brewfather_step: dict):
        self._target_temp = brewfather_step['stepTemp']
        self._target_temp_unit = 'degC'
        self._duration = brewfather_step['stepTime']
        self.set_next_step(None)

    def set_next_step(self, next_step):
        self._next_step = next_step


class SparkServiceClient:
    # TODO properly handle host and service
    SPARK_HOST = '192.168.178.192'
    SPARK_SERVICE = 'spark-one'
    SPARK_BLOCKS_API_PATH = 'blocks'
    SPARK_API_BASE_URL = f'http://{SPARK_HOST}/{SPARK_SERVICE}/{SPARK_BLOCKS_API_PATH}'

    def __init__(self, app):
        self.app = app

    async def read_blocks(self) -> list:
        session = http.session(self.app)
        response = await session.post(f'{self.SPARK_API_BASE_URL}/all/read')
        block_list = await response.json()
        return block_list

    async def read_block(self, obj: dict) -> dict:
        session = http.session(self.app)
        response = await session.post(f'{self.SPARK_API_BASE_URL}/read', data=obj)
        block = await response.json()
        return block

    async def patch_block(self, obj: dict) -> dict:
        session = http.session(self.app)
        payload = json.dumps(obj)
        response = await session.post(
            f'{self.SPARK_API_BASE_URL}/patch',
            data=payload,
            headers={'Content-Type': 'application/json'})
        block = await response.json()
        return block


class DatastoreClient:
    # TODO properly handle host and service
    SPARK_HOST = '192.168.178.192'
    DATASTORE_SERVICE = '/history/datastore'
    SET_API_PATH = '/set'
    GET_API_PATH = '/get'
    DATASTORE_API_BASE_URL = f'http://{SPARK_HOST}/{DATASTORE_SERVICE}'

    def __init__(self, app):
        self.app = app

    async def store_configuration(self, configuration: datastore.ConfigurationDatastore):
        """ store mash steps in datastore for later use """
        session = http.session(self.app)
        url = f'{self.DATASTORE_API_BASE_URL}{self.SET_API_PATH}'
        schema = schemas.ConfigurationDatastoreSchema()
        configuration_dump = schema.dump(configuration)

        # TODO generate an id?
        payload = json.dumps({'value': {'namespace': 'brewfather', 'id': '1', 'configuration': configuration_dump}})
        LOGGER.info(payload)
        response = await session.post(url, data=payload, headers={'Content-Type': 'application/json'})
        await response.json()

    async def load_configuration(self) -> datastore.ConfigurationDatastore:
        """ load current configuration from store """
        session = http.session(self.app)
        url = f'{self.DATASTORE_API_BASE_URL}{self.GET_API_PATH}'

        payload = json.dumps({'value': {'namespace': 'brewfather', 'id': '1'}})
        LOGGER.info(payload)
        response = await session.post(url, data=payload, headers={'Content-Type': 'application/json'})
        configuration_data = await response.json()
        schema = schemas.ConfigurationDatastoreSchema()
        schema.validate(configuration_data)
        configuration = schema.load(configuration_data)
        return configuration


@docs(
    tags=['Brewfather'],
    summary='fetch recipes',
)
@routes.get('/recipes')
async def get_recipes(request: web.Request) -> web.Response:
    recipes = await bfclient.recipes()
    recipes_name_list = []
    for recipe in recipes:
        recipes_name_list.append({'id': recipe['_id'], 'name':recipe['name']})
    return web.Response(body=json.dumps(recipes_name_list))


@docs(
    tags=['Brewfather'],
    summary='fetch one recipe',
)
@routes.get('/recipe/{recipe_id}')
async def get_recipe(request: web.Request) -> web.Response:
    recipe = await bfclient.recipe(request.match_info['recipe_id'])
    return web.Response(body=json.dumps(recipe))


def setup(app: web.Application):
    # TODO is there a better way instead of crapy global variable?
    global userid
    global token
    global bfclient
    bfclient = BrewfatherClient(userid, token, app)
    app.router.add_routes(routes)
    # We register our feature here
    # It will now be automatically started when the service starts
    features.add(app, BrewfatherFeature(app))


def fget(app: web.Application) -> BrewfatherFeature:
    # Retrieve the registered instance of PublishingFeature
    return features.get(app, BrewfatherFeature)
