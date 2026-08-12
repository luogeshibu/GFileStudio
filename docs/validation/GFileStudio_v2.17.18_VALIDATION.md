# G File Studio v2.17.18 Validation

## Automated tests

- Command: `pytest -q`
- Result: **162 passed**

## ID template scan report

- `changed_formats` now keeps every unique invalid complete XML ID for the element type instead of truncating to 8 samples.
- The scan dialog aggregates invalid IDs by XML element type and explicitly labels them as complete IDs, not prefixes.

## Basic processing: delete element attribute

- Added an independent rule card **删除元素属性** between attribute replacement and whole-element deletion.
- Matching scope remains direct children of the root `Layer`.
- It deletes the selected attribute key from every matching element tag, without deleting the element.

## RMU name/type recognition

Reference implementation reviewed: user-supplied `Distribution_Model_Manager_v3.1.1`.

Current G File Studio rules:

1. A cabinet must contain `BusDis`, `CBreakerDis`, and `ZhaiWaiJieDiDaoZha` inside the `rect`.
2. Cabinet names are searched only in user-selected directions.
3. `Text` and `DText` are both eligible name objects.
4. Each candidate Text/DText is owned by the nearest eligible RMU in that selected direction.
5. One owned candidate: use directly regardless of color.
6. Multiple owned candidates: choose nearest green candidate if any; otherwise choose nearest candidate.
7. No selected-direction candidate: keep the name unresolved. No other direction and no `BusDis.key_name` fallback is used.
8. Cabinet type remains Y/Q text first, CBreakerDis device fallback only when the corresponding label class is absent.

## Real-file regression

Using `/mnt/data/JED-NTH-ABH.sln.pic.g`:

- RMU cabinets: **340**
- Type recognition: **340 / 340**
- With **top only** selected: cabinet names **337 / 340**. The three names at rect IDs `2000333`, `2000362`, `2000429` are not in the selected top direction, so they intentionally remain unresolved.
- With **top + bottom** selected: cabinet names **340 / 340**.
- `2000238 -> 30839` is still recognized from the top direction even though its text box slightly overlaps the frame edge.

