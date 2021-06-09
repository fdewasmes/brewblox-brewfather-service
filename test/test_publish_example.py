"""
Checks whether the publish_example.PublishingFeature works as expected.
"""


import pytest
from aresponses import ResponsesMockServer
from brewblox_service import http, repeater, scheduler
from mock import AsyncMock

from YOUR_PACKAGE import publish_example

TESTED = publish_example.__name__


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

    return m


@pytest.fixture
def app(app):
    """
    RepeaterFeature depends on the `scheduler` and `http` features being enabled.
    We need to call their setup() functions during our test setup.
    """
    scheduler.setup(app)
    http.setup(app)
    return app


@pytest.fixture
def started_app(app):
    """
    In contrast with test_subscribe_example,
    we don't want to always call publish_example.setup().

    Testing code that's automatically repeating can be awkward.
    Now, the setup() function will only have been called
    if we depend on `started_app` in the test function.
    """
    publish_example.setup(app)
    return app


async def test_startup(started_app, client):
    # We're testing setup here, so we use the `started_app` fixture.

    feature = publish_example.fget(started_app)
    assert isinstance(feature, publish_example.PublishingFeature)

    # the `active` property is provided by RepeaterFeature
    assert feature.active


async def test_prepare(app, client):
    # Here we want to call functions manually,
    # so without the feature running in the background

    # features.add() shouldn't have been called
    with pytest.raises(KeyError):
        publish_example.fget(app)

    feature = publish_example.PublishingFeature(app)

    # The background task is not running
    assert not feature.active

    # Manually call prepare()
    # Usually this is done in the background task
    await feature.prepare()

    # Still not active - prepare() does not start the background task
    assert not feature.active


async def test_prepare_cancel(app, client):
    feature = publish_example.PublishingFeature(app)

    # app['config'] is set by parsing command-line arguments
    # but the result can be modified in tests
    # Here we want our background task to stop if poll interval <= 0
    # This is done by raising a specific exception (RepeaterCancelled)
    with pytest.raises(repeater.RepeaterCancelled):
        app['config']['poll_interval'] = 0
        await feature.prepare()


async def test_run(app, client, m_mqtt, aresponses: ResponsesMockServer):
    feature = publish_example.PublishingFeature(app)

    # We mock this specific URL
    # This tests our code in more detail than setting a generic mock on `session.get()`
    # It also makes it easier to test functions that make multiple HTTP requests.
    aresponses.add(
        host_pattern='jsonplaceholder.typicode.com',
        path_pattern='/todos/1',
        method_pattern='GET',
        response={'hello': 'world'},
    )

    # We don't want to wait the actual poll interval during tests
    app['config']['poll_interval'] = 0.0001

    # We expect these values to be available in config
    topic = app['config']['history_topic']
    name = app['config']['name']

    await feature.prepare()
    await feature.run()

    # We mocked the response to the HTTP request,
    # and we mocked the `mqtt.publish()` function.
    # We expect publish() to be called with the mock data.
    m_mqtt.publish.assert_awaited_once_with(
        app,
        topic,
        {
            'key': name,
            'data': {'hello': 'world'},
        },
    )

    # ... and we expect the mocked requests to have been used
    aresponses.assert_plan_strictly_followed()
