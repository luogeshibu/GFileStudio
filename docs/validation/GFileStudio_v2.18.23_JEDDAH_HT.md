# G File Studio v2.18.23 - Jeddah H.T Cleanup Validation

- New Jeddah-only rule removes direct Layer `<Text>` whose trimmed value equals `H.T` case-insensitively.
- No substring matching: `H.T-1` and `OTHER H.T` remain unchanged.
- Existing conditional SMR behavior from v2.18.22 remains unchanged and is covered by v2.18.21/v2.18.22 regression tests.
- Shared non-Jeddah business engines/processors were not modified.
