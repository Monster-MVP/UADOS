# Reproducible experiments

## Protocol before execution

Use `TEMPLATES/experiment.md` to state question, hypothesis, baseline, controls, measurements, units, sample design and analysis. Distinguish exploratory analysis from a confirmatory test. Define exclusion and stopping criteria before examining outcomes when those criteria affect inference.

Record the command as a JSON array of arguments, not an informal shell fragment. For example:

```sh
python -m uados --project . experiment add --session SESSION_ID \
  --title "Evaluate the prespecified hypothesis" \
  --hypothesis "A concrete, measurable prediction" \
  --command-json '["python3", "experiment.py", "--config", "config.json"]' \
  --config config.json --dataset data/manifest.json --seed 7 \
  --scope experiment.py --cwd .
```

Repeat dataset and scope arguments when appropriate. Check the actual CLI help for required fields. Recording a seed as metadata does not ensure the invoked program uses it: pass it in configuration or arguments and verify the relevant libraries honor it.

Run the registered experiment:

```sh
python -m uados --project . experiment run EXPERIMENT_ID \
  --session SESSION_ID --timeout 300
```

The executable runs with the contributor's privileges, without an execution sandbox. Inspect the program and its command before running.

Run completion changes recorded context. Refresh the session, inspect the new report and acknowledge its hash before adding an interpretation or further tracked work. Record the scientific conclusion separately:

```sh
python -m uados --project . experiment conclude EXPERIMENT_ID \
  --session SESSION_ID \
  --conclusion "Observed result, uncertainty and implications for the hypothesis" \
  --evidence evidence/analysis.md
```

## Reproduction packet

Keep enough material to repeat and interpret the run:

- Exact command, working directory, configuration and versioned input manifests.
- Code revision and relevant file fingerprints.
- Runtime, dependency versions, operating system and instrument or hardware details.
- Data provenance, preprocessing, splits and access conditions.
- Seed handling, nondeterministic operations and known sources of variation.
- Exit status, raw outputs, metrics and the analysis procedure.
- Budget, duration, timeout and incomplete-run handling.

The CLI records selected inputs; the researcher must identify other influential resources. An external service, changing dataset or unavailable instrument may prevent exact repetition. Label these limits and provide a feasible replication procedure instead of asserting full reproducibility.

## Analysis and uncertainty

Use metrics that answer the hypothesis, include baselines, and report units. Where appropriate, report repetitions, variability, confidence intervals, effect sizes and the analysis assumptions. Avoid interpreting one favorable seed as a general conclusion. Track multiple comparisons, model selection and exploratory choices that could bias the claim.

Distinguish operational failure from a valid negative result. A timeout, missing input or numerical error usually makes the run incomplete or invalid. A valid result contradicting the hypothesis is useful evidence and must remain in memory.

## Replication and drift

Before rerunning, compare code, config, data and environment with the original packet. Explain differences rather than silently overwriting old outputs. Retain separate records for reruns. If inputs drift, the new run answers a potentially different question; revise the conclusion and review scope accordingly.

If a launcher disappeared while a run remains recorded as `running`, inspect whether the process is still alive and preserve partial outputs. Once the execution has stopped, use `experiment resolve EXPERIMENT_ID --session SESSION_ID --reason ...` to record interrupted-run recovery before retrying. This command records your recovery judgment; it does not discover or terminate an unknown surviving process automatically.
