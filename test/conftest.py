"""
Master file for pytest fixtures.
Any fixtures declared here are available to all test functions in this directory.
"""

import logging
import os

import pytest
from brewblox_service import service

from brewblox_brewfather_service.__main__ import create_parser

TEMP_ENV_VARS = {
    'BREWFATHER_USER_ID': 'USER_ID',
    'BREWFATHER_TOKEN': 'API_KEY',
}


@pytest.fixture(scope='session', autouse=True)
def log_enabled():
    """Sets log level to DEBUG for all test functions.
    Allows all logged messages to be captured during pytest runs"""
    logging.getLogger().setLevel(logging.DEBUG)
    logging.captureWarnings(True)


@pytest.fixture(scope='session', autouse=True)
def environment():
    # Will be executed before the first test
    old_environ = dict(os.environ)
    os.environ.update(TEMP_ENV_VARS)

    yield
    # Will be executed after the last test
    os.environ.clear()
    os.environ.update(old_environ)


@pytest.fixture
def app_config() -> dict:
    return {
        'mash_service_id': 'spark-one',
        'mash_setpoint_device': 'HERMS MLT Setpoint'
    }


@pytest.fixture
def sys_args(app_config) -> list:
    return [str(v) for v in [
        'app_name',
        '--mash-service-id', app_config['mash_service_id'],
        '--mash-setpoint-device', app_config['mash_setpoint_device']
    ]]


@pytest.fixture
def event_loop(loop):
    # aresponses uses the 'event_loop' fixture
    # this makes loop available under either name
    yield loop


@pytest.fixture
def app(sys_args):
    parser = create_parser('default')
    app = service.create_app(parser=parser, raw_args=sys_args[1:])
    return app


@pytest.fixture
def client(app, aiohttp_client, loop):
    """Allows patching the app or aiohttp_client before yielding it.

    Any tests wishing to add custom behavior to app can override the fixture
    """

    return loop.run_until_complete(aiohttp_client(app))
