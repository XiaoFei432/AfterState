from copy import deepcopy
import pytest
from afterstate.analysis import analyze,validate,holm,cluster_interval,select_and_evaluate


def records():
    rows=[]


    for repo in ["r1","r2"]:
        for repeat in [0,1]:
            for c in ["Retry-1","Inspect-3"]:
                for p in ["PRE","REAL"]:
                    success=(c=="Retry-1")== (p=="PRE")
                    rows.append(dict(site_id=repo+"s",repository=repo,category="test",configuration="test",repeat=repeat,
                                     controller=c,protocol=p,feedback="raw",budget_actions=40,success=success,
                                     functional=success,state_obligations=True,completion_claim=True,silent_error=not success,
                                     actions=4,first_request_sha256="paired"))
    return rows


def test_known_paired_difference_and_interaction():
    r=analyze(records(),["Retry-1","Inspect-3"],samples=100)
    assert r["controllers"]["Retry-1"]["pre_minus_real_pp"]["estimate"]==100
    assert r["interactions"]["Inspect-3 vs Retry-1"]["estimate"]==200
    assert r["interactions"]["Inspect-3 vs Retry-1"]["ci95"]==[200,200]


def test_missing_pair_rejected():
    with pytest.raises(ValueError,match="Incomplete"):
        analyze(records()[:-1])


def test_duplicate_rejected():
    rows=records()
    with pytest.raises(ValueError,match="Duplicate"):
        validate(rows+[rows[0]])


def test_information_leak_rejected():
    rows=records(); rows[0]["first_request_sha256"]="protocol-leak"
    with pytest.raises(ValueError,match="hash mismatch"):
        analyze(rows)


def test_inability_not_silent_error():
    rows=records(); rows[1]["completion_claim"]=False
    with pytest.raises(ValueError,match="Silent-error"):
        validate(rows)
    rows[1]["silent_error"]=False
    validate(rows)


def test_resource_conditions_cannot_be_pooled():
    rows=records(); rows[0]["budget_actions"]=80
    with pytest.raises(ValueError,match="exactly one"):
        analyze(rows)


def test_unequal_configuration_repeats_rejected():
    rows=records()
    extra=[deepcopy(r) for r in rows if r["repeat"]==0]
    for r in extra:
        r["configuration"]="second-configuration"
    with pytest.raises(ValueError,match="Unequal repeats"):
        analyze(rows+extra)


def test_holm_known_values():
    assert holm({"a":.01,"b":.04,"c":.03})=={"a":.03,"c":.06,"b":.06}


def test_single_repository_does_not_produce_ci():
    assert cluster_interval([("r",1),("r",2)],samples=100)["ci95"] is None


def test_policy_selection_and_disjointness():
    train=records(); test=deepcopy(train)
    for r in test:
        r["repository"]="new-"+r["repository"]; r["site_id"]="new-"+r["site_id"]
    out=select_and_evaluate(train,test,["Retry-1","Inspect-3"],samples=100)
    assert out["selection"]=={"PRE":"Retry-1","REAL":"Inspect-3"}
    with pytest.raises(ValueError,match="disjoint"):
        select_and_evaluate(train,train,["Retry-1","Inspect-3"],samples=100)
