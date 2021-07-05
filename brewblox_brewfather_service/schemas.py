"""
Schemas used and data classes
"""

from enum import Enum
from datetime import datetime
from marshmallow_enum import EnumField
from marshmallow import Schema, ValidationError, fields, post_load, EXCLUDE


class AutomationStage(Enum):
    MASH = 10
    SPARGE = 20
    BOIL = 30
    HOPSTAND = 40
    FERMENTATION = 50


class AutomationState(Enum):
    STANDBY = 10
    HEAT = 20
    REST = 30


class Device:
    def __init__(self, service_id: str, id: str):
        self.service_id = service_id
        self.id = id


class MashStep:
    def __init__(self, description, type, name=None, pauseBefore=None, value=0, tooltip=None, duration=0):
        self.duration = duration
        self.description = description
        self.value = value
        self.tooltip = tooltip
        self.type = type
        self.name = name
        self.pauseBefore = pauseBefore

    def __repr__(self):
        obj_rep = f'<MashStep(name={self.name!r}, description={self.description!r}, '
        obj_rep += f'duration={self.duration!r}, pauseBefore={self.pauseBefore!r})>'
        return obj_rep


class Timer:
    def __init__(self, start_time, duration, expected_end_time):
        self.start_time = start_time
        self.duration = duration
        self.expected_end_time = expected_end_time

    def __repr__(self):
        obj_rep = f'<Timer(start_time={self.start_time!r}, duration={self.duration!r}, '
        obj_rep += f'expected_end_time={self.expected_end_time!r})>'
        return obj_rep


class CurrentState:
    def __init__(self, automation_stage: AutomationStage,
                 batch_id: str,
                 recipe_id: str,
                 recipe_name: str,
                 brewtracker: dict = None,
                 mash_start_time: datetime = None,
                 automation_state: AutomationState = AutomationState.STANDBY,
                 stage_index: int = -1,
                 step_index: int = -1,
                 step: MashStep = None,
                 timer: Timer = None):
        self.automation_stage = automation_stage
        self.automation_state = automation_state
        self.mash_start_time = mash_start_time
        self.batch_id = batch_id
        self.recipe_id = recipe_id
        self.recipe_name = recipe_name
        self.brewtracker = brewtracker
        self.stage_index = stage_index
        self.step_index = step_index
        self.step = step
        self.timer = timer

    def __repr__(self):
        obj_rep = f'<CurrentState(type={self.automation_stage!r}, state={self.automation_state!r}>'
        return obj_rep


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
    class Meta:
        unknown = EXCLUDE

    duration = fields.Int(required=False)
    description = fields.String(required=True)
    value = fields.Int(required=False)
    tooltip = fields.String(required=False, allow_null=True, allow_none=True)
    type = fields.String(required=True)
    name = fields.String(required=False, allow_null=True, allow_none=True)
    pauseBefore = fields.Boolean(required=False, allow_null=True, allow_none=True)

    @post_load
    def make_mash_step(self, data, **kwargs):
        return MashStep(**data)


class TimerSchema(Schema):
    start_time = fields.DateTime(allow_none=True, allow_null=True)
    duration = fields.Int(required=False)
    expected_end_time = fields.DateTime(allow_none=True, allow_null=True)

    @post_load
    def make_timer(self, data, **kwargs):
        return Timer(**data)


class CurrentStateSchema(Schema):
    automation_stage = EnumField(AutomationStage, required=True)
    automation_state = EnumField(AutomationState, required=True)
    mash_start_time = fields.DateTime(allow_none=True, allow_null=True)
    batch_id = fields.String(required=True)
    recipe_id = fields.String(required=False)
    recipe_name = fields.String(required=True)
    brewtracker = fields.Dict(required=False)
    stage_index = fields.Int(required=True)
    step_index = fields.Int(required=True)
    step = fields.Nested(MashStepSchema, required=False, allow_none=True, allow_null=True)
    timer = fields.Nested(TimerSchema, required=False, allow_none=True, allow_null=True)

    @post_load
    def make_current_state(self, data, **kwargs):
        return CurrentState(**data)
