import json
import sys
import pytest
from afterstate.controllers import run_controller,ScriptedAdapter,Budget,StdioAdapter


def run(tmp_path,actions,controller="Native",budget=None):
    return run_controller(ScriptedAdapter(actions),{"task":"test"},tmp_path,
                          ["{python}","-c","print('retry')"],{},controller,budget or Budget())


def test_inspection_rejects_modification_and_charges_action(tmp_path):
    r=run(tmp_path,[{"type":"command","argv":["{python}","-c","open('bad','w').write('x')"]},
                    {"type":"final","claim":False}],"Inspect-1")
    assert not (tmp_path/"bad").exists()
    assert "rejected" in r["events"][0]
    assert r["actions"]==2


def test_read3_cannot_read_workspace(tmp_path):
    (tmp_path/"secret").write_text("hidden")
    r=run(tmp_path,[{"type":"read","path":"secret"},{"type":"fixture"},{"type":"fixture"},{"type":"final","claim":False}],"Read-3")
    assert "rejected" in r["events"][0]
    assert "hidden" not in json.dumps(r)


def test_retry_precedes_model_action(tmp_path):
    r=run(tmp_path,[{"type":"final","claim":True}],"Retry-1")
    assert r["events"][0]["result"]["stdout"].strip()=="retry"
    assert r["completion_claim"] and r["actions"]==2


def test_budget_exhaustion_retains_current_state(tmp_path):
    r=run(tmp_path,[{"type":"command","argv":["{python}","-c","open('progress','w').write('keep')"]},
                    {"type":"final","claim":True}],budget=Budget(actions=1))
    assert (tmp_path/"progress").read_text()=="keep"
    assert r["termination"]=="budget_exhausted" and not r["completion_claim"]


def test_self_refine_executes_only_final_candidate(tmp_path):
    bad={"type":"command","argv":["{python}","-c","open('bad','w').write('x')"]}
    good={"type":"command","argv":["{python}","-c","open('good','w').write('x')"]}
    r=run(tmp_path,[bad,{"text":"feedback"},bad,{"text":"feedback"},good,{"type":"final","claim":True}],"Self-Refine")
    assert not (tmp_path/"bad").exists() and (tmp_path/"good").exists()
    assert r["actions"]==7


def test_reflection_is_charged(tmp_path):
    r=run(tmp_path,[{"text":"reflect"},{"type":"final","claim":False}],"Reflexion")
    assert r["actions"]==2 and not r["completion_claim"]


def test_explicit_inability_not_completion(tmp_path):
    r=run(tmp_path,[{"type":"final","claim":False}])
    assert not r["completion_claim"] and r["termination"]=="explicit_inability"


def test_invalid_token_usage_fails_closed(tmp_path):
    class Bad:
        def decide(self,request,max_tokens):
            return {"action":{"type":"final","claim":True},"generated_tokens":max_tokens+1}
    with pytest.raises(ValueError,match="generation limit"):
        run_controller(Bad(),{},tmp_path,["x"],{})


def test_first_model_request_hash_is_stable(tmp_path):
    left=run(tmp_path,[{"type":"final","claim":False}])
    right=run(tmp_path,[{"type":"final","claim":False}])
    assert left["first_model_request_sha256"]==right["first_model_request_sha256"]


def test_stdio_protocol_example(tmp_path):
    from pathlib import Path
    path=Path(__file__).resolve().parents[1]/"examples/stdio_adapter.py"
    adapter=StdioAdapter([sys.executable,str(path)])
    result=run_controller(adapter,{},tmp_path,["x"],{})
    assert result["termination"]=="explicit_inability"
