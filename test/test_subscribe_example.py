"""
Checks whether subscribe_example.SubscribingFeature works as expected.
"""

import pytest
from brewblox_service.testing import matching
from mock import AsyncMock

from YOUR_PACKAGE import subscribe_example

TESTED = subscribe_example.__name__


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
    m.subscribe = AsyncMock()
    m.listen = AsyncMock()
    m.unsubscribe = AsyncMock()
    m.unlisten = AsyncMock()

    return m


@pytest.fixture
def app(app):
    """
    This overrides the fixture defined in conftest.py.
    We can depend on the original fixture and modify its result.
    All other tests and fixtures that depend on `app` will use the modified result.

    We only call the setup() function for the features we are testing,
    and their dependencies.
    """
    subscribe_example.setup(app)
    return app


async def test_feature_startup(app, client, m_mqtt):
    """
    This test depends on both the `app`, and `client` fixtures.
    The setup() function was called in the `app` fixture,
    and the `client` fixture started the app.

    `SubscribingFeature.startup(app)` will have been called.
    """
    feature = subscribe_example.fget(app)
    assert isinstance(feature, subscribe_example.SubscribingFeature)

    m_mqtt.listen.assert_awaited_once_with(
        app,
        'brewcast/history/#',
        feature.on_message)

    m_mqtt.subscribe.assert_awaited_once_with(
        app,
        'brewcast/history/#')

    # These functions are part of shutdown(),
    # and should not yet have been called
    m_mqtt.unsubscribe.assert_not_awaited()
    m_mqtt.unlisten.assert_not_awaited()


async def test_feature_shutdown(app, client, m_mqtt):
    """
    This test depends on both the `app`, and `client` fixtures.
    The setup() function was called in the `app` fixture,
    and the `client` fixture started the app.

    `SubscribingFeature.startup(app)` will have been called.
    """
    feature = subscribe_example.fget(app)

    # shutdown() is also called when the test ends,
    # but if we want to assert results, we need to call it manually
    await feature.shutdown(app)

    m_mqtt.unlisten.assert_awaited_once_with(
        app,
        'brewcast/history/#',
        feature.on_message)

    m_mqtt.unsubscribe.assert_awaited_once_with(
        app,
        'brewcast/history/#')


async def test_on_message(app, client, mocker):
    # If we want to check whether a function is called
    # without mocking its behavior, we can set a spy
    s_logger = mocker.spy(subscribe_example, 'LOGGER')

    feature = subscribe_example.fget(app)
    await feature.on_message('hello', {'to': 'world'})

    # The actual call:
    # LOGGER.info(f'Message on topic {topic} = {message}')
    #
    # Let's assume we're not 100% sure how info will be formatted,
    # just that it should include topic and message body.
    # The `matching` test helper lets us compare with a regex string.
    s_logger.info.assert_called_once_with(matching(r'.*hello.*to.*world.*'))
