import os
import time
import pytest

from elysia.config import Settings, ElysiaKeyManager, _global_api_keys


def test_global_api_keys_are_used_as_fallback():
    """When user has no keys, global .env keys are still available."""
    # Ensure a global key exists
    os.environ["TEST_API_KEY"] = "global_value"
    # Re-populate _global_api_keys (simulate startup capture)
    _global_api_keys["test_api_key"] = "global_value"

    settings = Settings()
    # User has no API keys set
    settings.API_KEYS = {}

    with ElysiaKeyManager(settings):
        assert os.environ.get("TEST_API_KEY") == "global_value"

    # Cleanup
    _global_api_keys.pop("test_api_key", None)


def test_user_keys_override_global():
    """User-specific keys take priority over global .env keys."""
    os.environ["TEST_API_KEY"] = "global_value"
    _global_api_keys["test_api_key"] = "global_value"

    settings = Settings()
    settings.configure(api_keys={"test_api_key": "user_value"})

    with ElysiaKeyManager(settings):
        assert os.environ.get("TEST_API_KEY") == "user_value"

    # Cleanup
    _global_api_keys.pop("test_api_key", None)


def test_modified_api_keys_are_passed_down():
    os.environ["TEST_API_KEY_"] = "1234567890"
    settings = Settings()
    with ElysiaKeyManager(settings):
        assert "TEST_API_KEY_" in os.environ

    settings = Settings()
    settings.configure(api_keys={"TEST_API_KEY": "1234567890"})
    with ElysiaKeyManager(settings):
        assert "TEST_API_KEY" in os.environ


def test_exhausted_key_falls_back_to_global():
    """When a user key is marked as exhausted, the global key is used."""
    _global_api_keys["openrouter_api_key"] = "global_key"

    settings = Settings()
    settings.configure(
        api_keys={"openrouter_api_key": "user_key"},
        base_provider="openrouter/google",
        base_model="gemini-2.5-flash",
        complex_provider="openrouter/google",
        complex_model="gemini-2.5-flash",
    )

    # Manually mark the user key as exhausted
    sid = settings.SETTINGS_ID
    ElysiaKeyManager._exhausted_keys[(sid, "openrouter_api_key")] = (
        time.time() + 60
    )

    with ElysiaKeyManager(settings):
        # Should use global key since user key is exhausted
        assert os.environ.get("OPENROUTER_API_KEY") == "global_key"

    # Cleanup
    ElysiaKeyManager._exhausted_keys.clear()
    _global_api_keys.pop("openrouter_api_key", None)


def test_exhausted_key_recovers_after_cooldown():
    """After cooldown, the user key is used again."""
    _global_api_keys["openrouter_api_key"] = "global_key"

    settings = Settings()
    settings.configure(
        api_keys={"openrouter_api_key": "user_key"},
        base_provider="openrouter/google",
        base_model="gemini-2.5-flash",
        complex_provider="openrouter/google",
        complex_model="gemini-2.5-flash",
    )

    # Mark as exhausted but already expired
    sid = settings.SETTINGS_ID
    ElysiaKeyManager._exhausted_keys[(sid, "openrouter_api_key")] = (
        time.time() - 1  # already expired
    )

    with ElysiaKeyManager(settings):
        # Should use user key since cooldown expired
        assert os.environ.get("OPENROUTER_API_KEY") == "user_key"

    # Cleanup
    ElysiaKeyManager._exhausted_keys.clear()
    _global_api_keys.pop("openrouter_api_key", None)


def test_env_restored_after_context_manager():
    """Environment is fully restored after the context manager exits."""
    original_val = os.environ.get("TEST_API_KEY", None)
    os.environ["TEST_API_KEY"] = "original"

    settings = Settings()
    settings.configure(api_keys={"test_api_key": "temporary"})

    with ElysiaKeyManager(settings):
        assert os.environ.get("TEST_API_KEY") == "temporary"

    assert os.environ.get("TEST_API_KEY") == "original"

    # Cleanup
    if original_val is None:
        del os.environ["TEST_API_KEY"]
    else:
        os.environ["TEST_API_KEY"] = original_val
