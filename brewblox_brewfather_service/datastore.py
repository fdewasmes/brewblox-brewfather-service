"""
Dataclasses and Datastore API client to store and load configuration
"""

from brewblox_service import http
from brewblox_service import brewblox_logger
from brewblox_brewfather_service import schemas


LOGGER = brewblox_logger(__name__)


class Device:
    def __init__(self, service_id: str, id: str):
        self.service_id = service_id
        self.id = id


class MashStep:
    def __init__(self, stepTemp, rampTime, stepTime, type, name, displayStepTemp):
        self.stepTemp = stepTemp
        self.rampTime = rampTime
        self.stepTime = stepTime
        self.type = type
        self.name = name
        self.displayStepTemp = displayStepTemp

    def __repr__(self):
        return '<MashStep(name={self.name!r})>'.format(self=self)


class Mash:
    def __init__(self, name, steps, _id):
        self.name = name
        self.steps = steps
        self._id = _id

    def __repr__(self):
        return f'<Mash(name={self.name!r}, steps={self.steps!r})>'


class CurrentState:
    # TODO define enum
    def __init__(self, automation: str, step: int):
        self.automation = automation
        self.step = step

    def __repr__(self):
        return f'<CurrentState(automation={self.automation!r}, step={self.step!r})>'


class MashAutomation:
    def __init__(self, setpointDevice: Device, temp_sensor: Device):
        self.setpointDevice = setpointDevice
        self.temp_sensor = temp_sensor


class Settings:
    def __init__(self, mashAutomation: MashAutomation):
        self.mashAutomation = mashAutomation


class ConfigurationDatastore:
    def __init__(self, settings: Settings, current_state: CurrentState, mash: Mash):
        self.settings = settings
        self.current_state = current_state
        self.mash = mash

    def __repr__(self):
        return f'<Configuration(settings={self.settings!r}, current_state={self.current_state!r}, mash={self.mash!r})>'


class DatastoreClient:
    # TODO properly handle host and service
    SPARK_HOST = '192.168.178.192'
    DATASTORE_SERVICE = '/history/datastore'
    SET_API_PATH = '/set'
    GET_API_PATH = '/get'
    DATASTORE_API_BASE_URL = f'http://{SPARK_HOST}{DATASTORE_SERVICE}'

    def __init__(self, app):
        self.app = app

    async def store_configuration(self, configuration: ConfigurationDatastore):
        """ store mash steps in datastore for later use """
        LOGGER.info(f'storing configuration: {configuration}')
        session = http.session(self.app)
        url = f'{self.DATASTORE_API_BASE_URL}{self.SET_API_PATH}'
        schema = schemas.ConfigurationDatastoreSchema()
        configuration_dump = schema.dump(configuration)
        LOGGER.info(configuration_dump)

        # TODO generate an id?
        payload = {'value': {'namespace': 'brewfather', 'id': '1', 'configuration': configuration_dump}}
        response = await session.post(url, json=payload)

        await response.json()

    async def load_configuration(self) -> ConfigurationDatastore:
        """ load current configuration from store """
        session = http.session(self.app)
        url = f'{self.DATASTORE_API_BASE_URL}{self.GET_API_PATH}'

        payload = {'namespace': 'brewfather', 'id': '1'}
        response = await session.post(url, json=payload)
        raw_configuration_data = await response.json()
        configuration_data = raw_configuration_data['value']['configuration']
        schema = schemas.ConfigurationDatastoreSchema()
        schema.validate(configuration_data)

        configuration = schema.load(configuration_data)
        LOGGER.info(configuration)
        return configuration
