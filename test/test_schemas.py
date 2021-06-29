from brewblox_brewfather_service import schemas
from marshmallow import ValidationError
import json

TESTED = schemas.__name__


async def test_schemas_load_mash():
    with open('test/sample_recipe.json') as json_file:
        recipe_data = json.load(json_file)
    mash_data = recipe_data['mash']

    schema = schemas.MashSchema()
    try:
        schema.validate(mash_data)
        result = schema.load(mash_data)
        assert len(result.steps) == 4
    except ValidationError:
        raise AssertionError


async def test_schemas_load_settings():
    settings_data = {
        'mashAutomation': {
            'setpointDevice': {
                'service_id': 'spark-one',
                'id': 'HERMS MT Setpoint'
            }
        }
    }
    schema = schemas.SettingsSchema()
    try:
        schema.validate(settings_data)
        settings = schema.load(settings_data)
        assert settings is not None, 'settings should not be of None type'
        assert settings.mashAutomation is not None, 'mashAutomation should not be of None type'
        assert settings.mashAutomation.setpointDevice is not None, 'setpointDevice should not be of None type'
        assert settings.mashAutomation.setpointDevice.service_id is not None, 'service_id should not be of None type'
        assert settings.mashAutomation.setpointDevice.service_id == 'spark-one'
        assert settings.mashAutomation.setpointDevice.id == 'HERMS MT Setpoint'
    except ValidationError:
        raise AssertionError('data should be properly validated')


async def test_schemas_load_state():
    state_data = {
        'automation_type': 'MASH',
        'step_start_time': None,
        'step': {
            'displayStepTemp': 72,
            'stepTime': 1,
            'rampTime': None,
            'name': 'alpha amylase',
            'stepTemp': 72,
            'type': 'Temperature'
        },
        'step_index': 2,
        'automation_state': 'HEAT',
        'step_end_time': '2021-06-25T05:13:26.230131',
        'recipe_id': 'xxx',
        'recipe_name': 'sour'
    }
    schema = schemas.CurrentStateSchema()
    try:
        schema.validate(state_data)
        state = schema.load(state_data)
        assert state is not None, 'state should not be of None type'
        assert state.automation_type is not None, 'automation_type should not be of None type'
        assert state.automation_type == schemas.AutomationType.MASH
        assert state.automation_state is not None, 'automation_type should not be of None type'
        assert state.automation_state == schemas.AutomationState.HEAT
        assert state.step_start_time is None
        assert state.step_end_time is not None
        assert state.step_end_time.minute == 13
        assert state.step_end_time.year == 2021

    except ValidationError:
        raise AssertionError('data should be properly validated')
