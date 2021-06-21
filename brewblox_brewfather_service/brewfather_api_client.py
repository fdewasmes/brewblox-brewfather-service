"""
A Brewfather API client
"""


from aiohttp import web
from aiohttp_apispec import docs
from brewblox_service import brewblox_logger, features, mqtt
from brewblox_brewfather_service.datastore import ConfigurationDatastore, Device, MashAutomation, CurrentState, Settings, DatastoreClient
from brewblox_brewfather_service import schemas
from brewblox_brewfather_service.api.brewfather_api_client import BrewfatherClient
from brewblox_brewfather_service.api.spark_api_client import SparkServiceClient

LOGGER = brewblox_logger(__name__)

routes = web.RouteTableDef()


class BrewfatherFeature(features.ServiceFeature):

    async def startup(self, app: web.Application):
        LOGGER.info(f'Starting {self}')

        # Get values from config
        LOGGER.info(self.app['config'])

        self.bfclient = BrewfatherClient(self.app)
        self.spark_client = SparkServiceClient(self.app)
        self.datastore_client = DatastoreClient(self.app)

        # TODO get these from service configuration
        self.setpoint_device = Device('spark-one', 'HERMS MT Setpoint')
        self.temp_device = Device('spark-one', 'HERMS MT Sensor')

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

        configuration = ConfigurationDatastore(
            Settings(MashAutomation(self.setpoint_device, self.temp_device)),
            CurrentState('mash', -1),
            mash)

        await self.datastore_client.store_configuration(configuration)

    async def start_automated_mash(self):
        configuration = await self.datastore_client.load_configuration()
        LOGGER.info(f'loaded configuration: {configuration}')

        LOGGER.info(f'current state: {configuration.current_state}')
        current_step = configuration.current_state.step

        current_step += 1
        try:

            target_temp = configuration.mash.steps[current_step].stepTemp
            LOGGER.info(target_temp)
            await self.adjust_mash_setpoint(target_temp)
            configuration.current_state.step = current_step
            LOGGER.info(f'current state: {configuration.current_state}')
            await self.datastore_client.store_configuration(configuration)
        except IndexError:
            LOGGER.warn('current recipe has no mash steps')

    async def adjust_mash_setpoint(self, target_temp):
        obj = {'serviceId': self.setpoint_device.service_id, 'id': self.setpoint_device.id}
        block = await self.spark_client.read_block(obj)
        block['data']['storedSetting'] = target_temp
        data = await self.spark_client.patch_block(block)
        LOGGER.info(data)

    async def get_mash_data(self, recipe_id: str) -> dict:
        recipe = await self.get_recipe(recipe_id)
        mash_data = recipe['mash']
        return mash_data

    async def on_message(self, topic: str, message: dict):
        configuration = await self.datastore_client.load_configuration()
        step = configuration.current_state.step
        try:
            mash_step = configuration.mash.steps[step]
            expected_temp = mash_step.stepTemp
            updated_temp = message['data'][self.temp_device.id]
            LOGGER.info(f'--> updated_temp: {updated_temp}, expected: {expected_temp}')
        except IndexError:
            LOGGER.warn('attempting to reach mash step whil it does not exist')


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
    # We register our feature here
    # It will now be automatically started when the service starts
    features.add(app, BrewfatherFeature(app))


def fget(app: web.Application) -> BrewfatherFeature:
    # Retrieve the registered instance of PublishingFeature
    return features.get(app, BrewfatherFeature)
