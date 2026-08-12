# G File Studio v2.17.23 Validation

## Scope

This release intentionally changes only two areas:

1. Feeder merge -> optional main-bus processing.
2. ID Check & Repair -> visible progress while "Scan Current G" runs.

All other business logic is unchanged from v2.17.22.

## Main-bus processing

- Enabling main-bus processing now requires choosing **Single Bus** or **Double Bus**.
- Bus elements with XML `w < 10` are ignored by this feature.
- Single-bus mode checks only the highest valid horizontal `<Bus>` (minimum Y) in each feeder file.
- Double-bus mode checks the highest bus plus the nearest lower parallel bus whose length is approximately the same and whose horizontal projection overlaps substantially.
- Every selected main bus must have a non-empty `keyid`.
- In double-bus mode, the two selected buses must have two different keyids.
- The same keyid must occur in one continuous block in the user-defined feeder order; A/B/A is rejected.
- The same keyid is merged only if the selected buses land on the same horizontal Y after feeder alignment.
- Different keyids are never merged into one bus.
- facID/facName are not used as hard validation.
- Filename differences are warning/information only and do not disable the feature.

## Real-file checks

`JED-NTH-ABS-01.sln.pic.g`, double-bus mode:

- Selected upper bus: ID `30000846`, keyid `115404744746336274`, Y `30`.
- Selected second bus: ID `30000837`, keyid `115404744746336275`, Y `51`.
- Helper Bus elements with `w="6"` are ignored.

`JED-CTL-BWD-32.sln.pic(1).g`, single-bus mode:

- Selected bus: ID `30000313`.
- Its keyid is absent, therefore main-bus processing is correctly blocked.
- The `w="6"` helper Bus is ignored.

## ID scan progress

Clicking "扫描当前 G" now opens a visible progress dialog immediately. It displays the current filename and `current/total` progress and supports cancellation.

## Automated regression

`pytest -q`: **180 passed**.
