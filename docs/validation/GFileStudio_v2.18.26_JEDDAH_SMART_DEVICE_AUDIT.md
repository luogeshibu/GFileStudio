# G File Studio v2.18.26 validation

## Jeddah SMART device consistency

This release keeps the shared RMU / Basic / ID / Merge / Margin / Frame business logic unchanged and extends only the Jeddah batch orchestration/site-specific adapter.

### Function 1: existing SMART RMU device audit
For every recognized RMU whose own frame already contains `SMART`, check `CBreakerDis` devices inside that RMU and replace only these exact devrefs when needed:

- `#Load_Breaker_Switch_NON-SMART.zwk.icn.g:Load_Breaker_Switch_NON-SMART`
  -> `#Load_Breaker_Switch_SMART.zwk.icn.g:Load_Breaker_Switch_SMART`
- `#Circuit_Breaker_NO-SMART.zwk.icn.g:Circuit_Breaker_NO-SMART`
  -> `#Circuit_Breaker_SMART.zwk.icn.g:Circuit_Breaker_SMART`

No ID, keyid, key_name, node_area, coordinates, rotation, or other business attributes are changed.

### Function 2: post-SMR SMART device audit
After Jeddah SMR handling:
- existing SMART in the cabinet: keep the original SMART label, remove the external SMR, frame red;
- no SMART in the cabinet: create top-centered SMART at font size 20, frame red.

Then run the same SMART device audit again so newly converted cabinets also receive correct LBS / Circuit Breaker SMART devrefs.

### Validation
- Synthetic existing-SMART RMU: Y1/Y2/Y3 + Q1 corrected = 4.
- Idempotence: second audit changes = 0.
- `JED-CTL-BWD-28.sln.pic.g`: pre-existing SMART RMUs = 3, pre-check changes = 0; SMR converted = 1; post-check changes = 4.
- Full test suite: 313 passed, 2 skipped.
