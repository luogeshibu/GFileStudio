# G File Studio v2.17.20 Validation

## Scope

This release intentionally changes only two items:

1. Replaces the built-in SLD drawing frame template with the user-provided `SLD-Drawing-Frame-Template.sln.pic(2).g`, stored internally as `resources/templates/SLD-Drawing-Frame-Template.sln.pic.g`.
2. Removes Alias-related explanatory wording from the ID Check & Repair page/help text. ID rule behavior is unchanged.

## Template verification

- Source SHA256: `d0e41937528886c8f8514b943733ef1f7050562fa0022b582025a0f461157a01`
- Embedded SHA256: `d0e41937528886c8f8514b943733ef1f7050562fa0022b582025a0f461157a01`
- Result: exact byte-for-byte replacement confirmed.

## Automated tests

- Command: `python -m pytest -q`
- Result: `162 passed in 11.54s`
