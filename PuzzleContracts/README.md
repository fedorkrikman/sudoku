# Puzzle Contracts Registry

This directory contains the locally managed JSON Schemas and example artifacts that
describe the Sudoku pipeline. All schemas are versioned using semantic versioning
and referenced through offline URNs (for example `urn:puzzle:schemas/spec:1.0.0`).

## Layout

- `schemas/` – canonical JSON Schemas for each artifact type.
- `catalog.json` – lookup table that maps artifact types to the active schema
  version and local schema path.
- `fixtures/valid` – minimal canonical artifacts that satisfy the schemas.
- `fixtures/invalid` – intentionally malformed artifacts used for negative tests.
- `MIGRATIONS.md` – placeholder for documenting future schema migrations.

All artifacts include the shared envelope defined in `_common/envelope-1.0.0.json`.
When updating schemas remember to synchronise `catalog.json` and document changes
in `MIGRATIONS.md`.
