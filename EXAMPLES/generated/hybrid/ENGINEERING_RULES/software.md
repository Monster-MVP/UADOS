# Software engineering policy

## Design and implementation

Give each component a clear responsibility and explicit interfaces. Prefer a simple design that meets current requirements and leaves known extension points. Record major architectural choices with a problem, alternatives, evidence, rationale and limitations.

Before changing a public interface or persistent format, identify callers, compatibility requirements, migration and rollback. Treat silent data loss, incompatible contracts and altered security boundaries as major risk. Put behavioral and acceptance criteria in the task rather than leaving them only in implementation comments.

Keep edits within agreed ownership and scope. Separate unrelated changes when doing so improves review and recovery. Document important invariants, failure paths and non-obvious reasoning near the implementation or in memory.

## Dependencies and environment

Document supported runtimes and installation commands. Prefer existing dependencies when they serve the purpose. Before adding one, examine its license, maintenance, attack surface, transitive cost and reproducibility needs. Record version selection and meaningful upgrade changes. A dependency name without a resolvable version or lock strategy is inadequate for a claimed reproducible environment.

Do not introduce hidden network, shell, account or service requirements. If a feature needs them, state them in the plan and validate failure behavior when unavailable.

## Reliability and performance

Make errors actionable and preserve enough context to diagnose them without secrets. Distinguish retryable failure, invalid input and corrupted state. Bound long-running work with cancellation or timeouts when the interface permits them. Avoid reporting success before outputs are actually durable.

Measure performance against an explicit workload and budget. Record hardware, environment, repetitions and variability. Do not claim a universal speedup from one favorable run. Address correctness and operability alongside throughput.

## Delivery

Before release, verify acceptance criteria, relevant automated checks, supported environments, documentation and migration/recovery. Record the tested revision and evidence. CI, packaging, protected branches and deployments are optional integrations that must be configured and verified by the team; UADOS does not deploy them automatically.

See `VERSION_CONTROL/README.md` for ownership, review and release evidence practices.
