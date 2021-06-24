from os import getenv
from argparse import ArgumentParser

from brewblox_service import brewblox_logger, http, mqtt, scheduler, service

from brewblox_brewfather_service import brewfather_automation

LOGGER = brewblox_logger(__name__)


def create_parser(default_name='brewfather') -> ArgumentParser:
    parser: ArgumentParser = service.create_parser(default_name=default_name)

    group = parser.add_argument_group('Brewfather automation config')
    group.add_argument('--mash-service-id',
                       help='Service id driven by brewfather mash automation service. [%(default)s]',
                       type=str,
                       default='spark-one')
    group.add_argument('--mash-setpoint-device',
                       help='Setpoint device id (name) allowing to drive & control the mash temperature. [%(default)s]',
                       type=str,
                       default='HERMS MT Setpoint')

    return parser


def main():
    app = service.create_app(parser=create_parser())
    app['BREWFATHER_USER_ID'] = getenv('BREWFATHER_USER_ID')
    app['BREWFATHER_TOKEN'] = getenv('BREWFATHER_TOKEN')

    scheduler.setup(app)
    mqtt.setup(app)
    http.setup(app)

    brewfather_automation.setup(app)
    service.furnish(app)
    service.run(app)


if __name__ == '__main__':
    main()
