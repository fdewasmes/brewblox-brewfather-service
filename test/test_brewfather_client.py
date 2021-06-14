"""
Checks whether we can call the hello endpoint.
"""
import logging
import pytest

from brewblox_service import http, service
from brewblox_brewfather_service import brewfather_api_client
from aresponses import ResponsesMockServer
from brewblox_brewfather_service.__main__ import create_parser

TESTED = brewfather_api_client.__name__


@pytest.fixture(scope='session', autouse=True)
def log_enabled():
    """Sets log level to DEBUG for all test functions.
    Allows all logged messages to be captured during pytest runs"""
    logging.getLogger().setLevel(logging.DEBUG)
    logging.captureWarnings(True)


@pytest.fixture
async def app(app):
    app = service.create_app(parser=create_parser())
    app['config']['brewfather_user_id'] = 'user'
    app['config']['brewfather_token'] = 'token'
    app['config']['brewfather_user_id'] = '0I98vlCQtJUedKRyWlMcY181eIm2'
    app['config']['brewfather_token'] = 'bPBEUC4qZnksTKc6MNpYFHL5wMXxGqDmD0JKOC8GyXaXhJWvxuTgqSM2RrBsQ1sY'

    http.setup(app)
    brewfather_api_client.setup(app)
    feature = brewfather_api_client.fget(app)

    await feature.prepare()
    return app


async def test_getrecipes(app, client, aresponses: ResponsesMockServer):
    feature = brewfather_api_client.fget(app)

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

    await feature.get_recipes()
    aresponses.assert_plan_strictly_followed()


async def test_getrecipe(app, client):
    feature = brewfather_api_client.fget(app)

    await feature.get_mash_steps('MuBxiHOBDXru6BcYavJKrGZ9aUmQTo')
