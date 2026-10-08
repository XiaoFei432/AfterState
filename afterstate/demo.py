from __future__ import annotations
from dataclasses import asdict
import json
from pathlib import Path
import random
import tempfile

from .fixtures import CATEGORIES, reference_recover
from .protocol import capture_boundary, certify, restore_condition, score_clone, visible_request, PROTOCOLS
from .state import StateStore, digest


def run_demo(output: Path, categories=CATEGORIES, mechanical=5, reference=3, repeats=1):
    if repeats < 1:
        raise ValueError("Repeats must be positive")
    output.mkdir(parents=True, exist_ok=True)
    certificates, ledger, manifests = [], [], []
    for category in categories:
        with tempfile.TemporaryDirectory(prefix="afterstate-demo-") as temp:
            base = Path(temp)
            root = base / "task"
            store = StateStore(base / "store")
            boundary = capture_boundary(category, root, store, base / "fault.txt")
            certificate = certify(boundary, root, store, mechanical, reference)
            certificates.append(certificate)
            manifests.append({**asdict(boundary.site), "repository": boundary.site.repository,
                              "state_backend": "declared-directory-demo", "history": visible_request(boundary)["history"],
                              "future_fault_schedule": "one-shot failure; clear at boundary in every branch",
                              "certification": {"mechanical_repetitions": mechanical, "reference_repetitions": reference},
                              "reference_repair_visible_to_agent": False})
            for repeat in range(repeats):
                conditions = [p for p in PROTOCOLS if p != "POST" or boundary.site.legal_post]
                random.Random(1729 + repeat).shuffle(conditions)
                for condition in conditions:
                    initial = restore_condition(boundary, condition, root, store)

                    initial_score = score_clone(boundary.site, initial, store)
                    request = visible_request(boundary)
                    reference_recover(boundary.site, root, boundary.environment)
                    final = store.capture(root)
                    result = score_clone(boundary.site, final, store)
                    row = {"site_id": boundary.site.site_id, "repository": boundary.site.repository,
                           "category": category, "origin": boundary.site.origin, "configuration": "reference-demo",
                           "controller": "ReferenceRepair", "protocol": condition, "repeat": repeat,
                           "feedback": "raw", "budget_actions": None, "generated_tokens": 0,
                           "completion_claim": True, "silent_error": not result["success"],
                           "initial_success": initial_score["success"], "actions": 1,
                           "first_request_sha256": digest(request), "state_sha256": initial.fingerprint,
                           "final_state_sha256": final.fingerprint, "termination": "reference_repair", **result}
                    row["run_id"] = digest({k: row[k] for k in ["site_id", "configuration", "controller", "protocol", "repeat", "feedback"]})
                    ledger.append(row)
            print(f"Certified {category}: {mechanical} mechanical replays, {reference} reference recoveries")
    (output / "certificates.json").write_text(json.dumps(certificates, indent=2), encoding="utf-8")
    (output / "demo-manifests.json").write_text(json.dumps(manifests, indent=2), encoding="utf-8")
    (output / "demo-runs.jsonl").write_text("".join(json.dumps(row, sort_keys=True)+"\n" for row in ledger), encoding="utf-8")
    summary = {"origin": "new_controlled_demonstration", "sites": len(certificates),
               "runs": len(ledger), "successes": sum(r["success"] for r in ledger),
               "note": "Execution method: reference repairs; model calls: 0."}
    (output / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary
