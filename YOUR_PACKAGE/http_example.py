"""
An example of how to register HTTP endpoints
"""

from aiohttp import web
from aiohttp_apispec import docs

routes = web.RouteTableDef()


def setup(app: web.Application):
    # Register routes in this file (/example/endpoint in our case)
    app.router.add_routes(routes)


@docs(
    tags=['Example'],
    summary='Example endpoint',
    description='An example of how to use aiohttp features',
    parameters=[{
        'in': 'body',
        'name': 'body',
        'description': 'Input message',
        'required': 'true',
        'schema': {
            'type': 'object',
            'required': ['message'],
            'properties': {
                'message': {'type': 'string'}
            },
        },
    }],
)
@routes.post('/example/endpoint')
async def example_endpoint_handler(request: web.Request) -> web.Response:
    """
    Example endpoint handler. Using `routes.post` means it will only respond to POST requests.

    Each aiohttp endpoint should take a request as argument, and return a response.
    You can use aiohttp-apispec to document your endpoint.
    This adds the endpoint to those shown in the /{name}/api/doc page.

    You can also use marshmallow to validate input.
    For more information, see: https://aiohttp-apispec.readthedocs.io/en/latest/index.html
    """
    args = await request.json()
    message = args['message']
    return web.Response(body=f'Hello world! (You said: "{message}")')
