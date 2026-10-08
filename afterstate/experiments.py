from dataclasses import asdict
import json
from pathlib import Path
import random
import tempfile

from .controllers import Budget, run_controller
from .protocol import capture_boundary, certify, restore_condition, score_clone, visible_request
from .state import StateStore, digest


def run_pairs(adapter_factory, output, categories, controllers, repeats=3, budget=None,
              feedback="raw", configuration="custom-reference-adapter", seed=1729):
    budget=budget or Budget()
    if repeats < 1 or not categories or not controllers:
        raise ValueError("Need positive repeats and nonempty category/controller sets")
    if len(set(categories))!=len(categories) or len(set(controllers))!=len(controllers):
        raise ValueError("Duplicate categories or controllers")
    output=Path(output)
    output.mkdir(parents=True,exist_ok=True)
    records=[]
    with (output/"runs.jsonl").open("w",encoding="utf-8") as stream:
        for category in categories:
            with tempfile.TemporaryDirectory(prefix="afterstate-pair-") as temp:
                base=Path(temp)
                root=base/"task"
                store=StateStore(base/"store")
                boundary=capture_boundary(category,root,store,base/"fault.txt")
                certificate=certify(boundary,root,store)
                (output/(boundary.site.site_id+"-certificate.json")).write_text(json.dumps(certificate,indent=2),encoding="utf-8")
                for controller in controllers:
                    for repeat in range(repeats):
                        protocols=["PRE","REAL"]
                        random.Random(seed+repeat).shuffle(protocols)
                        for protocol in protocols:
                            state=restore_condition(boundary,protocol,root,store)
                            visible=visible_request(boundary,controller,feedback)
                            visible.update(budget=asdict(budget), repeat_seed=seed+repeat)
                            result=run_controller(adapter_factory(),visible,root,boundary.site.command,
                                                  boundary.environment,controller,budget)
                            final=store.capture(root)
                            scored=score_clone(boundary.site,final,store)
                            identity={"site_id":boundary.site.site_id,"configuration":configuration,
                                      "controller":controller,"repeat":repeat,"protocol":protocol,
                                      "feedback":feedback,"budget_actions":budget.actions}
                            run_id=digest(identity)
                            (output/(run_id+"-trace.json")).write_text(json.dumps(result,indent=2),encoding="utf-8")
                            row={**identity,"run_id":run_id,"repository":boundary.site.repository,
                                 "category":category,"origin":"new_controlled_experiment",
                                 "first_request_sha256":digest(visible),
                                 "first_model_request_sha256":result["first_model_request_sha256"],
                                 "state_sha256":state.fingerprint,"final_state_sha256":final.fingerprint,
                                 **scored,**{k:result[k] for k in ["actions","generated_tokens","completion_claim","termination","elapsed_seconds"]},
                                 "silent_error":result["completion_claim"] and not scored["success"]}
                            stream.write(json.dumps(row,sort_keys=True)+"\n")
                            stream.flush()
                            records.append(row)
    return records
