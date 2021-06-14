"""
Example of how to import and use the brewblox service
"""

from argparse import ArgumentParser

from brewblox_service import brewblox_logger, http, mqtt, scheduler, service

from brewblox_brewfather_service import brewfather_api_client

LOGGER = brewblox_logger(__name__)


def create_parser(default_name='brewblox_brewfather_service') -> ArgumentParser:
    parser: ArgumentParser = service.create_parser(default_name=default_name)

    group = parser.add_argument_group('Brewfather broker config')
    group.add_argument('--brewfather-user-id',
                       help='Brewfather userid. [%(default)s]',
                       type=str,
                       default='')
    group.add_argument('--brewfather-token',
                       help='Brewfather token [%(default)s]',
                       type=str,
                       default='')

    return parser


def main():

    app = service.create_app(parser=create_parser())

    scheduler.setup(app)
    mqtt.setup(app)
    http.setup(app)

    brewfather_api_client.setup(app)
    service.furnish(app)

    # service.run() will start serving clients async
    service.run(app)


if __name__ == '__main__':
    main()
