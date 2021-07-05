"""
Dataclasses and Datastore API client to store and load configuration
"""


from brewblox_service import http
from brewblox_service import brewblox_logger
from brewblox_brewfather_service import schemas


LOGGER = brewblox_logger(__name__)


class DatastoreClient:
    HISTORY_SERVICE = 'history'
    DATASTORE_API_PATH = 'datastore'
    DATASTORE_API_PATH_SET = 'set'
    DATASTORE_API_PATH_GET = 'get'
    DATASTORE_API_BASE_URL = f'http://{HISTORY_SERVICE}:5000/{HISTORY_SERVICE}/{DATASTORE_API_PATH}'

    def __init__(self, app):
        self.app = app
        self._namespace = 'brewfather'
        self._mash_steps_id = 'mash'
        self._brewtracker_id = 'brewtracker'
        self._settings_id = 'settings'
        self._mash_log_id = 'mashlog'
        self._state_id = 'state'

        self._state = None
        self._settings = None
        self._mash_steps = None


    async def store_settings(self, settings: schemas.Settings):
        """ store automation settings in datastore for later use """
        LOGGER.debug(f'storing settings: {settings}')

        session = http.session(self.app)
        url = f'{self.DATASTORE_API_BASE_URL}/{self.DATASTORE_API_PATH_SET}'

        schema = schemas.SettingsSchema()
        settings_dump = schema.dump(settings)

        payload = {'value': {'namespace': self._namespace, 'id': self._settings_id, 'data': settings_dump}}
        response = await session.post(url, json=payload)

        await response.json()
        self._settings = settings

    async def store_state(self, state: schemas.CurrentState):
        """ store automation state in datastore for later use """
        LOGGER.debug(f'storing state: {state}')
        session = http.session(self.app)
        url = f'{self.DATASTORE_API_BASE_URL}/{self.DATASTORE_API_PATH_SET}'
        schema = schemas.CurrentStateSchema()
        state_dump = schema.dump(state)

        payload = {'value': {'namespace': self._namespace, 'id': self._state_id, 'data': state_dump}}
        response = await session.post(url, json=payload)

        await response.json()
        self._state = state

    async def load_state(self) -> schemas.CurrentState:
        """ load current state from store """
        session = http.session(self.app)
        url = f'{self.DATASTORE_API_BASE_URL}/{self.DATASTORE_API_PATH_GET}'

        payload = {'namespace': self._namespace, 'id': self._state_id}
        response = await session.post(url, json=payload)
        raw_state_data = await response.json()

        # check configuration
        state_data = raw_state_data['value']['data']
        schema = schemas.CurrentStateSchema()
        schema.validate(state_data)

        state = schema.load(state_data)
        self._state = state
        return state

    async def load_brewtracker(self) -> dict:
        """ load brewtracker from store """
        session = http.session(self.app)
        url = f'{self.DATASTORE_API_BASE_URL}/{self.DATASTORE_API_PATH_GET}'

        payload = {'namespace': self._namespace, 'id': self._brewtracker_id}
        response = await session.post(url, json=payload)
        raw_brewtracker_data = await response.json()

        return raw_brewtracker_data

    async def store_brewtracker(self, brewtracker: dict) -> dict:
        """ store brewtracker to store """
        session = http.session(self.app)
        url = f'{self.DATASTORE_API_BASE_URL}/{self.DATASTORE_API_PATH_SET}'

        payload = {'value': {'namespace': self._namespace, 'id': self._state_id, 'data': brewtracker}}
        response = await session.post(url, json=payload)

        raw_brewtracker_data = await response.json()

        return raw_brewtracker_data
