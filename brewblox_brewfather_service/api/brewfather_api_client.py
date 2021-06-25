from aiohttp import BasicAuth
from brewblox_service import http


class BrewfatherClient:
    BREWFATHER_HOST = 'https://api.brewfather.app'
    BREWFATHER_API_VERSION = '/v1'
    BASE_URL = BREWFATHER_HOST + BREWFATHER_API_VERSION

    def __init__(self, app):
        self.userid = app['BREWFATHER_USER_ID']
        self.token = app['BREWFATHER_TOKEN']
        self.app = app

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
