# G File Studio v2.18.24 - Jeddah SMART / Measurement Cleanup Validation

This release adds Jeddah-only orchestration rules without changing shared RMU, Basic, ID, Merge, Margin or Drawing Frame business algorithms.

## Duplicate SMART cleanup

- Every RMU returned by the existing distribution RMU identification engine is checked.
- If one RMU contains multiple `Text[ts=SMART]` labels, the first/original XML label is preserved exactly and later duplicates are removed.
- A single SMART label is never moved, restyled or rewritten.

Uploaded sample `JED-NTH-ABH-08.sln.pic(2).g`:

- recognized RMUs scanned: 8
- RMUs containing duplicate SMART: 3
- duplicate SMART Text elements removed: 3
- original SMART IDs preserved: `8000044`, `8000076`, `8000170`

## Adjacent measurement text cleanup

Exact pair:

- `2000.00`
- `UPDATED_MEASURMENT`

Both are deleted only when they are separate direct Layer Text elements on the same visual line and horizontally adjacent. The allowed horizontal gap is at most 10 G-coordinate units. Distant occurrences are retained.

Uploaded sample:

- adjacent pairs found: 1
- Text elements removed: 2
- sample geometry gap: 1
