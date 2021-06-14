"""
A Brewfather API client
"""

from aiohttp import web, BasicAuth
from brewblox_service import brewblox_logger, features, http

LOGGER = brewblox_logger(__name__)


class BrewfatherFeature(features.ServiceFeature):

    async def prepare(self):

        LOGGER.info(f'Starting {self}')

        # Get values from config
        LOGGER.info(self.app['config'])
        self.userid = self.app['config']['brewfather_user_id']
        self.token = self.app['config']['brewfather_token']
        self.bfclient = BrewfatherClient(self.userid, self.token, self.app)

    async def startup(self, app: web.Application):
        """ do nothing yet"""

    async def shutdown(self, app: web.Application):
        """ do nothing yet"""

    async def get_recipes(self) -> list:
        recipes = await self.bfclient.recipes()
        LOGGER.info(recipes)
        return recipes

    async def get_recipe(self, recipe_id: str) -> dict:
        recipe = await self.bfclient.recipe(recipe_id)
        LOGGER.info(recipe)
        return recipe

    async def get_mash_steps(self, recipe_id: str) -> dict:
        recipe = await self.get_recipe(recipe_id)
        mash = recipe['mash']
        LOGGER.info(mash)


class BrewfatherClient:
    BREWFATHER_HOST = 'https://api.brewfather.app'
    BREWFATHER_API_VERSION = '/v1'
    BASE_URL = BREWFATHER_HOST + BREWFATHER_API_VERSION

    def __init__(self, userid, token, app):
        self.userid = userid
        self.token = token
        self.app = app

    async def recipes(self) -> list:
        url = self.BASE_URL + '/recipes'
        session = http.session(self.app)
        response = await session.get(url, auth=BasicAuth(self.userid, self.token))
        all_recipes = await response.json()
        return all_recipes

    async def recipe(self, recipeid: str) -> dict:
        url = self.BASE_URL + '/recipes' + '/' + recipeid
        session = http.session(self.app)
        response = await session.get(url, auth=BasicAuth(self.userid, self.token))
        recipe = await response.json()
        return recipe


def setup(app: web.Application):
    # We register our feature here
    # It will now be automatically started when the service starts
    features.add(app, BrewfatherFeature(app))


def fget(app: web.Application) -> BrewfatherFeature:
    # Retrieve the registered instance of PublishingFeature
    return features.get(app, BrewfatherFeature)
