"""Phase 4 Benchmarks: Software Relay, Research Intelligence, and Paper Rebuttal."""

import json
import os
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path
from typing import Any, Dict, List

from uados import governance as gov
from uados import orchestration as orch
from uados.project import Project
from uados.research import (
    add_experiment,
    conclude_experiment,
    run_experiment,
)
from uados.resilience import (
    create_review_bundle,
    verify_review_bundle,
)
from uados.storage import safe_path

GLOBAL_BENCHMARK_METRICS: Dict[str, Any] = {
    "benchmark1": {},
    "benchmark2": {},
    "benchmark3": {},
    "timing_records": [],
}


class Phase4Benchmarks(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.benchmark_root = Path(self.tmp.name).resolve()

    def _measure(self, label: str, func: Any, *args: Any, **kwargs: Any) -> Any:
        start = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed = time.perf_counter() - start
        GLOBAL_BENCHMARK_METRICS["timing_records"].append({"operation": label, "elapsed_seconds": round(elapsed, 4)})
        self.assertLess(elapsed, 5.0, f"Operation {label} exceeded 5.0s threshold ({elapsed:.3f}s)")
        return result

    def test_benchmark_1_software_engineering_relay(self) -> None:
        """Benchmark 1: 30-day cross-agent software relay with boundary failure & review handshake."""
        ws = self.benchmark_root / "bm1_project"
        project = self._measure("B1_Project_Init", Project.initialize, ws, "UADOS-Relay-Demo", "Multi-Agent Relay Demo", protocol_version=2)

        # Agent A: Architecture & Implementation
        session_a = self._measure("B1_AgentA_Start", project.start_session, "Agent-A-Architect", "other")
        self._measure("B1_AgentA_Ack", project.acknowledge, session_a["session"], session_a["report_hash"])

        # Create source and evidence files
        src_path = ws / "src" / "resilient_mod.py"
        src_path.parent.mkdir(parents=True, exist_ok=True)
        src_path.write_text("def parse_retry_after(header: str) -> float:\n    # Initial implementation\n    return float(header)\n", encoding="utf-8")

        plan_ev = ws / "evidence" / "plan.md"
        plan_ev.parent.mkdir(parents=True, exist_ok=True)
        plan_ev.write_text("# Implementation Plan\nHandle exponential backoff and retry-after header.\n", encoding="utf-8")

        task_res = self._measure(
            "B1_Task_Add",
            project.add_task,
            session_a["session"],
            "Implement Resilient Backoff Module",
            "Must handle HTTP 429 and parse retry-after header safely.",
            risk="routine",
            scopes=["src/resilient_mod.py"],
        )
        task_id = task_res["task"]

        self._measure(
            "B1_Task_Plan",
            gov.plan_task,
            project,
            session_a["session"],
            task_id,
            "1. Implement parse_retry_after; 2. Add boundary validation.",
            "1. Verify float conversion; 2. Assert malformed header raises ValueError.",
            ["evidence/plan.md"],
        )

        # Agent A records deliberate boundary failure and remediation
        test_ev = ws / "evidence" / "boundary_test.md"
        test_ev.write_text("Failed on empty header: ValueError. Remediated with safe parsing.", encoding="utf-8")
        src_path.write_text("def parse_retry_after(header: str) -> float:\n    if not header or not header.strip():\n        return 0.0\n    return float(header.strip())\n", encoding="utf-8")

        self._measure("B1_Task_Claim", project.claim_task, session_a["session"], task_id)
        self._measure(
            "B1_Task_Record",
            project.record_task,
            session_a["session"],
            task_id,
            "Remediated empty header boundary failure; verified safe float parsing.",
            ["evidence/boundary_test.md"],
        )

        # Agent A exports Review Bundle before handing over
        bundle_rel = "AUDIT/review-bundles/T_RELAY_001-bundle.json"
        bundle_meta = self._measure(
            "B1_Bundle_Create",
            create_review_bundle,
            project,
            session_a["session"],
            task_id,
            bundle_rel,
            reason="upstream_rate_limit_429_cross_session_review",
            test_command="python3 -m unittest",
        )
        self.assertEqual(bundle_meta["task_id"], task_id)

        # Agent A safely closes session with handover
        close_a = self._measure(
            "B1_AgentA_Close",
            project.close_session,
            session_a["session"],
            "Completed implementation of parse_retry_after with boundary test.",
            ["AUDIT/review-bundles/T_RELAY_001-bundle.json"],
        )
        self.assertTrue(close_a["closed"])

        # Shift 2: Developer A2 resumes from handover in zero memory sharing
        project_dev = Project(ws)
        session_a2 = self._measure("B1_Dev2_Start", project_dev.start_session, "Agent-A-Developer", "other")
        self._measure("B1_Dev2_Ack", project_dev.acknowledge, session_a2["session"], session_a2["report_hash"])
        self._measure("B1_Dev2_Claim", project_dev.claim_task, session_a2["session"], task_id)

        # Agent B: Independent Reviewer in zero-context instance
        # Reads project fresh from disk
        project_b = Project(ws)
        session_b = self._measure("B1_AgentB_Start", project_b.start_session, "Agent-B-Reviewer", "other")
        self._measure("B1_AgentB_Ack", project_b.acknowledge, session_b["session"], session_b["report_hash"])

        # Verify Review Bundle
        bundle_v = self._measure("B1_Bundle_Verify", verify_review_bundle, project_b, bundle_rel)
        self.assertTrue(bundle_v["verified"])

        # Stage 1: Independent Analysis & Stage 2 Challenge
        rev_ev = ws / "evidence" / "reviewer_analysis.md"
        rev_ev.write_text("Verified boundary handling and AST of parse_retry_after.", encoding="utf-8")

        # Independent review submission
        self._measure(
            "B1_Task_Review",
            project_b.review_task,
            session_b["session"],
            task_id,
            "result",
            "approve",
            "Verified edge case handling and file hash integrity.",
            ["evidence/reviewer_analysis.md"],
        )

        # Developer A2 refreshes context after review and completes task
        ref_a2 = self._measure("B1_Dev2_Refresh", project_dev.refresh_session, session_a2["session"])
        self._measure("B1_Dev2_ReAck", project_dev.acknowledge, session_a2["session"], ref_a2["report_hash"])
        self._measure("B1_Task_Complete", project_dev.complete_task, session_a2["session"], task_id)

        audit_res = self._measure("B1_Project_Audit", project_b.audit)
        self.assertTrue(audit_res["ok"])
        self.assertEqual(audit_res["projection_drift"], [])

        GLOBAL_BENCHMARK_METRICS["benchmark1"] = {
            "status": "PASSED",
            "task_id": task_id,
            "bundle_id": bundle_v["bundle_id"],
            "audit_ok": audit_res["ok"],
        }
        b1_dir = Path(__file__).resolve().parents[1] / "AUDIT" / "benchmarks" / "benchmark1-software-relay"
        b1_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ws / "AUDIT" / "review-bundles" / "T_RELAY_001-bundle.json", b1_dir / "T_RELAY_001-bundle.json")
        shutil.copy2(ws / "SESSION_HANDOVER.md", b1_dir / "SESSION_HANDOVER.md")
        shutil.copy2(src_path, b1_dir / "resilient_mod.py")

    def test_benchmark_2_research_intelligence_falsification(self) -> None:
        """Benchmark 2: Full scientific research lifecycle with Literature Gap, Falsifiable Hypothesis, Ablation & Novelty Review."""
        ws = self.benchmark_root / "bm2_project"
        project = self._measure("B2_Project_Init", Project.initialize, ws, "Industrial-Fire-Research", "Research on Wavelet Attention for Industrial Fire Detection", mode="research", protocol_version=2)

        session_pi = self._measure("B2_PI_Start", project.start_session, "Prof-Fire-PI", "other")
        self._measure("B2_PI_Ack", project.acknowledge, session_pi["session"], session_pi["report_hash"])

        # 1. Literature & Gap Analysis: Register 4 baseline literature sources
        lit_ev = ws / "evidence" / "lit_manifest.json"
        lit_ev.parent.mkdir(parents=True, exist_ok=True)
        lit_ev.write_text(json.dumps({"accessed": ["L1", "L2", "L3", "L4"], "verified": True}), encoding="utf-8")

        # Source 1: IEEE Xplore
        s1 = self._measure(
            "B2_Source1_Add",
            gov.add_source,
            project,
            session_pi["session"],
            "YOLOv8-Fire: Real-Time Industrial Fire Detection",
            "IEEE-TIFS-2024-001",
            "https://doi.org/10.1109/TIFS.2024.001",
            "Fast single-stage detector achieving 76.2% mAP at 13.2ms",
            "High false alarm rate (14.8%) under heavy industrial dust and smoke plumes",
            "full_text",
            ["evidence/lit_manifest.json"],
            "IEEE Xplore",
        )

        # Source 2: ACM Digital Library
        s2 = self._measure(
            "B2_Source2_Add",
            gov.add_source,
            project,
            session_pi["session"],
            "FireNet-CNN: Deep Multi-Scale Features for Fire Detection",
            "ACM-MM-2023-042",
            "https://doi.org/10.1145/3581783.042",
            "Multi-scale feature pyramid reduces false alarms to 11.2%",
            "Lacks frequency-domain analysis; vulnerable to dynamic welding and steam flicker",
            "full_text",
            ["evidence/lit_manifest.json"],
            "ACM Digital Library",
        )

        # Source 3: Springer Nature
        s3 = self._measure(
            "B2_Source3_Add",
            gov.add_source,
            project,
            session_pi["session"],
            "Swin-Fire: Vision Transformer for Smoke and Flame",
            "SPRINGER-IJCV-2023-118",
            "https://doi.org/10.1007/s11263-023-118",
            "High mAP (81.2%) on clean optical benchmarks",
            "Inference latency exceeds 45ms on edge embedded GPU, unusable for real-time safety",
            "full_text",
            ["evidence/lit_manifest.json"],
            "Springer Nature",
        )

        # Source 4: Elsevier ScienceDirect
        s4 = self._measure(
            "B2_Source4_Add",
            gov.add_source,
            project,
            session_pi["session"],
            "WaveletDet: Spatial-Frequency Decomposition for Complex Vision",
            "ELSEVIER-PR-2024-209",
            "https://doi.org/10.1016/j.patcog.2024.209",
            "Separates high-frequency smoke texture from low-frequency fire glow",
            "Fixed filter coefficients cannot adaptively handle fluctuating dust concentrations",
            "full_text",
            ["evidence/lit_manifest.json"],
            "ScienceDirect",
        )

        # Register Research Idea with 8 required fields
        idea_ev = ws / "evidence" / "gap_matrix.md"
        idea_ev.write_text("# Research Gap Analysis\nCombining Adaptive Wavelet Frequency Attention (AWFA) with Cross-Scale Multi-Feature (CSMF).\n", encoding="utf-8")

        idea_fields = {
            "existing_work": "Existing CNN and Transformer models trade off false alarm suppression against edge inference latency.",
            "current_limitation": "Static spatial kernels fail to distinguish dynamic dust plumes from turbulent fire flames.",
            "scientific_gap": "Lack of learnable sub-band frequency attention coupled with real-time multi-scale feature aggregation.",
            "proposed_innovation": "Adaptive Wavelet Frequency Attention (AWFA) dynamically weights 2D DWT sub-bands for real-time smoke-fire discrimination.",
            "prior_methods_insufficient": "Fixed DWT cannot adapt to varying dust densities; Transformers exceed 15ms edge compute budgets.",
            "expected_contribution": "Provides a mathematically bounded, frequency-aware fire detector with mAP50 > 80% and latency < 14ms.",
            "publication_potential": "Target IEEE Transactions on Information Forensics and Security (T-IFS) / Pattern Recognition.",
            "coverage_limit": "Evaluated on industrial metallurgical and chemical plant datasets.",
        }

        idea_res = self._measure(
            "B2_Idea_Add",
            gov.add_idea,
            project,
            session_pi["session"],
            "Adaptive Wavelet Frequency Attention with Multi-Scale Fusion for Industrial Fire Detection",
            idea_fields,
            [s1["source"], s2["source"], s3["source"], s4["source"]],
            ["evidence/gap_matrix.md"],
        )
        idea_id = idea_res["idea"]

        # 2. Register Falsifiable Hypothesis
        hypo_ev = ws / "evidence" / "hypothesis_design.md"
        hypo_ev.write_text("# Falsifiable Hypothesis\nPrediction: mAP50 gain >= 3.5% at p < 0.05 with latency <= 15.0ms.\n", encoding="utf-8")

        hypo_res = self._measure(
            "B2_Hypothesis_Add",
            gov.add_hypothesis,
            project,
            session_pi["session"],
            idea_id,
            "AWFA + CSMF will improve small/smoke-obscured fire mAP50 by at least 3.5% over YOLOv8-Fire with latency increase <= 5%.",
            "YOLOv8-Fire Baseline (mAP50 = 76.2%, Latency = 13.2ms, False Alarm = 14.8%)",
            "mAP50 (%), Paired t-test p-value, Edge latency (ms on Jetson Orin), False Alarm Rate (%)",
            "Hypothesis is REFUTED if mAP50 improvement < 3.5%, or p >= 0.05, or latency > 15.0ms.",
            "Gaussian noise injection (sigma=0.05), random illumination fluctuation (+-20%), 5-fold cross validation.",
            ["evidence/hypothesis_design.md"],
        )
        hypo_id = hypo_res["hypothesis"]

        # 3. Novelty Review by Independent Reviewer
        session_rev = self._measure("B2_NoveltyRev_Start", project.start_session, "Dr-Novelty-Reviewer", "other")
        self._measure("B2_NoveltyRev_Ack", project.acknowledge, session_rev["session"], session_rev["report_hash"])

        nov_ev = ws / "evidence" / "novelty_audit.md"
        nov_ev.write_text("Novelty audit confirms learnable sub-band attention is non-trivial compared to WaveletDet and Swin-Fire.", encoding="utf-8")

        self._measure(
            "B2_Novelty_Review",
            gov.review_idea,
            project,
            session_rev["session"],
            idea_id,
            "candidate",
            "Challenged whether AWFA is mere modular stacking; verified frequency-spatial cross-coupling theory and non-linear gain.",
            ["evidence/novelty_audit.md"],
        )

        # 4. Run Experiments and Conclude
        # Since session_rev added events to the ledger, session_pi refreshes context
        ref_pi = self._measure("B2_PI_Refresh", project.refresh_session, session_pi["session"])
        self._measure("B2_PI_ReAck", project.acknowledge, session_pi["session"], ref_pi["report_hash"])

        exp_script = ws / "scripts" / "train_eval.py"
        exp_script.parent.mkdir(parents=True, exist_ok=True)
        exp_script.write_text("""import json, sys
# Simulated rigorous deterministic evaluation
results = {
    'baseline': {'mAP50': 76.2, 'latency_ms': 13.2, 'false_alarm_rate': 14.8},
    'ablation_awfa_only': {'mAP50': 78.4, 'latency_ms': 13.6, 'false_alarm_rate': 8.1},
    'ablation_csmf_only': {'mAP50': 77.9, 'latency_ms': 13.5, 'false_alarm_rate': 11.2},
    'full_proposed': {'mAP50': 80.8, 'latency_ms': 13.8, 'false_alarm_rate': 4.2, 'p_value': 0.0032}
}
with open('outputs/eval_results.json', 'w') as f:
    json.dump(results, f, indent=2)
print('Evaluation completed successfully.')
""", encoding="utf-8")

        cfg_file = ws / "conf" / "experiment_config.json"
        cfg_file.parent.mkdir(parents=True, exist_ok=True)
        cfg_file.write_text(json.dumps({"batch_size": 16, "epochs": 50, "wavelet": "db4", "seed": 42}), encoding="utf-8")

        out_dir = ws / "outputs"
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "eval_results.json").write_text("{}", encoding="utf-8")

        exp_res = self._measure(
            "B2_Exp_Add",
            add_experiment,
            project,
            session_pi["session"],
            "AWFA vs Baseline and Ablation Experiments",
            "Evaluating mAP50, latency and false alarm rate under smoke.",
            [sys.executable, "scripts/train_eval.py"],
            "conf/experiment_config.json",
            [],
            42,
            ["scripts/train_eval.py"],
            cwd=".",
            hypothesis_id=hypo_id,
        )
        exp_id = exp_res["experiment"]

        run_res = self._measure("B2_Exp_Run", run_experiment, project, session_pi["session"], exp_id, timeout=30.0)
        self.assertEqual(run_res["status"], "succeeded")
        run_id = run_res["run"]

        exp_ev = ws / "evidence" / "experiment_findings.md"
        exp_ev.write_text("Full proposed model achieved 80.8% mAP50 (+4.6% gain, p=0.0032 < 0.05) and 13.8ms latency (+4.5% <= 5%).", encoding="utf-8")

        # Refreshed context after experiment run and findings evidence
        ref_post_run = self._measure("B2_PI_PostRun_Refresh", project.refresh_session, session_pi["session"])
        self._measure("B2_PI_PostRun_Ack", project.acknowledge, session_pi["session"], ref_post_run["report_hash"])

        self._measure(
            "B2_Exp_Conclude",
            conclude_experiment,
            project,
            session_pi["session"],
            exp_id,
            "AWFA+CSMF demonstrated statistically significant mAP50 increase (+4.6%) and false alarm reduction from 14.8% to 4.2%.",
            ["evidence/experiment_findings.md"],
        )

        outcome_res = self._measure(
            "B2_Hypothesis_Outcome",
            gov.conclude_hypothesis,
            project,
            session_pi["session"],
            hypo_id,
            exp_id,
            run_id,
            "supported",
            "All falsification criteria met: mAP50 improved by 4.6% (> 3.5%), p=0.0032 (< 0.05), and latency remained 13.8ms (<= 15.0ms).",
            ["evidence/experiment_findings.md"],
        )
        self.assertEqual(outcome_res["verdict"], "supported")

        audit_res = self._measure("B2_Project_Audit", project.audit)
        self.assertTrue(audit_res["ok"])

        GLOBAL_BENCHMARK_METRICS["benchmark2"] = {
            "status": "PASSED",
            "idea_id": idea_id,
            "hypothesis_id": hypo_id,
            "hypothesis_verdict": outcome_res["verdict"],
            "mAP50_gain": "+4.6%",
            "p_value": 0.0032,
            "audit_ok": audit_res["ok"],
        }
        b2_dir = Path(__file__).resolve().parents[1] / "AUDIT" / "benchmarks" / "benchmark2-research-falsification"
        b2_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(idea_ev, b2_dir / "LITERATURE_GAP_MATRIX.md")
        shutil.copy2(hypo_ev, b2_dir / "HYPOTHESIS_DESIGN.md")
        shutil.copy2(nov_ev, b2_dir / "NOVELTY_AUDIT.md")
        shutil.copy2(ws / "outputs" / "eval_results.json", b2_dir / "EVALUATION_RESULTS.json")

    def test_benchmark_3_peer_review_rebuttal_closure(self) -> None:
        """Benchmark 3: Academic paper claim-evidence mapping, multi-reviewer critique, and rebuttal closure."""
        ws = self.benchmark_root / "bm3_project"
        project = self._measure("B3_Project_Init", Project.initialize, ws, "Paper-Rebuttal-Project", "Peer Review and Rebuttal for Industrial Fire Detection", protocol_version=2)

        author_sess = self._measure("B3_Author_Start", project.start_session, "Paper-First-Author", "other")
        self._measure("B3_Author_Ack", project.acknowledge, author_sess["session"], author_sess["report_hash"])

        # 1. Claim-Evidence Mapping Table
        claim_map = ws / "docs" / "CLAIM_EVIDENCE_MAPPING.md"
        claim_map.parent.mkdir(parents=True, exist_ok=True)
        claim_map.write_text("""# Claim-Evidence Mapping Table
| Claim ID | Paper Claim Statement | Supporting Evidence Path | Quantitative Bound | Overclaiming Status |
| :--- | :--- | :--- | :--- | :--- |
| **CLM-01** | AWFA dynamically discriminates turbulent smoke from flame flicker | `evidence/wavelet_energy.json` | SNR improved by 6.4 dB | Validated |
| **CLM-02** | Real-time edge inference on embedded Jetson Orin platform | `evidence/edge_fps_log.txt` | 72.4 FPS (13.8ms per frame) | Validated |
| **CLM-03** | Dust false alarm rate reduced by > 70% relative to baseline | `evidence/metallurgy_test.json` | 14.8% -> 4.2% (71.6% relative drop) | Validated |
""", encoding="utf-8")

        # Create referenced evidence
        (ws / "evidence").mkdir(parents=True, exist_ok=True)
        (ws / "evidence" / "wavelet_energy.json").write_text(json.dumps({"snr_gain_db": 6.4, "subband_energy_variance": 0.012}), encoding="utf-8")
        (ws / "evidence" / "edge_fps_log.txt").write_text("Frames: 10000, Total Time: 138.1s, Average Latency: 13.81ms, FPS: 72.4", encoding="utf-8")
        (ws / "evidence" / "metallurgy_test.json").write_text(json.dumps({"baseline_far": 0.148, "awfa_far": 0.042, "relative_drop": 0.716}), encoding="utf-8")

        # 2. Multi-Reviewer Critique & Point-by-Point Rebuttal Matrix
        rebuttal_matrix = ws / "docs" / "REBUTTAL_MATRIX.md"
        rebuttal_matrix.write_text("""# Structured Rebuttal Matrix (Peer Review Closure)

## Reviewer 1 (Methodology & Mathematical Rigor)
- **Critique 1.1**: "Does the wavelet attention mechanism conserve energy across 2D sub-bands? Explain mathematical convergence under non-stationary illumination."
- **Author Response**: We thank the reviewer for this insightful comment. Under Parseval's theorem, discrete orthogonal wavelet decomposition strictly preserves L2 energy norm: $\\|x\\|^2 = \\|c_A\\|^2 + \\|c_H\\|^2 + \\|c_V\\|^2 + \\|c_D\\|^2$. We proved the energy conservation bounds in Lemma 1 and revised Section 3.2.
- **Evidence / Revision**: Added `proof_lemma1.pdf` and updated manuscript Page 5, Paragraph 3.
- **Reviewer 1 Final Verdict**: **ACCEPT (Score: 8/10)**. "The mathematical justification and Parseval energy bound satisfactorily resolve my concern."

## Reviewer 2 (Experimental Design & Sequence Leakage)
- **Critique 2.1**: "Industrial video datasets feature strong inter-frame correlations. Did your train/val/test split enforce strict temporal sequence separation?"
- **Author Response**: Yes. We enforced zero video sequence overlap. All test sequences come from 3 distinct industrial plants never seen in training. Cross-plant evaluation demonstrates mAP50 of 80.1% (p=0.0041).
- **Evidence / Revision**: Added dataset split hash manifest `dataset_splits_sha256.json` and revised Section 4.4.
- **Reviewer 2 Final Verdict**: **ACCEPT (Score: 8/10)**. "Cross-plant sequence hold-out completely rules out temporal data leakage."

## Reviewer 3 (Engineering Deployment & Boundary Failure)
- **Critique 3.1**: "In high-temperature steam plume conditions, what is the false negative rate? What is the compute breakdown per component?"
- **Author Response**: We tested 120 new steam plume video clips. The false negative rate is 2.1%. AWFA computation takes 0.42ms out of 13.8ms total inference.
- **Evidence / Revision**: Added `steam_stress_results.json` and Table 4 compute breakdown in Section 4.5.
- **Reviewer 3 Final Verdict**: **ACCEPT (Score: 7/10)**. "The real-time profiling on Jetson Orin is solid and reliable."

## Meta-Review Consensus
- **Decision**: **ACCEPT (Oral Presentation Candidate)**.
""", encoding="utf-8")

        # Refreshed context after writing documentation to docs/
        ref_auth = self._measure("B3_Author_Refresh", project.refresh_session, author_sess["session"])
        self._measure("B3_Author_ReAck", project.acknowledge, author_sess["session"], ref_auth["report_hash"])

        # Register task and record rebuttal documentation in ledger
        task_reb = self._measure(
            "B3_Task_Add",
            project.add_task,
            author_sess["session"],
            "Paper Peer Review Rebuttal & Traceability Closure",
            "Establish claim-evidence mapping and finalize point-by-point rebuttal matrix.",
            risk="routine",
            scopes=["docs/CLAIM_EVIDENCE_MAPPING.md", "docs/REBUTTAL_MATRIX.md"],
        )
        task_reb_id = task_reb["task"]

        self._measure(
            "B3_Task_Plan",
            gov.plan_task,
            project,
            author_sess["session"],
            task_reb_id,
            "1. Build claim mapping; 2. Address R1, R2, R3 critiques with supplemental experiments.",
            "1. Verify claim bounds; 2. Assert all reviewers reach Accept verdict.",
            ["docs/CLAIM_EVIDENCE_MAPPING.md"],
        )

        self._measure("B3_Task_Claim", project.claim_task, author_sess["session"], task_reb_id)
        self._measure(
            "B3_Task_Record",
            project.record_task,
            author_sess["session"],
            task_reb_id,
            "Completed claim mapping and rebuttal matrix with 3 reviewer acceptances.",
            ["docs/REBUTTAL_MATRIX.md"],
        )
        self._measure("B3_Task_Complete", project.complete_task, author_sess["session"], task_reb_id)

        audit_res = self._measure("B3_Project_Audit", project.audit)
        self.assertTrue(audit_res["ok"])

        GLOBAL_BENCHMARK_METRICS["benchmark3"] = {
            "status": "PASSED",
            "claim_count": 3,
            "reviewers_accepted": 3,
            "final_decision": "ACCEPT",
            "audit_ok": audit_res["ok"],
        }

        # Export artifacts to AUDIT/benchmarks/
        out_bench = Path(__file__).resolve().parents[1] / "AUDIT" / "benchmarks"
        out_bench.mkdir(parents=True, exist_ok=True)
        b3_dir = out_bench / "benchmark3-paper-rebuttal"
        b3_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(claim_map, b3_dir / "CLAIM_EVIDENCE_MAPPING.md")
        shutil.copy2(rebuttal_matrix, b3_dir / "REBUTTAL_MATRIX.md")

        (out_bench / "phase4-benchmark-metrics.json").write_text(json.dumps(GLOBAL_BENCHMARK_METRICS, indent=2), encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
