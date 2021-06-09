"""
Checks whether we can call the hello endpoint.
"""

import pytest

from YOUR_PACKAGE import http_example


@pytest.fixture
def app(app):
    """
    This overrides the fixture defined in conftest.py.
    We can depend on the original fixture and modify its result.
    All other tests and fixtures that depend on `app` will use the modified result.
    """
    http_example.setup(app)
    return app


async def test_hello(app, client):
    """
    This test depends on a running application.
    We depend on the `app` fixture to get an application where `http_example.setup(app)`
    has been called.
    We depend on the `client` fixture where the app was started,
    and is now listening for HTTP requests.
    """
    res = await client.post('/example/endpoint', json={'message': 'hello'})
    assert res.status == 200
    assert await res.text() == 'Hello world! (You said: "hello")'
