from feature_flags import is_shadow_mode_enabled, reload as reload_features


def setup_function():
    reload_features()


def test_shadow_mode_disabled_by_default():
    assert is_shadow_mode_enabled({}) is False


def test_shadow_mode_can_be_overridden_via_env():
    assert is_shadow_mode_enabled({"PUZZLE_SHADOW_MODE_ENABLED": "1"}) is True
    assert is_shadow_mode_enabled({"PUZZLE_SHADOW_MODE_ENABLED": "off"}) is False
    assert is_shadow_mode_enabled({"SHADOW_MODE_ENABLED": "true"}) is True
