import json
import sys

payload=json.load(sys.stdin)
stage=payload["request"]["stage"]
if stage=="inspect":
    action={"type":"list","path":"."}
elif stage=="immutable_read":
    action={"type":"fixture"}
elif stage in {"reflect","self_feedback"}:
    action={"type":"thought","text":"Example adapter has no recovery model."}
else:
    action={"type":"final","claim":False}
json.dump({"action":action,"generated_tokens":0},sys.stdout)
