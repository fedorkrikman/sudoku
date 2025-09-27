from feature_flags import (
    get_shadow_feature,
    is_shadow_mode_enabled,
    reload as reload_features,
)


def setup_function():
    reload_features()


def test_shadow_mode_disabled_by_default():
    assert is_shadow_mode_enabled({}, profile="dev") is False


def test_shadow_mode_can_be_overridden_via_env():
    assert is_shadow_mode_enabled({"CLI_SHADOW_ENABLED": "1"}, profile="dev") is True
    assert is_shadow_mode_enabled({"SHADOW_ENABLED": "off"}, profile="dev") is False
    assert is_shadow_mode_enabled({"PUZZLE_SHADOW_MODE_ENABLED": "true"}, profile="dev") is True


def test_shadow_feature_merges_profile_overrides():
    dev = get_shadow_feature("dev")
    prod = get_shadow_feature("prod")
    assert dev["hash_salt"] == "dev-seed"
    assert prod["hash_salt"] == "prod-salt"
