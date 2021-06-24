"""
Schemas used
"""

import json
from enum import Enum
from datetime import datetime, timedelta
from marshmallow_enum import EnumField
from marshmallow import Schema, ValidationError, fields, post_load, EXCLUDE
from marshmallow.validate import OneOf


class AutomationType(Enum):
    MASH = 1
    BOIL = 2
    SPARGE = 3
    FERMENTATION = 4


class AutomationState(Enum):
    HEAT = 1
    REST = 2


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
    def __init__(self, automation_type: AutomationType,
                 step_index: int, step: MashStep, step_start_time=datetime.utcnow(), step_end_time=datetime.utcnow(), automation_state: AutomationState = AutomationState.REST):
        self.automation_type = automation_type
        self.automation_state = automation_state
        self.step_index = step_index
        self.step = step
        self.step_start_time = step_start_time
        self.step_end_time = step_end_time

    def __repr__(self):
        return f'<CurrentState(automation_type={self.automation_type!r}, automation_state={self.automation_state!r}, step_index= {self.step_index!r}, step={self.step!r}, step_start_time={self.step_start_time!r}, step_end_time={self.step_end_time!r})>'


class MashAutomation:
    def __init__(self, setpointDevice: Device):
        self.setpointDevice = setpointDevice


class Settings:
    def __init__(self, mashAutomation: MashAutomation):
        self.mashAutomation = mashAutomation


def validate(schema: Schema, data: dict):
    errors = schema.validate(data)
    if errors:
        raise ValidationError(errors)
    return data


class DeviceSchema(Schema):
    service_id = fields.String(required=True)
    id = fields.String(required=True)

    @post_load
    def make_device(self, data, **kwargs):
        return Device(**data)


class MashSettingsSchema(Schema):
    setpointDevice = fields.Nested(DeviceSchema, required=True)

    @post_load
    def make_mashautomation_settings(self, data, **kwargs):
        return MashAutomation(**data)


class SettingsSchema(Schema):
    mashAutomation = fields.Nested(MashSettingsSchema, required=True)

    @post_load
    def make_settings(self, data, **kwargs):
        return Settings(**data)


class MashStepSchema(Schema):
    stepTemp = fields.Int(required=True)
    rampTime = fields.Raw(required=True, allow_none=True)
    stepTime = fields.Int(required=True)
    type = fields.String(required=True, validate=OneOf(['Temperature']))
    name = fields.String(required=True)
    displayStepTemp = fields.Int(required=True)

    @post_load
    def make_mash_step(self, data, **kwargs):
        return MashStep(**data)


class MashSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    name = fields.String(required=True)
    steps = fields.Nested(MashStepSchema, many=True, required=True)
    _id = fields.String(required=True)

    @post_load
    def make_mash(self, data, **kwargs):
        return Mash(**data)


class CurrentStateSchema(Schema):
    automation_type = EnumField(AutomationType, required=True)
    automation_state = EnumField(AutomationState, required=True)
    step_index = fields.Int(required=True)
    step = fields.Nested(MashStepSchema, allow_none=True, allow_null=True)
    step_start_time = fields.DateTime(allow_none=True, allow_null=True)
    step_end_time = fields.DateTime(allow_none=True, allow_null=True)

    @post_load
    def make_current_state(self, data, **kwargs):
        return CurrentState(**data)


if __name__ == '__main__':
    with open('./mash.json', 'r') as file:
        mashstr = file.read()

    jsonstr = json.loads(mashstr)
    schema = MashSchema()
    result = schema.load(jsonstr['mash'])
    print(result)
