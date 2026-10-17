# Experiment protocol: <title>

- Experiment ID / owner / task:
- Question:
- Falsifiable hypothesis:
- Exploratory or confirmatory:
- Plan review and resource authorization, if required:

## Design

- Experimental unit and sampling:
- Baselines and controls:
- Treatment or changed variable:
- Metrics, units and expected direction:
- Exclusion/stopping criteria:
- Leakage, confounding and validity threats:

## Execution packet

```json
["python3", "experiment.py", "--config", "config.json"]
```

- Working directory:
- Configuration path and fingerprint:
- Dataset/manifests and access conditions:
- Code revision and scoped files:
- Runtime, dependencies and hardware/instruments:
- Seeds and how the program consumes them:
- Budget, timeout and output locations:

Register the packet with `experiment add`; use `experiment run` to record execution. Explain influential inputs not captured automatically by those selected files.

## Results and analysis

- Exit status and raw output paths:
- Observations and metric values:
- Repetitions, variability and statistical method:
- Comparison with hypothesis and baselines:
- Operational failure, invalid run, negative result or supported finding:
- Limitations and alternative explanations:

## Reproduction and next action

List the exact steps, missing/external resources and expected tolerance for a repeat. Preserve separate rerun records. Link the analysis, decision and follow-up task.
