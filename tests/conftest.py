# tests/conftest.py
import os
import sys
import types
import importlib.machinery
import pytest

# Ensure we can import project modules from repo root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# If psutil isn't installed in some environments, provide a tiny stub module.
# (Also ensures __spec__ exists so importlib.util.find_spec("psutil") won't ValueError.)
try:
    import psutil  # noqa: F401
except ImportError:
    stub = types.ModuleType("psutil")
    stub.__spec__ = importlib.machinery.ModuleSpec("psutil", loader=None)
    sys.modules["psutil"] = stub


@pytest.fixture
def mock_config(mocker):
    """
    Patches the configuration so tests can control settings
    (like blacklist/whitelist) without relying on env files.
    """
    mocker.patch("config.BRIDGE_ID", "TEST_BRIDGE")
    mocker.patch("config.BRIDGE_NAME", "Test Home")

    # Make throttling instant for tests
    mocker.patch("config.RTL_THROTTLE_INTERVAL", 0)

    # Default filtering behavior for tests
    mocker.patch("config.DEVICE_BLACKLIST", ["SimpliSafe*", "BadDevice*"])
    mocker.patch("config.DEVICE_WHITELIST", [])

    # Fixture is side-effect only
    return None
