from brewblox_brewfather_service import schemas
from marshmallow import ValidationError

TESTED = schemas.__name__


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
        'brewtracker': {
            'active': False,
            'stages': [
                {
                    'position': 300,
                    'name': 'Mash',
                    'paused': True,
                    'start': 1626329336627,
                    'step': 0,
                    'duration': 300,
                    'type': 'tracker',
                    'steps': [
                        {
                            'pauseBefore': False,
                            'description': "Démarrer le tracker d'empâtage",
                            'time': 300,
                            'priority': 10,
                            'duration': 0,
                            'name': 'Start',
                            'type': 'mash'
                        },
                        {
                            'pauseBefore': True,
                            'name': 'Mash',
                            'value': 52,
                            'type': 'event',
                            'duration': 0,
                            'tooltip': 'Faire chauffer à 56.6 °C',
                            'description': "Faire chauffer <b>15.15 L</b> d'eau à 56.6 °C pour l'empâtage",
                            'time': 300,
                            'priority': 10
                        },
                    ]
                }
            ],
            'alarm': True,
            'hidden': False,
            'enabled': True,
            'notify': True,
            '_rev': 'KTZwrhUEzUUo1UCqTSZGBOFm0W9Lvz',
            'completed': False,
            'stage': 0,
            '_id': 'BDxjSu7vYe20qKSH45kLCJZqG1b1AR',
            'name': 'Brassin #8'
        },
        'stage_index': 0,
        'batch_id': 'BDxjSu7vYe20qKSH45kLCJZqG1b1AR',
        'timer': {
            'start_time': '2021-07-15T06:52:05.580774',
            'duration': 5,
            'expected_end_time': '2021-07-15T06:52:10.580774'
        },
        'automation_stage': 'MASH',
        'recipe_id': '',
        'automation_state': 'HEAT',
        'recipe_name': 'TEST RECIPE CITRA',
        'step': {
            'value': 0,
            'description': 'Empâtage terminé',
            'type': 'event',
            'pauseBefore': True,
            'tooltip': None,
            'name': 'Mash',
            'duration': 0
        },
        'step_index': 11,
        'mash_start_time': '2021-07-15T06:52:05.580774'
    }

    schema = schemas.CurrentStateSchema()
    try:
        schema.validate(state_data)
        state = schema.load(state_data)
        assert state is not None, 'state should not be of None type'
        assert state.automation_stage is not None, 'automation_stage should not be of None type'
        assert state.automation_stage == schemas.AutomationStage.MASH
        assert state.automation_state is not None, 'automation_type should not be of None type'
        assert state.automation_state == schemas.AutomationState.HEAT
        assert state.step.value == 0
        assert state.step.duration == 0
        assert state.step.name == 'Mash'
        assert state.timer is not None
        assert state.timer.expected_end_time.minute == 52
        assert state.timer.expected_end_time.year == 2021

    except ValidationError:
        raise AssertionError('data should be properly validated')
