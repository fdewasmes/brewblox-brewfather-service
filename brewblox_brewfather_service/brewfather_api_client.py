"""
A Brewfather API client
"""

from aiohttp import web
from brewblox_service import brewblox_logger, features, http

LOGGER = brewblox_logger(__name__)


class BrewfatherFeature(features.ServiceFeature):

    async def prepare(self):

        LOGGER.info(f'Starting {self}')

        # Get values from config
        userid = self.app['config']['userid']
        token = self.app['config']['token']
        self.bfclient = BrewfatherClient(userid, token)

    async def startup(self, app: web.Application):
        self.bfclient.recipes()

    async def shutdown(self, app: web.Application):
        """ do nothing yet"""


class BrewfatherClient:

    BREWFATHER_HOST = "https://api.brewfather.app"
    BREWFATHER_API_VERSION = "/v1"
    BASE_URL = BREWFATHER_API_VERSION + BREWFATHER_API_VERSION

    def __init__(self, userid, token):
        self.userid = userid
        self.token = token

    async def recipes(self):
        url = self.BASE_URL + "/recipes"
        session = http.session(self.app)
        response = await session.get(url)
        data = await response.json()
        LOGGER.info(data)


def setup(app: web.Application):
    # We register our feature here
    # It will now be automatically started when the service starts
    features.add(app, BrewfatherFeature(app))


def fget(app: web.Application) -> BrewfatherFeature:
    # Retrieve the registered instance of PublishingFeature
    return features.get(app, BrewfatherFeature)
