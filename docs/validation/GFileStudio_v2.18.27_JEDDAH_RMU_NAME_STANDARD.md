# G File Studio v2.18.27 validation

## Jeddah RMU name visual standardization

This release keeps the shared RMU recognition/name-matching business logic unchanged and extends only the Jeddah batch site-specific presentation step.

For each RMU name already recognized by the existing RMU engine, Jeddah batch processing now:

- sets the selected RMU-name Text to white (`#FFFFFF`);
- sets `fs`, `p_FontWidth`, and `p_FontHeight` to `50`;
- keeps the Text box proportions when resizing;
- centers the RMU name horizontally against its own RMU frame;
- places the Text above the RMU top frame with a clear gap of exactly `10` drawing units between the Text bottom and the frame top.

The standalone RMU module keeps its existing behavior. The font-size/position rule is Jeddah-only.

## Validation

- Synthetic RMU: white name, font size 50, horizontal center delta = 0, top-frame clear gap = 10.
- `JED-CTL-BWD-28.sln.pic.g`: 11/11 recognized names matched; each checked sample had center delta = 0 and top gap = 10.
- Full test suite: 315 passed, 2 skipped.
