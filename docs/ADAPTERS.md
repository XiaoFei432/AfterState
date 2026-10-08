# Custom adapter interface

`configs/registry.json` records public agent versions. The adapter interface accepts external decision processes. Native checkpoint and framework-specific integrations are not included.

## JSON exchange

Create a JSON file containing an executable argument list, for example:

```json
["python", "examples/stdio_adapter.py"]
```

Then run:

```console
python -m afterstate run --adapter-command adapter-command.json --categories patch database --controllers Native Inspect-3 --configuration my-custom-adapter --output runs/custom
```

The executable receives one JSON object on stdin and returns one JSON object on stdout. It starts afresh per decision; all visible history is supplied in the request. Diagnostics use stderr. An adapter can connect to a persistent model service; task history is supplied in each request.

Input:

```json
{
  "request": {
    "task": "...",
    "history": [{"command": ["git", "apply", "--reject", "change.patch"], "result": {"exit_code": 1}}],
    "controller": "Native",
    "cwd": "/task",
    "stage": "recover",
    "events": [],
    "memories": [],
    "context": null
  },
  "max_tokens": 2048
}
```

Response:

```json
{"action": {"type": "list", "path": "."}, "generated_tokens": 12}
```

Supported actions:

| Type | Fields | Meaning |
|---|---|---|
| `list` | `path` relative to task root | List names only, read-only |
| `read` | `path` relative to task root | Read up to 2 KiB; no symlink traversal |
| `fixture` | none | Return fixed task-independent text for Read-3 |
| `continue` | none | End initial optional inspection phase |
| `command` | `argv` string array | Execute trusted local command; `{python}` resolves to the harness interpreter |
| `final` | `claim` boolean, optional `text` | Explicit completion claim or inability |
| `thought` | `text` | Reflection or feedback content in a deliberation stage |

`inspect` and `immutable_read` stages constrain allowed actions. `reflect` and `self_feedback` expect text. `candidate` and `revise` return a proposed executable action; candidates are never executed before the final revision. Unknown/forbidden actions are logged and charged to the budget.

The interface includes generated-token usage, `max_tokens`, repeat seed and model settings. Task observations use harness actions. The included `stdio_adapter.py` returns deterministic inability and uses zero model tokens; it is a scripted protocol example.

## Execution boundary

Shell subprocesses and external adapters share the host access rights. No CPU, memory, network, whole-filesystem or disk quota isolation is enforced. Adapter-side reads, inherited environment variables and background child writers are outside the directory backend's observation boundary.

