"""
Brewfather API client. All calls are stateless.
Depends on environment variables to get API credentials. These are added to the app object on service main function.
"""

import asyncio
from copy import deepcopy
from aiohttp import BasicAuth
from brewblox_service import brewblox_logger, repeater, http
from aiohttp import web

LOGGER = brewblox_logger(__name__)


class BrewfatherClient(repeater.RepeaterFeature):
    BREWFATHER_HOST = 'https://api.brewfather.app'
    BREWFATHER_API_VERSION = '/v1'
    BASE_URL = BREWFATHER_HOST + BREWFATHER_API_VERSION

    def __init__(self, app: web.Application):
        super().__init__(app)
        self.userid = app['BREWFATHER_USER_ID']
        self.token = app['BREWFATHER_TOKEN']
        self._brewtracker_data = None
        self._tracking = False

    async def prepare(self):
        super.__prepare__(self)
        LOGGER.info(f'Starting {self}')

    async def shutdown(self, app: web.Application):
        pass

    @property
    def brewtracker_data(self):
        return deepcopy(self._brewtracker_data)

    def start_tracking(self):
        LOGGER.debug('Start tracking brewfather')
        self._tracking = True

    async def run(self):
        # TODO: allow to setup wake interval
        await asyncio.sleep(30)
        if self._tracking:
            if self._brewtracker_data is not None:
                batch_id = self._brewtracker_data['_id']
                self._brewtracker_data = await self.brewtracker(batch_id)
                LOGGER.debug('refreshed brewtracker')

    async def recipes(self, offset: int = 0, limit: int = 10) -> list:
        url = self.BASE_URL + '/recipes'
        params = {'offset': offset, 'limit': limit}
        session = http.session(self.app)
        response = await session.get(url, params=params, auth=BasicAuth(self.userid, self.token))
        all_recipes = await response.json()
        return all_recipes

    async def recipe(self, recipe_id: str) -> dict:
        url = self.BASE_URL + '/recipes' + '/' + recipe_id
        session = http.session(self.app)
        response = await session.get(url, auth=BasicAuth(self.userid, self.token))
        recipe = await response.json()
        return recipe

    async def batches(self, status: str = None) -> dict:
        # we support only planning, brewing and fermenting as other status are irrelevant for us
        valid_status = {'Planning', 'Brewing', 'Fermenting'}
        params = {}
        if status is not None:
            if status not in valid_status:
                raise ValueError(f'status must be on of {valid_status}')
            params = {'status': status}
        url = self.BASE_URL + '/batches'
        session = http.session(self.app)
        response = await session.get(url, params=params, auth=BasicAuth(self.userid, self.token))
        batches = await response.json()
        return batches

    async def batch(self, batch_id: str) -> dict:
        if batch_id is None:
            raise ValueError('batch_id param cannot be of None type')
        if not batch_id.strip():
            raise ValueError('batch_id param cannot be empty')

        url = f'{self.BASE_URL}/batches/{batch_id}'
        session = http.session(self.app)
        response = await session.get(url, auth=BasicAuth(self.userid, self.token))
        batch = await response.json()
        return batch

    async def brewtracker(self, batch_id: str) -> dict:
        if batch_id is None:
            raise ValueError('batch_id param cannot be of None type')
        if not batch_id.strip():
            raise ValueError('batch_id param cannot be empty')

        url = f'{self.BASE_URL}/batches/{batch_id}/brewtracker'
        session = http.session(self.app)
        response = await session.get(url, auth=BasicAuth(self.userid, self.token))
        brewtracker = await response.json()
        self._brewtracker_data = brewtracker
        return brewtracker
