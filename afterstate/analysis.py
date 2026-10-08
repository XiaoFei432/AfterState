from __future__ import annotations
from collections import defaultdict
from itertools import combinations
import json
import math
from pathlib import Path
import random
from statistics import mean


BLOCK = ("site_id", "configuration", "repeat", "feedback", "budget_actions")
IDENTITY = BLOCK + ("controller", "protocol")
REQUIRED = IDENTITY + ("repository", "category", "success", "functional", "state_obligations",
                      "completion_claim", "actions", "silent_error", "first_request_sha256")


def load_records(path):
    rows = [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]
    validate(rows)
    return rows


def validate(rows):
    if not rows:
        raise ValueError("No run-level records")
    seen, sites = set(), {}
    for row in rows:
        missing = set(REQUIRED) - row.keys()
        if missing:
            raise ValueError("Missing run fields: " + ", ".join(sorted(missing)))
        key = tuple(row[k] for k in IDENTITY)
        if key in seen:
            raise ValueError("Duplicate continuation")
        seen.add(key)
        for k in ("success", "functional", "state_obligations", "completion_claim", "silent_error"):
            if type(row[k]) is not bool:
                raise ValueError(f"{k} must be boolean")
        if row["success"] != (row["functional"] and row["state_obligations"]):
            raise ValueError("Full oracle must equal functional AND state obligations")
        if row["silent_error"] != (row["completion_claim"] and not row["success"]):
            raise ValueError("Silent-error definition violated")
        if type(row["actions"]) is not int or row["actions"] < 0:
            raise ValueError("Invalid action count")
        meta = (row["repository"], row["category"])
        if row["site_id"] in sites and sites[row["site_id"]] != meta:
            raise ValueError("Site identity has inconsistent repository/category")
        sites[row["site_id"]] = meta
        if row.get("infrastructure_error"):
            raise ValueError("Unresolved infrastructure error; not an agent failure")


def matched_cells(rows, controllers, protocols=("PRE", "REAL")):
    validate(rows)
    selected = [r for r in rows if r["controller"] in controllers and r["protocol"] in protocols]
    if not selected:
        raise ValueError("No selected continuations")

    if len({(r["feedback"], r["budget_actions"]) for r in selected}) != 1:
        raise ValueError("Select exactly one feedback and resource setting")
    blocks = defaultdict(dict)
    for r in selected:
        blocks[tuple(r[k] for k in BLOCK)][(r["controller"], r["protocol"])] = r
    expected = {(c, p) for c in controllers for p in protocols}
    for block in blocks.values():
        if set(block) != expected:
            raise ValueError("Incomplete paired block; missing runs cannot be treated as failures")
        for c in controllers:
            hashes = {block[(c, p)]["first_request_sha256"] for p in protocols}
            if len(hashes) != 1 or not next(iter(hashes)):
                raise ValueError("Paired first-request hash mismatch or missing hash")

    grids = defaultdict(set)
    for site, config, repeat, _, _ in blocks:
        grids[site].add((config, repeat))
    if len({frozenset(g) for g in grids.values()}) != 1:
        raise ValueError("Unequal site/configuration/repeat grid; specify a different estimand explicitly")
    repeats_by_configuration=defaultdict(set)
    for config,repeat in next(iter(grids.values())):
        repeats_by_configuration[config].add(repeat)
    if len({frozenset(r) for r in repeats_by_configuration.values()}) != 1:
        raise ValueError("Unequal repeats across configurations would violate equal configuration weighting")
    return blocks


def quantile(values, probability):
    ordered = sorted(values)
    pos = (len(ordered)-1)*probability
    low = int(pos)
    high = min(low+1, len(ordered)-1)
    return ordered[low] + (ordered[high]-ordered[low])*(pos-low)


def cluster_interval(site_values, samples=10000, seed=1729):


    if samples < 1:
        raise ValueError("Bootstrap resamples must be positive")
    clusters = defaultdict(list)
    for repository, value in site_values:
        clusters[repository].append(value)
    point = mean(v for _, v in site_values)
    if len(clusters) < 2:
        return {"estimate": point, "ci95": None, "p_centered_bootstrap": None,
                "reason": "At least two repository clusters are required"}
    keys = sorted(clusters)
    rng = random.Random(seed)
    draws = []
    for _ in range(samples):
        chosen = [rng.choice(keys) for _ in keys]
        draws.append(mean(x for k in chosen for x in clusters[k]))

    p = (1 + sum(abs(x-point) >= abs(point)-1e-12 for x in draws))/(samples+1)
    return {"estimate": point, "ci95": [quantile(draws, .025), quantile(draws, .975)],
            "p_centered_bootstrap": min(1.0, p), "repository_clusters": len(keys),
            "resamples": samples, "seed": seed}


def holm(pvalues):
    adjusted = {}
    maximum = 0.0
    for i, (name, p) in enumerate(sorted(pvalues.items(), key=lambda kv: kv[1])):
        maximum = max(maximum, (len(pvalues)-i)*p)
        adjusted[name] = min(1.0, maximum)
    return adjusted


def equivalent(interval, margin_pp=2):
    bounds = interval.get("ci95")
    return bounds is not None and bounds[0] >= -margin_pp and bounds[1] <= margin_pp


def analyze(rows, controllers=None, samples=10000, seed=1729):
    controllers = controllers or sorted({r["controller"] for r in rows})
    blocks = matched_cells(rows, controllers)
    site_cells = defaultdict(lambda: defaultdict(list))
    repositories = {}
    cross_tabs = {c: defaultdict(int) for c in controllers}
    for key, block in blocks.items():
        site = key[0]
        repositories[site] = next(iter(block.values()))["repository"]
        for cell, row in block.items():
            site_cells[site][cell].append(row)
        for c in controllers:
            label = lambda r: "success" if r["success"] else ("silent" if r["silent_error"] else "other_failure")
            cross_tabs[c][label(block[c, "PRE"])+"/"+label(block[c, "REAL"])] += 1
    means = {s: {cell: {metric: mean(float(r[metric]) for r in records)
                       for metric in ["success", "silent_error", "actions", "functional"]}
                 for cell, records in cells.items()} for s, cells in site_cells.items()}
    summary = {}
    for c in controllers:
        metrics = {p: {m: mean(means[s][c, p][m] for s in means)
                       for m in ["success", "silent_error", "actions", "functional"]} for p in ["PRE", "REAL"]}
        effects = [(repositories[s], 100*(means[s][c, "PRE"]["success"]-means[s][c, "REAL"]["success"])) for s in means]
        interval = cluster_interval(effects, samples, seed)
        summary[c] = {"metrics": metrics, "pre_minus_real_pp": interval,
                      "equivalent_within_2pp": equivalent(interval), "paired_outcomes": dict(cross_tabs[c])}
    interactions = {}
    for c0, c1 in combinations(controllers, 2):
        values = [(repositories[s], 100*((means[s][c1, "REAL"]["success"]-means[s][c0, "REAL"]["success"])
                                         -(means[s][c1, "PRE"]["success"]-means[s][c0, "PRE"]["success"]))) for s in means]
        interactions[c1+" vs "+c0] = cluster_interval(values, samples, seed)
    ps = {k: v["p_centered_bootstrap"] for k, v in interactions.items() if v["p_centered_bootstrap"] is not None}
    for k, p in holm(ps).items():
        interactions[k]["p_holm"] = p
    return {"sites": len(means), "matched_blocks": len(blocks), "controllers": summary,
            "interactions": interactions, "units": "rates are fractions; contrasts and CIs are percentage points",
            "p_value_method": "two-sided centered repository bootstrap approximation; Holm within controller-pair family"}


def select_and_evaluate(policy_rows, replication_rows, tie_order, samples=10000):
    policy = analyze(policy_rows, tie_order, samples)
    train_repos = {r["repository"] for r in policy_rows}
    test_repos = {r["repository"] for r in replication_rows}
    if train_repos & test_repos or {r["site_id"] for r in policy_rows} & {r["site_id"] for r in replication_rows}:
        raise ValueError("POLICY and REPLICATION must have disjoint repositories and sites")
    choices = {p: max(tie_order, key=lambda c: policy["controllers"][c]["metrics"][p]["success"]) for p in ["PRE", "REAL"]}
    frozen = list(dict.fromkeys([choices["PRE"], choices["REAL"]]))
    replication = analyze(replication_rows, frozen, samples)
    return {"selection": choices, "tie_order": tie_order, "frozen_policy_sha256": __import__("hashlib").sha256(json.dumps(choices, sort_keys=True).encode()).hexdigest(),
            "held_out_analysis": replication, "repositories_disjoint": True}
