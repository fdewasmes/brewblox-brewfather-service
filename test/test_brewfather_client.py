"""
Checks whether we can call the hello endpoint.
"""

import pytest

from brewblox_service import http, service, mqtt
from brewblox_brewfather_service import brewfather_automation
from aresponses import ResponsesMockServer
from brewblox_brewfather_service.__main__ import create_parser

TESTED = brewfather_automation.__name__


@pytest.fixture
async def app(app):
    app = service.create_app(parser=create_parser())

    http.setup(app)
    mqtt.setup(app)
    brewfather_automation.setup(app)
    feature = brewfather_automation.fget(app)
    await feature.startup(app)
    return app


async def test_getrecipes(app, client, aresponses: ResponsesMockServer):
    feature = brewfather_automation.fget(app)

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


async def test_start_automated_mash(app, client):
    feature = brewfather_automation.fget(app)
    await feature.start_automated_mash('wbM4VL9qLjCMAvrg2aM8V3BtDq0yHX')
