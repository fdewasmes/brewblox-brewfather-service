"""
Schemas used
"""

import json
from marshmallow import Schema, ValidationError, fields, post_load
from marshmallow.validate import OneOf
from brewblox_brewfather_service import datastore


def validate(schema: Schema, data: dict):
    errors = schema.validate(data)
    if errors:
        raise ValidationError(errors)
    return data


class DeviceSchema(Schema):
    service_id = fields.String(Required=True)
    id = fields.String(Required=True)

    @post_load
    def make_device(self, data, **kwargs):
        return datastore.Device(**data)


class MashSettingsSchema(Schema):
    setpointDevice = fields.Nested(DeviceSchema, Required=True)

    @post_load
    def make_mashautomation_settings(self, data, **kwargs):
        return datastore.MashAutomation(**data)


class SettingsSchema(Schema):
    mashAutomation = fields.Nested(MashSettingsSchema, Required=True)

    @post_load
    def make_settings(self, data, **kwargs):
        return datastore.Settings(**data)


class MashStepSchema(Schema):
    stepTemp = fields.Int(Required=True)
    rampTime = fields.Raw(Required=True, allow_none=True)
    stepTime = fields.Int(Required=True)
    type = fields.String(Required=True, validate=OneOf(['Temperature']))
    name = fields.String(Required=True)
    displayStepTemp = fields.Int(Required=True)

    @post_load
    def make_mash_step(self, data, **kwargs):
        return datastore.MashStep(**data)


class MashSchema(Schema):
    name = fields.String(Required=True)
    steps = fields.Nested(MashStepSchema, many=True, Required=True)
    _id = fields.String(Required=True)

    @post_load
    def make_mash(self, data, **kwargs):
        return datastore.Mash(**data)


class CurrentStateSchema(Schema):
    automation = fields.String(Required=True, validate=OneOf(['mash', 'boil', 'sparge', 'fermentation']))
    step = fields.Int(Required=True)

    @post_load
    def make_current_state(self, data, **kwargs):
        return datastore.CurrentState(**data)


class ConfigurationDatastoreSchema(Schema):
    settings = fields.Nested(SettingsSchema, Required=True)
    current_state = fields.Nested(CurrentStateSchema, Required=True)
    mash = fields.Nested(MashSchema, Required=False)

    @post_load
    def make_configuration(self, data, **kwargs):
        return datastore.ConfigurationDatastore(**data)


if __name__ == '__main__':
    with open('./mash.json', 'r') as file:
        mashstr = file.read()

    jsonstr = json.loads(mashstr)
    schema = MashSchema()
    result = schema.load(jsonstr['mash'])
    print(result)
