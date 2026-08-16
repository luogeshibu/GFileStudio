# G File Studio v2.17.43 Validation

## Scope

This release only changes the output naming behavior of the 图形边距调整 module.

- Removed the 输出标记 field from the margin-adjustment page.
- Margin-adjustment outputs now keep the exact source filename.
- If the output directory already contains same-name files, the UI offers overwrite / skip / cancel.
- Output is blocked when the target path is the original source file path.
- Margin geometry, frame handling, ID enforcement, and all other modules are unchanged.

## Verification

- `python -m pytest -q`: **229 passed**
- `python -m compileall -q g_file_studio app.py`: passed
- Added regression coverage for source-filename output and same-path protection.
