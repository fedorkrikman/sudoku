from orchestrator import orchestrator


def test_shadow_defaults_from_features_file() -> None:
    overrides = {"PUZZLE_ROOT_SEED": "config-defaults"}
    result = orchestrator.run_pipeline(env_overrides=overrides)
    policy = result["modules"]["solver"]["shadow_policy"]
    assert policy["sample_rate"] == "0"
    assert policy["hash_salt"] == "dev-seed"
    assert policy["enabled"] is False


def test_cli_overrides_take_precedence_over_env() -> None:
    overrides = {
        "PUZZLE_ROOT_SEED": "config-override",
        "SHADOW_ENABLED": "0",
        "PUZZLE_SHADOW_SAMPLE_RATE": "0.60",
        "PUZZLE_SHADOW_HASH_SALT": "env-salt",
        "CLI_SHADOW_ENABLED": "1",
        "CLI_SHADOW_SAMPLE_RATE": "0.80",
        "CLI_SHADOW_HASH_SALT": "cli-salt",
    }
    result = orchestrator.run_pipeline(env_overrides=overrides)
    policy = result["modules"]["solver"]["shadow_policy"]
    assert policy["enabled"] is True
    assert policy["sample_rate"] == "0.8"
    assert policy["hash_salt"] == "cli-salt"
