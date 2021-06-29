"""
Checks whether we can call the hello endpoint.
"""

import json
from os import getenv

import pytest
from aresponses import ResponsesMockServer
from brewblox_service import http
from brewblox_service.testing import response
from brewblox_spark_api import blocks_api
from mock import AsyncMock

from brewblox_brewfather_service import brewfather_automation

TESTED = brewfather_automation.__name__


@pytest.fixture(scope='session')
def sample_recipe():
    with open('test/sample_recipe.json') as json_file:
        data = json.load(json_file)
    return data


@pytest.fixture
def m_mqtt(mocker):
    """
    We don't want to create and connect to a MQTT broker here.
    That takes too long, and is too fragile.
    We'll just mock the used mqtt functions, and assert they are called as expected.
    Set `autouse=True` if you want all tests and fixtures to use this mock.
    """
    m = mocker.patch(TESTED + '.mqtt')

    # async functions must be mocked explicitly
    m.publish = AsyncMock()
    m.listen = AsyncMock()
    m.subscribe = AsyncMock()

    return m


@pytest.fixture
def m_api_mqtt(mocker):
    m = mocker.patch(blocks_api.__name__ + '.mqtt')

    # async functions must be mocked explicitly
    m.publish = AsyncMock()
    m.listen = AsyncMock()
    m.unlisten = AsyncMock()
    m.subscribe = AsyncMock()
    m.unsubscribe = AsyncMock()

    return m


@pytest.fixture
def app(app, m_mqtt, m_api_mqtt):
    app['BREWFATHER_USER_ID'] = getenv('BREWFATHER_USER_ID')
    app['BREWFATHER_TOKEN'] = getenv('BREWFATHER_TOKEN')

    http.setup(app)
    brewfather_automation.setup(app)

    # Skip finish_init function
    # We'd rather test this manually
    brewfather_automation.fget_brewfather(app).finished = True

    return app


async def test_get_recipes(app, client, aresponses: ResponsesMockServer):
    # Required to avoid spurious intercepts by aresponses
    aresponses.add(
        path_pattern='/recipes',
        method_pattern='GET',
        response=aresponses.passthrough,
    )
    # Called by the /recipes endpoint
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

    data = await response(client.get('/recipes'))
    assert len(data) == 2

    aresponses.assert_plan_strictly_followed()


async def test_load_recipe(app, client, sample_recipe, aresponses: ResponsesMockServer):
    # Required to avoid spurious intercepts by aresponses
    aresponses.add(
        path_pattern='/recipe/id1/load',
        method_pattern='GET',
        response=aresponses.passthrough,
    )
    # Called by the /recipe/{id}/load endpoint
    aresponses.add(
        host_pattern='api.brewfather.app',
        path_pattern='/v1/recipes/id1',
        method_pattern='GET',
        response=sample_recipe,
    )
    aresponses.add(
        path_pattern='/history/datastore/set',
        method_pattern='POST',
        response={},
    )
    aresponses.add(
        path_pattern='/history/datastore/set',
        method_pattern='POST',
        response={},
    )

    await response(client.get('/recipe/id1/load'))
    aresponses.assert_plan_strictly_followed()

