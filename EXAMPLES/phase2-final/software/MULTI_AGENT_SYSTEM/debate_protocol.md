# Adversarial debate protocol

Lifecycle authority: [MASTER_AGENT_WORKFLOW.md](../MASTER_AGENT_WORKFLOW.md). A protocol-2 major task uses a plan debate before claim and a result debate over submitted implementation before completion. The CLI stores staged contributions and content fingerprints; participants supply substantive reasoning and actual independence.

## Round 1: independent analysis

Every assigned participant submits its own proposed solution, assumptions, risks and evidence. Inspect the underlying task, change request, plan or result, scoped files and relevant policies. Analyze independently before reading endorsements from others where the host supports that isolation. Explain a plausible alternative and the observation that could make it preferable.

## Round 2: adversarial challenge

Every participant challenges an analysis by another participant with a concrete failure mechanism and evidence. Ask why the proposal could fail, which assumptions are unsupported, what alternatives exist and which evidence is missing. Address compatibility, resource access, recovery and research validity where applicable.

Complete analysis before challenge, and challenge before voting. Round inputs, analyses and challenges are immutable; rework requires a new recorded debate rather than editing those submissions. During the vote round a contributor may append a reasoned replacement ballot; all earlier votes remain visible. Do not remove dissent by changing the participant set.

## Round 3: vote and consensus

Each participant votes on the selected analysis with reason and evidence. Use the CLI's explicit vote vocabulary; a request for changes is not an approval. Consensus records the selected analysis ID, approach, rejected alternatives, reasoning, remaining risks and preserved participant votes/challenges. See [consensus_protocol.md](consensus_protocol.md).

Bind the debate to the current task and relevant source/policy/evidence plus role assignments and declared capabilities. For result review, include the actual submitted work revision. If these inputs change, do not reuse stale approval. A participant who detects a blocker should request changes and name the missing evidence or recovery step.


## CLI contribution forms

Use issued IDs and actual supporting evidence. Every mutating form takes the contributor's currently acknowledged session. Repeat analysis assumption/risk/alternative/evidence flags as needed.

```sh
python -m uados --project . debate analysis DEBATE_ID --session SESSION_ID \
  --solution "Independent proposed approach" --assumption "Explicit assumption" \
  --risk "Concrete failure mode" --alternative "Reasoned alternative" \
  --evidence evidence/analysis.md
python -m uados --project . debate advance DEBATE_ID --session SESSION_ID
python -m uados --project . debate challenge DEBATE_ID --session SESSION_ID \
  --target OTHER_ANALYSIS_ID --failure "How this could fail" \
  --unsupported "Unsupported assumption" --alternative "Better choice under stated conditions" \
  --missing-evidence "What would resolve the challenge" --evidence evidence/challenge.md
python -m uados --project . debate advance DEBATE_ID --session SESSION_ID
python -m uados --project . debate vote DEBATE_ID --session SESSION_ID \
  --select SELECTED_ANALYSIS_ID --verdict approve --reason "Evidence-backed disposition of challenges" \
  --evidence evidence/review.md
python -m uados --project . debate consensus DEBATE_ID --session SESSION_ID \
  --select SELECTED_ANALYSIS_ID --reason "Selection and rejected alternatives" \
  --risk "Remaining risk and its disposition"
```

Advance succeeds only when all participants have completed the current contribution round. Other participants must submit their own records; this sample shows forms for one contributor, not a one-agent debate. Use `--verdict request_changes` for an unresolved objection. Consensus requires all current votes to approve the same actual analysis and the independent quorum; prior objections remain in history. Consensus also generates bound independent approval records from eligible reviewer ballots.
