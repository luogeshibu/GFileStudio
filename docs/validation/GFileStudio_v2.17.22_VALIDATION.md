# G File Studio v2.17.22 Validation

## Scope

Only the optional feeder-merge main-bus/keyid logic was changed. Other modules were intentionally left unchanged.

## Automated regression

- `pytest -q`
- Result: **173 passed**

## Uploaded G-file checks

### JED-CTL-BWD-32.sln.pic(1).g

- Real horizontal Bus detected: `30000313`
- `keyid`: missing/empty
- Expected behavior: **main-bus merge is blocked**

### JED-NTH-ABS-01.sln.pic.g

- Double-bus layout detected
- Bus `30000837`: keyid `115404744746336275`, Y=51
- Bus `30000846`: keyid `115404744746336274`, Y=30
- Expected behavior: **preflight accepted**; the two keyids remain independent bus groups and can never be collapsed into one bus.

## Rules verified

- facID/facName mismatch does not hard-block the option.
- Missing/blank keyid on any real horizontal Bus hard-blocks the option.
- A file may contain two distinct bus keyids.
- Different keyids never merge even at the same Y.
- Same keyid must be contiguous across feeder order.
- Same keyid must be on the same final horizontal line before merge.
