# Validation - 2.18.203

- `python -m compileall -q g_file_studio`
- `pytest -q tests/test_v218203_local_catalog_no_flash.py tests/test_v218201_central_connection_and_id_examples.py tests/test_v218202_classified_device_split.py`
- Static review confirms the automatic AppData catalog restore path contains no `QMessageBox` or `QProgressDialog` calls.

## v2.18.205 responsive symbol inventory

- `python -m compileall -q g_file_studio`: passed before packaging.
- `pytest -q tests/test_v218205_symbol_inventory_responsive.py`: 4 passed.
- `pytest -q tests/test_v218205_symbol_inventory_responsive.py tests/test_v218201_central_connection_and_id_examples.py tests/test_v218202_classified_device_split.py tests/test_v218203_local_catalog_no_flash.py -k 'not version'`: 11 passed, 2 deselected stale version assertions.
- The new table fitter measures only the seven visible symbol-inventory columns once after row hydration; viewport resize/show reuses cached natural widths and does not call Qt content auto-sizing.
