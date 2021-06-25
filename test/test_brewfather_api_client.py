import pytest
from os import getenv
from brewblox_service import http
from brewblox_brewfather_service.api.brewfather_api_client import BrewfatherClient
from aresponses import ResponsesMockServer
import json

TESTED = BrewfatherClient.__name__


@pytest.fixture
async def app(app):
    http.setup(app)
    app['BREWFATHER_USER_ID'] = getenv('BREWFATHER_USER_ID')
    app['BREWFATHER_TOKEN'] = getenv('BREWFATHER_TOKEN')
    return app


async def test_recipes(app, client, aresponses: ResponsesMockServer):

    aresponses.add(
        host_pattern='api.brewfather.app',
        path_pattern='/v1/recipes',
        method_pattern='GET',
        response=[
            {
                '_id': 'id1',
                'name': 'Recipe 1',
                'author': 'user',
                'type': 'All Grain',
                'equipment': {'name': 'Kettle'},
                'style': {'name': 'Belgian Tripel'},
            },
            {
                '_id': 'id2',
                'name': 'Recipe 2',
                'author': 'user',
                'type': 'All Grain',
                'equipment': {'name': 'Kettle'},
                'style': {'name': 'White IPA'},
            }
        ],
    )
    bfclient = BrewfatherClient(app)
    recipes = await bfclient.recipes()

    aresponses.assert_plan_strictly_followed()
    assert len(recipes) == 2


async def test_recipe(app, client, aresponses: ResponsesMockServer):

    with open('test/sample_recipe.json') as json_file:
        data = json.load(json_file)
    aresponses.add(
        host_pattern='api.brewfather.app',
        path_pattern='/v1/recipes/id1',
        method_pattern='GET',
        response=data,
    )
    bfclient = BrewfatherClient(app)
    recipe = await bfclient.recipe('id1')

    aresponses.assert_plan_strictly_followed()
    assert len(recipe['mash']['steps']) == 4
