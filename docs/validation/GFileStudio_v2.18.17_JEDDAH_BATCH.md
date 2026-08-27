# G File Studio v2.18.17 — Jeddah Feeder Batch Processing Validation

## Scope

This release adds a new **Jeddah Feeder Batch Processing** module. Existing module business algorithms are not modified. The new module is an orchestration layer that processes each single-feeder G file independently; it does not merge feeder drawings.

## Fixed Jeddah workflow

1. Remove abnormal small ConnectLine / FeedLine / Bus / BusDis elements using the existing small-element engine and configured threshold.
2. Set the Text corresponding to an already-recognized RMU name to white (#FFFFFF) using Jeddah-only presentation/output logic; existing RMU recognition remains unchanged.
3. Reuse the existing RMU enhancement engine to set SMART and SMR RMU frames to red (#FF0000).
4. Reuse the existing RMU enhancement engine to remove Bus-containing RMU rectangles and move the corresponding title above the bus.
5. Reuse the existing feeder-title engine to move feeder names above buses.
6. Reuse the existing ID processor and globally confirmed ID templates to perform final ID check and repair.

## Isolation

Jeddah parameters are stored under the `jeddah_batch/*` settings namespace and do not overwrite existing RMU, Basic Processing, Small Element, or ID module settings.

Compared with v2.18.16, existing runtime source changes are limited to version/registration/i18n/help display files:

- `g_file_studio/__init__.py`
- `g_file_studio/i18n.py`
- `g_file_studio/ui/main_window.py`
- `g_file_studio/ui/help_content.py`
- `pyproject.toml`

All Jeddah processing implementation is added in new files under `g_file_studio/jeddah/` and `g_file_studio/ui/pages/jeddah_batch_page.py`.

The Golden Baseline lock test for the protected original business code passes unchanged.

## Automated validation

- Full regression suite: **291 passed, 2 skipped**.
- Golden Baseline lock: passed.

## Real-file verification

Verified against `JED-CTL-BABJ.sln.pic(1).g` with threshold 10 and RMU name exclusions `NOP, DAS/OK, SFI`:

- Final G files: 1 / 1
- Abnormal small elements removed: 16
- Recognized RMU names: 60
- RMU name Texts matched: 60
- RMU name Texts changed to white: 60
- SMART RMUs matched: 17
- Feeder titles moved above buses: 10
- IDs repaired: 7
- Unconfigured ID element types detected: 3; these are reported as warnings and are not assigned IDs without a confirmed global template.

