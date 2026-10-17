# Independent T000008 result review

Reviewer: Phase3-Validation-Reviewer / S000012; 2026-10-13 Asia/Shanghai. Separate model contributor, no implementation or maintained test authorship. Final source hashes are recorded below.

## Independent validation

I independently ran `PYTHONPATH=src python3 -m unittest discover -s tests -v`: **103 tests passed in 46.628 seconds**, captured in `manifest-final-independent-v1.txt`. I independently ran the focused manifest suite: **12 tests passed in 0.474 seconds**, captured in `manifest-final-focused-v1.txt`. The final focused tests include nested/shared binary DAG, mixed-root closure, injected cycle guard explicitly distinguished from cryptographic cycle construction, generated/alias paths, malformed stored metadata, bounds, late invalid dependency with no published snapshots, leaf drift, plan-gate audit/export/rebuild and historical child-snapshot corruption. Existing legacy/trust regressions are included in the 103 test run. No hosted/provider/remote claims are made.

The maintained source and test files were read at the final review. The implementation now enforces reserved generated/session-report/change-request exclusions, canonical root paths, strict boolean/version/path metadata, deterministic dependency order, graph bounds and prepublication graph validation. `walk_evidence` traverses nested dependency records; `check_evidence`, audit, export and rebuild use archived closure metadata. Existing ordinary JSON remains opaque.

## Strongest challenge and disposition

The principal failure mode was a root record that appeared valid while a transitive child was omitted, replaced by a newer live manifest or published only after a later invalid node. The final tests and hooks address this through immutable archived manifest traversal, exact stored closure comparison, shared-node deduplication, current live leaf checks, prepublication validation and no event/record for late-invalid graphs. Export/rebuild retains dependency snapshots; missing historical child snapshots fail audit. Cycle tests use parser injection and explicitly make no SHA256 fixed-point claim.

The implementation remains bounded: manifests/files/aggregate graph reads have limits; the lock coordinates CLI writers but not arbitrary OS edits; content hashes provide local consistency and do not authenticate source authorship or remote freshness. Orphan snapshots after a later commit failure are allowed as documented. Matching newer runtime is required for optional metadata; no downgrade compatibility is claimed.

One initial harness invocation without `PYTHONPATH` failed to import `uados`; this was a test harness environment error, preserved as such. The corrected independent runs above use the source runtime explicitly and pass. No implementation or test changes were made by this reviewer.

Result approval is supportable for the current submitted revision once the required protocol-2 result debate records these evidence paths and keeps the limits visible. This does not approve production-scale storage, remote authorization or universal evidence authenticity.

{
  "final_source_hashes": {
    "src/uados/manifests.py": "f66a8d3d3ecc82d545727c321a5ca4ae1362add251bea61415910a8607f9bce2",
    "src/uados/storage.py": "a818e1a5f6f73ccaed4888e059f0ce09156cacd7ab14b894d157ef24232a5d6d",
    "src/uados/project.py": "dc9e0e6357c4421853b5a4542d77871512e0d855412fca666db838cf967db1c4",
    "src/uados/protocol.py": "127796155e42b2e21d48b73f1490ed0aa4cdc044815c6e28e126bd20f1989955",
    "tests/test_manifests.py": "036ad23411fd08e7293f48d38e0f03135f48d6ad670b5f146239adf1a9773703",
    "docs/manifests.md": "430773b7dc3c1dcca6f0c19822db2106d2c6587a4a842c888bc2bc83e67b411c"
  },
  "reviewer": "Phase3-Validation-Reviewer",
  "session": "S000012",
  "test_outputs": [
    "AUDIT/phase3-validation-review/manifest-final-independent-v1.txt",
    "AUDIT/phase3-validation-review/manifest-final-focused-v1.txt"
  ],
  "tests": 103,
  "focused_tests": 12
}
