# Project memory update protocol

Authority: [master workflow, section 3](../MASTER_AGENT_WORKFLOW.md#3-execute-and-preserve-reasoning). See [PROJECT_MEMORY/README.md](../PROJECT_MEMORY/README.md) for the resource map.

Route a fact to one primary record: task outcome and evidence through task commands; significant choices through decision/change records; experiment execution and interpretation through research commands; technical explanations, lessons and failures through `note` or maintained `PROJECT_MEMORY/notes/`; stopping context through session closure. Keep architecture and policies maintained, with a tracked rationale for significant changes.

A durable note names its task/source, observation date or event, scope, conclusion, evidence strength, uncertainty and affected next decision. Preserve negative results, rejected alternatives and failure triggers. Record resource identifiers and authorized retrieval instructions without credentials or confidential raw data.

Generated views are read-only inputs for contributors. Repair projection drift from the ledger using the master's audit procedure; do not edit the view to make evidence appear consistent. After changing governed maintained memory, refresh affected sessions and inspect the new context report. A content hash supports comparison of bytes; it is not proof of honest observation.
