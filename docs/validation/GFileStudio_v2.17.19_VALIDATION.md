# G File Studio v2.17.19 Validation

## Change scope

- Only changes the feeder merge UI behavior for the “合并主母线为一条” checkbox.
- When the checkbox is changed from unchecked to checked, the application immediately shows a warning that all feeder G files in the merge list must come from the same station.
- Unchecking the option does not show a warning.
- Bus merge, ID, layout, frame, RMU and other processing logic are unchanged.

## Warning text

请确认当前加入合并列表的所有馈线 G 文件必须来自同一厂站。

“合并主母线为一条”会把这些馈线已对齐的顶部主母线合并为同一条 Bus。如果文件来自不同厂站，请取消勾选并重新选择文件。

## Regression test

Command: `QT_QPA_PLATFORM=offscreen pytest -q`

Result: **162 passed**.
