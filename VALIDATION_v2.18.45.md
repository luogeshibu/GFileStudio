# G File Studio v2.18.45 Validation

## Manual OLD → NEW pairing UX

- Universal Symbol Upgrade no longer implies that OLD and NEW filenames must match.
- Added an explicit `手动配对…` workflow. The user may select an OLD row (or no row) and choose any uploaded OLD and NEW symbol from two combo boxes.
- The dialog previews parsed XML element type, body ID, w/h, AlignCenter, and pins for both files before confirmation.
- Manual pairing may use completely different filenames and body IDs. XML element type and electrical pin topology are still validated for safety.
- Manual mappings are marked `手动确认` and take precedence over automatic suggestions.
- One NEW symbol may be manually used by more than one legacy OLD symbol, supporting legacy aliases converging on one current standard symbol.
- Unpairing/removing an OLD mapping correctly returns a NEW symbol to the unmatched pool only when no other mapping still uses it.
- Existing exact-name and unique `XML type + body ID` auto-pairing behavior is retained.

## Regression

- Retains v2.18.43 centered rotation / connection-anchor fixes.
- Retains v2.18.44 generic symbol standard template enhancements.
