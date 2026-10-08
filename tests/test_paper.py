from pathlib import Path
from afterstate.paper import audit,read_data

ROOT=Path(__file__).resolve().parents[1]

def test_published_arithmetic():
    result=audit(ROOT)
    assert result["passed"], [c for c in result["checks"] if not c["passed"]]
    assert len(result["checks"])>=80

def test_missing_values_are_not_imputed():
    data=read_data(ROOT)
    assert data["surgery"]["stratum_success_counts"] is None
    assert data["inspection"][1]["pre_success_pct"] is None
    assert data["resource"][2]["inspect_real_pct"] is None
    assert data["provenance"]["run_level_records_available"] is False
