"""
Example of how to import and use the brewblox service
"""
from os import getenv
from argparse import ArgumentParser

from brewblox_service import brewblox_logger, http, mqtt, scheduler, service

from brewblox_brewfather_service import brewfather_api_client

LOGGER = brewblox_logger(__name__)


def create_parser(default_name='brewfather') -> ArgumentParser:
    parser: ArgumentParser = service.create_parser(default_name=default_name)

    return parser


def main():

    app = service.create_app(parser=create_parser())
    app['BREWFATHER_USER_ID'] = getenv('BREWFATHER_USER_ID')
    app['BREWFATHER_TOKEN'] = getenv('BREWFATHER_TOKEN')

    scheduler.setup(app)
    mqtt.setup(app)
    http.setup(app)

    brewfather_api_client.setup(app)
    service.furnish(app)

    # service.run() will start serving clients async
    service.run(app)


if __name__ == '__main__':
    main()
