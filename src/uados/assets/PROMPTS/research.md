# Research prompt

Investigate question `<QUESTION>` under the project's UADOS research workflow. Establish and acknowledge current context before designing or running substantive work.

Read relevant literature records, decisions, hypotheses, dataset manifests and experiment results. Describe source coverage and access limits; do not invent references or interpret an unavailable source as empty. Define a falsifiable hypothesis, baseline, controls, outcome metrics, units and threats to validity. Review costly or consequential work independently before execution.

Create an execution packet with command JSON argument array, working directory, configuration, dataset/manifests, code scope, seed handling, runtime dependencies and resource limits. Register it using `experiment add`; ensure the program actually applies recorded seeds. Inspect executable inputs because `experiment run` is not a sandbox.

Run with a suitable timeout and preserve raw output. Refresh and acknowledge context after the recorded run. Interpret observations using a maintained analysis artifact and `experiment conclude`; distinguish process success from a supported scientific conclusion, valid negative result, invalid run or operational failure.

Report repetitions, variability and uncertainty appropriate to the claim. Preserve alternative explanations, failures and negative findings. Keep restricted data under authorized access; FAIR metadata does not authorize public sharing. Close with evidence and a concrete next experiment or decision.
