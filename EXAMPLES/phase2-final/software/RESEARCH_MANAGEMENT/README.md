# Research management

Research uses the common UADOS lifecycle with additional obligations for hypotheses, data, reproducibility and claims. Hybrid projects apply these rules to research work and software rules to the systems that produce results.

- `reproducibility.md`: protocol, commands, inputs, environment and analysis.
- `data_management.md`: data lineage, FAIR practice, access and preservation.
- `publication.md`: literature, novelty, limitations and evidence-backed claims.
- `experiments.md`: generated experiment and execution records; use the CLI to update it.

Before a run, define a question and a falsifiable hypothesis. Explain the experimental unit, baseline, controls, outcome metrics and observations that would reject the hypothesis. Plan costly or consequential experiments as major tasks with independent review.

The experiment CLI records a JSON argument vector, configuration, dataset inputs, seed, scope and working directory and runs that command with a timeout. It supplies local execution records and fingerprints. It does not infer correct experimental design, capture every dependency or make an undocumented dataset reproducible.

Keep data manifests, detailed protocols, literature records and analyses as maintained artifacts linked from tasks, notes and decisions. Record failures, valid negative results and ambiguous results with equal care. A process exit code and a scientific conclusion answer different questions.
