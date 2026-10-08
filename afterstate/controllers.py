from __future__ import annotations
from dataclasses import dataclass
import json
from pathlib import Path
import subprocess
import time

from .execution import execute
from .state import safe_path, digest


CONTROLLERS = ("Native", "Retry-1", "Reflexion", "Self-Refine", "Inspect-1", "Inspect-3", "Inspect-6", "Read-3")


@dataclass(frozen=True)
class Budget:
    actions: int = 40
    tokens: int = 16000
    seconds: float = 1800
    command_seconds: float = 300

    def __post_init__(self):
        if min(self.actions, self.tokens, self.seconds, self.command_seconds) <= 0:
            raise ValueError("All resource limits must be positive")

    @classmethod
    def scaled(cls, actions):
        return cls(actions=actions, tokens=400 * actions, seconds=45 * actions)


class StdioAdapter:


    def __init__(self, command: list[str], timeout=120):
        self.command = command
        self.timeout = timeout

    def decide(self, request, max_tokens):
        payload = {"request": request, "max_tokens": max_tokens}
        response = subprocess.run(self.command, input=json.dumps(payload), text=True,
                                  capture_output=True, timeout=self.timeout, check=True)
        data = json.loads(response.stdout)
        return data


class ScriptedAdapter:

    def __init__(self, actions):
        self.actions = iter(actions)

    def decide(self, request, max_tokens):
        return {"action": next(self.actions, {"type": "final", "claim": False}), "generated_tokens": 0}


def inspect_action(action, root):
    kind = action.get("type")
    if kind == "fixture":
        return "Immutable task-independent fixture: alpha beta gamma.\n"
    if kind == "list":
        name = action.get("path", ".")
        p = root if name == "." else safe_path(root, name)
        if p.is_symlink():
            raise ValueError("Inspection cannot follow symlinks")
        return "\n".join(sorted(c.name + ("/" if c.is_dir() else "") for c in p.iterdir())).encode("utf-8")[:2048].decode("utf-8",errors="ignore")
    if kind == "read":
        p = safe_path(root, action["path"])
        if p.is_symlink():
            raise ValueError("Inspection cannot follow symlinks")
        with p.open("rb") as f:
            return f.read(2048).decode("utf-8", errors="ignore")
    raise ValueError("Initial inspections accept only list/read; arbitrary shell is not read-only")


def run_controller(adapter, initial_request, root, failed_command, environment,
                   controller="Native", budget=None):
    if controller not in CONTROLLERS:
        raise ValueError("Unknown controller")
    budget = budget or Budget()
    started = time.monotonic()
    events, memories = [], []
    used_tokens = 0
    claimed = False
    stop = "budget_exhausted"
    failures = 1
    handled_failures = 0
    request_hashes = []
    inspection_limit = int(controller.split("-")[1]) if controller.startswith("Inspect-") else (3 if controller == "Read-3" else 0)
    inspection_count = 0

    def available():
        return len(events) < budget.actions and used_tokens < budget.tokens and time.monotonic() - started < budget.seconds

    def decide(stage, cap=2048, context=None):
        nonlocal used_tokens
        if not available():
            return None
        request = {**initial_request, "stage": stage, "events": list(events),
                   "memories": list(memories), "context": context}
        request_hashes.append(digest({"request": request, "max_tokens": min(cap, budget.tokens-used_tokens)}))
        if isinstance(adapter, StdioAdapter):
            adapter.timeout = min(adapter.timeout, budget.seconds - (time.monotonic()-started))
        try:
            response = adapter.decide(request, min(cap, budget.tokens-used_tokens))
        except subprocess.TimeoutExpired:
            events.append({"type": "deadline", "stage": stage})
            return None
        tokens = response.get("generated_tokens")
        if not isinstance(tokens, int) or isinstance(tokens, bool) or tokens < 0:
            raise ValueError("Adapter must report a nonnegative integer generated_tokens")
        if tokens > min(cap, budget.tokens-used_tokens):
            raise ValueError("Adapter exceeded generation limit; invalid continuation")
        used_tokens += tokens
        if time.monotonic() - started >= budget.seconds:
            events.append({"type": "deadline", "stage": stage, "tokens": tokens})
            return None
        return response["action"]

    def act(action):
        nonlocal failures, claimed, stop
        kind = action.get("type")
        event = {"action": action}
        try:
            if kind == "final":
                if type(action.get("claim")) is not bool:
                    raise ValueError("final.claim must be an explicit boolean")
                claimed = action["claim"]
                stop = "completion_claim" if claimed else "explicit_inability"
            elif kind in {"read", "list", "fixture"}:
                event["output"] = inspect_action(action, root)
            elif kind == "command":
                argv = action["argv"]
                if not isinstance(argv, list) or not argv or not all(isinstance(x, str) for x in argv):
                    raise ValueError("command.argv must be a nonempty string array")
                remaining = budget.seconds - (time.monotonic()-started)
                if remaining <= 0:
                    stop = "budget_exhausted"
                    event["error"] = "deadline"
                else:
                    result = execute(argv, root, timeout=min(budget.command_seconds, remaining), env=environment)
                    event["result"] = result.feedback()
                    failures += int(result.exit_code != 0)
            else:
                raise ValueError("Unsupported action type")
        except (ValueError, KeyError, OSError) as exc:
            event["rejected"] = str(exc)
        events.append(event)

    if controller == "Retry-1" and available():
        act({"type": "command", "argv": list(failed_command)})
    while available():
        if stop != "budget_exhausted":
            break
        if inspection_count < inspection_limit:
            action = decide("immutable_read" if controller == "Read-3" else "inspect")
            if action is None:
                break
            inspection_count += 1
            allowed = {"fixture"} if controller == "Read-3" else {"read", "list"}
            if action.get("type") == "continue":
                events.append({"action": action, "stage": "end_inspection"})
                inspection_count = inspection_limit
            elif action.get("type") not in allowed:
                events.append({"action": action, "rejected": "Only read-only inspection is allowed in this phase"})
            else:
                act(action)
            continue
        if controller in {"Reflexion", "Self-Refine"} and handled_failures < min(failures, 3):
            handled_failures += 1
            if controller == "Reflexion":
                reflection = decide("reflect", 512)
                if reflection is None:
                    break
                memories.append(str(reflection.get("text", "")))
                memories[:] = memories[-3:]
                events.append({"stage": "reflect", "text": memories[-1]})
            else:
                candidate = decide("candidate", 512)
                if candidate is None:
                    break
                events.append({"stage": "candidate", "candidate": candidate})
                complete = True
                for _ in range(2):
                    feedback = decide("self_feedback", 256, candidate)
                    if feedback is None:
                        complete = False
                        break
                    events.append({"stage": "self_feedback", "feedback": feedback})
                    revised = decide("revise", 512, {"candidate": candidate, "feedback": feedback})
                    if revised is None:
                        complete = False
                        break
                    candidate = revised
                    events.append({"stage": "revise", "candidate": candidate})
                if complete and available():
                    act(candidate)
                continue
        action = decide("recover")
        if action is None:
            break
        act(action)
    return {"actions": len(events), "generated_tokens": used_tokens, "completion_claim": claimed,
            "termination": stop, "elapsed_seconds": time.monotonic()-started,
            "first_model_request_sha256": request_hashes[0] if request_hashes else None,
            "model_request_sha256": request_hashes, "events": events}
