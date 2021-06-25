"""
Checks whether we can call the hello endpoint.
"""

import pytest
from os import getenv
from brewblox_service import http, mqtt
from aresponses import ResponsesMockServer
from brewblox_brewfather_service import brewfather_automation
from mock import AsyncMock

TESTED = brewfather_automation.__name__


@pytest.fixture(autouse=True)
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
async def app(app):
    http.setup(app)
    mqtt.setup(app)
    return app


@pytest.fixture
def started_app(app, m_mqtt, aresponses: ResponsesMockServer):
    app['BREWFATHER_USER_ID'] = getenv('BREWFATHER_USER_ID')
    app['BREWFATHER_TOKEN'] = getenv('BREWFATHER_TOKEN')
    aresponses.add(
        host_pattern='history:5000',
        path_pattern='/history/datastore/set',
        method_pattern='POST',
        response={
            'id': 'settings',
            'namespace': 'brewfather',
            'data': {
                'mashAutomation': {
                    'setpointDevice': {
                        'service_id': 'spark-one',
                        'id': 'HERMS MT Setpoint'
                    }
                }
            }
        },
    )
    brewfather_automation.setup(app)

    return app


async def test_get_recipes(app, client, aresponses: ResponsesMockServer):

    aresponses.add(
        host_pattern='https://api.brewfather.app',
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
    """res = await client.get('/recipes')
    assert res.status == 200
    response = await res.json()

    aresponses.assert_plan_strictly_followed()
    assert len(response) == 2"""
