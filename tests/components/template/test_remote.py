import asyncio
from base64 import b64encode
from collections import defaultdict
from datetime import timedelta
from itertools import product
import logging

import pytest
import voluptuous as vol

from homeassistant.components import persistent_notification
from homeassistant.components.remote import (
    ATTR_ALTERNATIVE,
    ATTR_COMMAND_TYPE,
    ATTR_DELAY_SECS,
    ATTR_DEVICE,
    ATTR_NUM_REPEATS,
    DEFAULT_DELAY_SECS,
    DOMAIN as RM_DOMAIN,
    SERVICE_DELETE_COMMAND,
    SERVICE_LEARN_COMMAND,
    SERVICE_SEND_COMMAND,
    RemoteEntity,
    RemoteEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_COMMAND, STATE_OFF
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from homeassistant.components.template.remote import TemplateRemote

_LOGGER = logging.getLogger(__name__)

LEARNING_TIMEOUT = timedelta(seconds=30)

COMMAND_TYPE_IR = "ir"
COMMAND_TYPE_RF = "rf"
COMMAND_TYPES = [COMMAND_TYPE_IR, COMMAND_TYPE_RF]

CODE_STORAGE_VERSION = 1
FLAG_STORAGE_VERSION = 1

CODE_SAVE_DELAY = 15
FLAG_SAVE_DELAY = 15

COMMAND_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_COMMAND): vol.All(
            cv.ensure_list, [vol.All(cv.string, vol.Length(min=1))], vol.Length(min=1)
        ),
    },
    extra=vol.ALLOW_EXTRA,
)

SERVICE_SEND_SCHEMA = COMMAND_SCHEMA.extend(
    {
        vol.Optional(ATTR_DEVICE): vol.All(cv.string, vol.Length(min=1)),
        vol.Optional(ATTR_DELAY_SECS, default=DEFAULT_DELAY_SECS): vol.Coerce(float),
    }
)

SERVICE_LEARN_SCHEMA = COMMAND_SCHEMA.extend(
    {
        vol.Required(ATTR_DEVICE): vol.All(cv.string, vol.Length(min=1)),
        vol.Optional(ATTR_COMMAND_TYPE, default=COMMAND_TYPE_IR): vol.In(COMMAND_TYPES),
        vol.Optional(ATTR_ALTERNATIVE, default=False): cv.boolean,
    }
)

SERVICE_DELETE_SCHEMA = COMMAND_SCHEMA.extend(
    {vol.Required(ATTR_DEVICE): vol.All(cv.string, vol.Length(min=1))}
)


@pytest.fixture
def mock_device():
    """Mock device for testing."""
    class MockDevice:
        def __init__(self):
            self.api = self
            self.unique_id = "mock_unique_id"

        async def async_request(self, func, *args):
            return await func(*args)

        async def send_data(self, data):
            pass

        async def enter_learning(self):
            pass

        async def check_data(self):
            return b64encode(b"mock_code").decode("utf8")

        async def sweep_frequency(self):
            pass

        async def check_frequency(self):
            return True, 433.92

        async def cancel_sweep_frequency(self):
            pass

        async def find_rf_packet(self):
            pass

    return MockDevice()


@pytest.fixture
def mock_store():
    """Mock store for testing."""
    class MockStore:
        def __init__(self):
            self.data = {}

        async def async_load(self):
            return self.data

        async def async_save(self, data):
            self.data = data

        async def async_delay_save(self, data_func, delay):
            self.data = data_func()

    return MockStore()


@pytest.fixture
def template_remote(mock_device, mock_store):
    """Fixture for TemplateRemote."""
    return TemplateRemote(mock_device, mock_store, mock_store)


async def test_send_command(template_remote):
    """Test sending a command."""
    await template_remote.async_send_command(["b64:mock_code"])
    assert template_remote._flags == defaultdict(int)


async def test_learn_command(template_remote):
    """Test learning a command."""
    await template_remote.async_learn_command(
        command=["mock_command"], device="mock_device", command_type=COMMAND_TYPE_IR
    )
    assert template_remote._codes["mock_device"]["mock_command"] == "mock_code"


async def test_delete_command(template_remote):
    """Test deleting a command."""
    template_remote._codes = {"mock_device": {"mock_command": "mock_code"}}
    await template_remote.async_delete_command(
        command=["mock_command"], device="mock_device"
    )
    assert "mock_command" not in template_remote._codes["mock_device"]
