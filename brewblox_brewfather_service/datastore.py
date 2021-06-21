"""
A Brewfather API client
"""

from brewblox_service import brewblox_logger

LOGGER = brewblox_logger(__name__)


class Device:
    def __init__(self, service_id: str, id: str):
        self.serviceId = service_id
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
    def __init__(self, automation, step):
        self.automation = automation
        self.step = step


class MashAutomation:
    def __init__(self, setpointDevice: Device, tempDevice: Device):
        self.setpointDevice = setpointDevice
        self.tempDevice = tempDevice


class Settings:
    def __init__(self, mashAutomation: MashAutomation):
        self.mashAutomation = mashAutomation


class ConfigurationDatastore:
    def __init__(self, settings: Settings, current_state: CurrentState, mash: Mash):
        self.settings = settings
        self.current_state = current_state
        self.mash = mash
