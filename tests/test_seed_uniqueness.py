import sudoku_generator

from orchestrator import orchestrator


def _normalise_symbol_pattern(grid: str) -> str:
    mapping: dict[str, str] = {}
    next_id = 0
    pattern: list[str] = []
    for ch in grid:
        if ch not in mapping:
            mapping[ch] = str(next_id)
            next_id += 1
        pattern.append(mapping[ch])
    return ",".join(pattern)


def test_run_pipeline_without_explicit_seed_uses_unique_root_seed() -> None:
    first = orchestrator.run_pipeline(env_overrides={"PUZZLE_ROOT_SEED": ""})
    second = orchestrator.run_pipeline(env_overrides={"PUZZLE_ROOT_SEED": ""})

    assert first["root_seed"] != second["root_seed"]
    assert first["run_id"] != second["run_id"]
    assert first["complete_id"] != second["complete_id"]


def test_complete_grid_changes_layout_for_different_seeds() -> None:
    spec = {
        "artifact_id": "spec-layout-check",
        "name": "sudoku-9x9",
        "size": 9,
        "block": {"rows": 3, "cols": 3},
        "alphabet": list("123456789"),
    }

    first = sudoku_generator.port_generate_complete(spec, seed="seed-alpha")
    second = sudoku_generator.port_generate_complete(spec, seed="seed-beta")

    assert first["grid"] != second["grid"]
    assert _normalise_symbol_pattern(first["grid"]) != _normalise_symbol_pattern(second["grid"])
