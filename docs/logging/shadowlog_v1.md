# Shadowlog v1 schema

> Verified on 2025-09-26

Shadowlog events фиксируют тени solver-исполнения рядом с основным Sudoku
конвейером. События испускаются в JSON со следующими обязательными полями:

| Field | Type | Description |
| --- | --- | --- |
| ``schema_ver`` | string | Literal ``"shadowlog/1"``. |
| ``ts`` | string | ISO8601 timestamp (UTC) derived deterministically from the sample digest. |
| ``profile`` | string | Validation profile (``dev``/``ci``/``prod``). |
| ``stage`` | string | Pipeline stage, e.g. ``"solver:check_uniqueness"``. |
| ``module_id`` | string | Identifier of the primary solver module. |
| ``impl_id`` | string | Implementation name (``novus`` or ``legacy``). |
| ``decision_source`` | string | Router decision source (``config``/``env``/``fallback``). |
| ``sampled`` | bool | ``True`` if the shadow execution was performed. |
| ``sample_rate`` | float | Effective sampling rate used for the run. |
| ``hash_salt_set`` | bool | Indicates whether a hash salt was provided. |
| ``run_id`` | string | Pipeline run identifier. |
| ``seed`` | string | Stage seed (hexadecimal). |
| ``u64_digest_trunc`` | string | First eight bytes of the SHA-256 digest in hex. |
| ``verdict_unique`` | bool\|null | Primary solver unique flag, null on schema errors. |
| ``verdict_status`` | string\|null | ``ok``/``unsolved``/``invalid_input``/``timeout``/``budget_exhausted``. |
| ``category`` | string | Outcome category (``OK``, ``C1``, ``M2``, ``E1`` …). |
| ``fallback_used`` | bool | Whether the router fell back to another implementation. |
| ``time_ms`` | int | Primary solver duration reported by the orchestrator. |
| ``commit_sha`` | string | Git HEAD SHA (``+dirty`` suffix when applicable). |
| ``baseline_sha`` | string | Baseline commit SHA or ``"none"``. |
| ``baseline_id`` | string | ``dynamic:<digest>``, ``tag:<name>`` or ``"none"``. |
| ``solved_ref_digest`` | string | Artifact digest for the solved grid or ``"none"``. |
| ``time_ms_baseline`` | int\|null | Baseline latency when available. |
| ``perf_delta_ms`` | int\|null | Shadow execution latency delta in milliseconds. |
| ``perf_delta_pct`` | float\|null | Relative performance delta (optional, informational). |
| ``host_id`` | string | Short host identifier. |
| ``cpu_info`` | object | ``{"model": <cpu model>}``. |
| ``hw_fingerprint`` | string | First 32 hex chars of the hardware fingerprint. |
| ``warmup_runs`` | int\|null | Micro-benchmark warm-up runs (set for perf events). |
| ``measure_runs`` | int\|null | Micro-benchmark measurement runs. |
| ``details`` | object\|null | Additional information (e.g. mismatch summary or traceback). |
| ``event_id`` | string | 8 hex characters computed from the canonical JSON without ``event_id``. |

Опциональные поля (например, ``details``) опускаются, когда не нужны. Порядок
ключей не фиксируется, потребители обязаны поддерживать расширение схемы.

## Normalisation for comparisons

Для сравнения логов в `tools/ci.determinism_50x3` и `tools/ci.shadow_overhead_guard`
применяется нормализация:

- игнорируются поля: `timestamp`, `ts`, `host`, `host_id`, `pid`, `duration_ms`,
  `time_ms`, `perf_delta_ms`, `perf_delta_pct`, `hw_fingerprint`, `event_id`;
- записи сортируются по `op_seq` (если присутствует) либо по `u64_digest_trunc`;
- числовые поля форматируются с точностью до 3 знаков после запятой;
- строки нормализуются в Unicode NFC.

## Severity map

| Severity | Назначение | Пример |
| --- | --- | --- |
| CRITICAL | несовпадение решённой сетки или статус `invalid_input` | `category="C1"`, `verdict_status="invalid_input"` |
| MAJOR | расхождение кандидатов, тайм-ауты, auto-fallback | `category="M2"`, `fallback_used=true` |
| MINOR | допустимые расхождения производительности | `category="OK"`, `perf_delta_ms > 0` |

## Storage

- Логи пишутся в `logs/shadow/<run_id>-<suffix>.json` (каноническая JSON-сериализация).
- Для сравнений используется JCS (`json.dumps(..., sort_keys=True, separators)`),
  чтобы побайтно сверять события.
