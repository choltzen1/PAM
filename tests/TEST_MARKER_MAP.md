# Test Marker Map

This file tracks test marker coverage for safety and CI behavior.

## Marker behavior
- `integration`: may touch external services or real databases; excluded by default.
- `no_external_writes`: guaranteed to avoid external-system writes (mocked/in-memory paths).

## Integration-marked tests
- [tests/test_database_connectivity.py](tests/test_database_connectivity.py)
- [tests/test_api_endpoints.py](tests/test_api_endpoints.py) (`test_search_orbit_found` only)

## no_external_writes-marked tests
- [tests/test_admin_delete_promo.py](tests/test_admin_delete_promo.py)
- [tests/test_api_endpoints.py](tests/test_api_endpoints.py)
- [tests/test_clear_endpoints.py](tests/test_clear_endpoints.py)
- [tests/test_database_date_diagnostics.py](tests/test_database_date_diagnostics.py)
- [tests/test_field_mapping.py](tests/test_field_mapping.py)
- [tests/test_field_roundtrip.py](tests/test_field_roundtrip.py)
- [tests/test_generate_and_ingest.py](tests/test_generate_and_ingest.py)
- [tests/test_generate_next_promo_code.py](tests/test_generate_next_promo_code.py)
- [tests/test_generate_next_with_orbit.py](tests/test_generate_next_with_orbit.py)
- [tests/test_get_promo_codes.py](tests/test_get_promo_codes.py)
- [tests/test_sql_generation_e2e.py](tests/test_sql_generation_e2e.py)
- [tests/test_version_history_db.py](tests/test_version_history_db.py)

## Notes
- Default pytest config excludes integration tests (`-m "not integration"`).
- Integration tests require explicit opt-in (`--run-integration`).
- Test harness blocks DB writes and outbound HTTP in non-integration runs.
