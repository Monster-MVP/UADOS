# Data management and FAIR practice

FAIR practice means making data and metadata findable, accessible under stated conditions, interoperable and reusable. It does not require unrestricted publication of confidential or personal data.

## Input manifest

For each dataset or resource, preserve a manifest with:

- Stable identifier, source, version, acquisition date and license or permitted use.
- Local path or retrieval reference and content checksum when feasible.
- Schema, units, coordinate system, label definitions and missing-value conventions.
- Acquisition or preprocessing procedure and derived-data lineage.
- Access restrictions, responsible owner, retention conditions and restoration steps.
- Split construction, exclusions and leakage risks relevant to the experiment.

Register the relevant input files or manifests with the experiment. A manifest fingerprint establishes the recorded manifest's bytes; it cannot detect a changed underlying external dataset unless the manifest accurately records and the researcher verifies that dataset's checksum/version.

## Storage and lineage

Keep raw data immutable where feasible; write derived data to a separate location and record the transformation command and configuration. Preserve mappings between raw and derived observations. Document any manual curation or exclusions.

Choose durable formats and include a data dictionary. Use controlled access for sensitive content, and include only approved metadata in project memory. Keep encryption keys and credentials outside the project ledger, notes, logs and exports.

## Availability and sharing

Report “unavailable” when access failed, “missing” when a required file is absent, and “empty” only after successfully inspecting an empty source. Include recovery instructions. These states have different implications for a conclusion.

Before sharing a project or reproduction packet, inspect what it includes. External data, symlink targets and restricted resources may not travel with a portable project copy. Provide authorized retrieval instructions and verify the restored environment. Do not replace inaccessible data with invented observations.

## Retention and integrity

Define which inputs, raw outputs and intermediate artifacts must survive publication or handover, where they are backed up, and who can restore them. Record deliberate deletions and their impact on repeatability. Fingerprints detect drift relative to a record; they are not a substitute for retaining the files.
