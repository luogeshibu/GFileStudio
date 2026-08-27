# G File Studio v2.18.44 Validation

## Baseline
- Based directly on v2.18.43.
- Keeps v2.18.43 batch OLD/NEW pairing and zenon-centered 90/270-degree rectangular-symbol rotation.
- Keeps the v2.18.41 orthogonal-wire safety guard.

## Generic symbol-standard customization
- The six existing SMART/NORMAL RMU roles remain protected built-in rules.
- Users may add/delete additional custom device-symbol standards.
- Custom rows persist scope, role, XML element tag, standard devref and the selected business-element matcher.
- Supported matchers: exact old/current devref, XML element type, exact p_NameString, exact key_name.
- Built-in rules are applied first; custom rules cannot double-modify an already handled built-in RMU device.
- Ambiguous custom-rule matches are skipped with warnings.

## G element/property catalog
- Standard main-G scanning records XML tag, devref body ID, w/h, rotations, p_NameString/key_name examples and occurrence counts.
- Raw icon-definition G scanning records body XML type/ID, w/h, AlignCenter, pin coordinates and pin IDs.
- GBK/GB18030 raw icon definitions are parsed through the existing safe decoder even when ElementTree cannot parse them directly.
- Raw icon definitions generate rotation-specific geometry templates for 0/90/180/270 degrees.

## Generic anchor-preserving geometry
- Geometry-template learning now supports arbitrary devref elements with verifiable ConnectLine anchors, not only the three built-in RMU device tags.
- Custom standards reuse the same anchor-preserving replacement engine.
- If no safe geometry template is available, replacement falls back to devref-only and does not move wiring.
- Geometry-only adjustments are now written even when the target devref string is unchanged.

## Supplied-file verification
- `JED-NTH-ABH-12.sln.pic(4).g` plus the supplied raw symbol-definition G files were scanned successfully.
- Main-G catalog found the existing RMU devrefs and their element properties.
- Raw symbol G metadata including AlignCenter/pins was parsed successfully despite multibyte XML declarations.
- No regression was introduced into the previous RMU 30907 grounding-switch and horizontal/vertical connection-line fixes.

## Automated validation
- Python compile checks: PASS.
- Full pytest suite: `364 passed, 2 skipped`.
