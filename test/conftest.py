"""
Master file for pytest fixtures.
Any fixtures declared here are available to all test functions in this directory.
"""


import logging

import pytest
from brewblox_service import service

from YOUR_PACKAGE.__main__ import create_parser


@pytest.fixture(scope='session', autouse=True)
def log_enabled():
    """Sets log level to DEBUG for all test functions.
    Allows all logged messages to be captured during pytest runs"""
    logging.getLogger().setLevel(logging.DEBUG)
    logging.captureWarnings(True)


@pytest.fixture
def app_config() -> dict:
    return {
        'poll_interval': 5,
    }


@pytest.fixture
def sys_args(app_config) -> list:
    return [str(v) for v in [
        'app_name',
        '--poll-interval', app_config['poll_interval'],
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
