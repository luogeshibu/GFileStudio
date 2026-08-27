# G File Studio v2.18.42 Validation

## Baseline
- Based directly on v2.18.41.
- Keeps the v2.18.41 rotated-icon orthogonal ConnectLine preservation fix.

## Symbol Standard Check
- Sidebar module renamed from `现场 RMU 图元 Profile` to `图元标准检查`.
- Existing saved SiteSmartProfile data and ACTIVE/ARCHIVED version workflow remain compatible.
- New read-only `只检查标准` action uses the same RMU/device/geometry engine as upgrade but never writes source G files and does not create a `final` output directory.
- Existing upgrade workflow is retained as `检查并升级`.
- Read-only report: `symbol-standard-check.csv/html`.
- Upgrade report: `symbol-standard-upgrade.csv/html`.
- Standard scope remains SMART/NORMAL RMU LBS, Circuit Breaker, ZhaiWaiJieDiDaoZha and learned geometry; SMR remains site-specific and is skipped by the generic standard engine.
- Jeddah batch continues to consume the selected ACTIVE standard; only user-facing naming/help text changed.

## Validation
- `python -m compileall -q g_file_studio app.py`: PASS
- `pytest -q`: `355 passed, 2 skipped`
- Added regression tests proving check-only mode leaves source bytes unchanged and creates no `final` folder.
