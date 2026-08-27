# G File Studio v2.18.25 validation

- Jeddah Batch step 1 now reuses Basic Processing full graphic ungrouping before abnormal-small-element deletion.
- `remove_all_graphic_merges(..., lower_rmu_rects=True)` is called without modifying the shared engine implementation.
- Synthetic regression confirms all `<Merge>` elements are removed while non-Merge attributes remain unchanged.
- Real sample `JED-CTL-BWD-28.sln.pic.g`: 11 Merge elements removed; 0 remain.
- Full test suite: 311 passed, 2 skipped.
