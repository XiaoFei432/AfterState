from __future__ import annotations
import html
import json
import re
from pathlib import Path


def read_data(root):
    return json.loads((Path(root) / "data/paper/aggregates.json").read_text(encoding="utf-8"))


def audit(root):
    d = read_data(root)
    cohorts = json.loads((Path(root) / "configs/cohorts.json").read_text(encoding="utf-8"))
    checks = []

    def check(name, actual, expected, tolerance=1e-9):
        passed = abs(actual-expected) <= tolerance
        checks.append({"name": name, "actual": actual, "expected": expected,
                       "tolerance": tolerance, "passed": passed})

    a, m, paired, o, s = d["audit"], d["main"], d["main_pairing"], d["oracle"], d["surgery"]
    check("audit categories sum to nonzero returns", sum(a[k] for k in ["partial", "complete_despite_error", "no_relevant_effects", "insufficient_evidence"]), a["nonzero_returns"])
    check("partial-effects prevalence among nonzero returns (%)", 100*a["partial"]/a["nonzero_returns"], 25)
    check("MAIN per-protocol count", 240*8*3, m["per_protocol"])
    check("unique recovery ledger", sum(c["new_runs"] for c in cohorts["cohorts"]), cohorts["unique_recovery_runs"])
    check("MAIN pairing total", sum(paired.values()), m["per_protocol"])
    check("PRE successes from pairing", paired["both_success"]+paired["pre_only"], m["pre_success_count"])
    check("REAL successes from pairing", paired["both_success"]+paired["real_only"], m["real_success_count"])
    check("PRE full success (%)", 100*m["pre_success_count"]/m["per_protocol"], 72.3, .051)
    check("REAL full success (%)", 100*m["real_success_count"]/m["per_protocol"], 62.9, .051)
    gap = 100*(m["pre_success_count"]-m["real_success_count"])/m["per_protocol"]
    check("MAIN success contrast (pp)", gap, 9.4, .051)
    check("paired disagreement (%)", 100*(paired["pre_only"]+paired["real_only"])/m["per_protocol"], 25)
    check("action increase from printed means (%)", 100*(m["real_actions"]/m["pre_actions"]-1), 36)
    check("natural sites", sum(c["natural"] for c in d["categories"]), 180)
    check("controlled sites", sum(c["controlled"] for c in d["categories"]), 60)
    for c in d["categories"]:
        check(c["category"]+" category size", c["natural"]+c["controlled"], 40)
        check(c["category"]+" rounded gap", c["pre_success_pct"]-c["real_success_pct"], c["gap_pp"], .151)
    check("weaker oracle extra PRE acceptances", o["pre_functional"]-o["pre_full"], 210)
    check("weaker oracle extra REAL acceptances", o["real_functional"]-o["real_full"], 564)
    hidden = 100*(1-(o["pre_functional"]-o["real_functional"])/(o["pre_full"]-o["real_full"]))
    check("contrast concealed by weaker oracle (%)", hidden, 65.6, .051)
    counts = s["success_counts"]
    check("UNDO restoration of aggregate contrast (%)", 100*(counts["UNDO"]-counts["REAL"])/(counts["PRE"]-counts["REAL"]), 92)
    check("WORKTREE residual gap (pp)", 100*(counts["WORKTREE"]-counts["REAL"])/s["per_condition"], 5.6, .051)
    policies = {p["controller"]:p for p in d["policy"]}
    for row in d["pairwise_interactions"]:
        x, y = policies[row["first"]], policies[row["second"]]
        pre = x["pre_success_pct"]-y["pre_success_pct"]
        real = x["real_success_pct"]-y["real_success_pct"]
        name = row["first"]+" vs "+row["second"]
        check(name+" PRE advantage", pre, row["pre_advantage_pp"], .151)
        check(name+" REAL advantage", real, row["real_advantage_pp"], .151)
        check(name+" interaction", real-pre, row["interaction_pp"], .201)
        check(name+" reversal", int(pre*real < 0), int(row["reversal"]))
    check("strict mean reversals", sum(r["reversal"] for r in d["pairwise_interactions"]), 6)
    rep = d["replication"]
    rp = rep["pairing_real"]
    check("replication pairing total", sum(rp.values()), rep["per_protocol_per_controller"])
    check("replication Inspect successes", rp["both_success"]+rp["inspect_only"], 510)
    check("replication Retry successes", rp["both_success"]+rp["retry_only"], 432)
    check("held-out success advantage (pp)", 100*(510-432)/720, 10.8, .051)
    for c in rep["controllers"]:
        for p in ["pre", "real"]:
            check(c["controller"]+" replication "+p+" rate", 100*c[p+"_success_count"]/720, c[p+"_success_pct"], .051)
    warnings = list(d["source_caveats"])
    warnings.append("These checks evaluate arithmetic relationships in manuscript aggregate data.")
    return {"origin": "paper_aggregate_arithmetic_audit", "passed": all(c["passed"] for c in checks),
            "checks": checks, "warnings": warnings,
            "derived": {"main_gap_pp": gap, "focal_interaction_pp": 17.5, "hidden_contrast_pct": hidden}}


def figures(root, output):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    d = read_data(root)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10,
                         "axes.spines.top": False, "axes.spines.right": False,
                         "svg.fonttype": "none", "pdf.fonttype": 42,
                         "figure.dpi": 120, "savefig.dpi": 180})
    colors = ["#3973A5", "#D18B36", "#539781", "#9565A3"]
    generated = []

    def save(fig, name, caption):
        fig.text(.5, .014, "Source: manuscript aggregate data.",
                 ha="center", fontsize=8, color="#555555")
        fig.tight_layout(rect=(0, .045, 1, 1), pad=1.8)
        for ext in ["png", "svg", "pdf"]:
            meta = {"Creator": "AfterState anonymous artifact"} if ext == "pdf" else None
            fig.savefig(output / (name+"."+ext), metadata=meta)
            if ext == "svg":
                path = output / (name+".svg")
                path.write_text(re.sub(r"<!--.*?-->", "", path.read_text(encoding="utf-8"), flags=re.DOTALL), encoding="utf-8")
        plt.close(fig)
        generated.append({"name": name, "caption": caption})

    def pairs(ax, labels, pre, real, xlabel="Success (%)"):
        y = np.arange(len(labels))
        ax.barh(y-.18, pre, height=.34, label="PRE", color=colors[0])
        ax.barh(y+.18, real, height=.34, label="REAL", color=colors[1])
        for i, (p, r) in enumerate(zip(pre, real)):
            ax.text(p+.7, i-.18, f"{p:.1f}", va="center", fontsize=9)
            ax.text(r+.7, i+.18, f"{r:.1f}", va="center", fontsize=9)
        ax.set_yticks(y, labels)
        ax.invert_yaxis()
        ax.set_ylim(len(labels)+.25,-.6)
        ax.set_xlabel(xlabel)
        ax.set_xlim(0, max(pre+real)*1.15)
        ax.legend(loc="lower right", frameon=False)

    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.5))
    paired = d["main_pairing"]
    labels = ["Both\nsucceed", "PRE\nonly", "REAL\nonly", "Both\nfail"]
    values = [100*n/d["main"]["per_protocol"] for n in paired.values()]
    axes[0].bar(labels, values, color=colors)
    for i, (v, n) in enumerate(zip(values, paired.values())):
        axes[0].text(i, v+1, f"{v:.1f}%\n({n:,})", ha="center", fontsize=9)
    axes[0].set_ylim(0, 70)
    axes[0].set_ylabel("Matched continuations (%)")
    axes[0].set_title("(a) Matched recovery outcomes")
    o = d["oracle"]
    pairs(axes[1], ["Full contract", "Functional only"],
          [100*o[k]/5760 for k in ["pre_full", "pre_functional"]],
          [100*o[k]/5760 for k in ["real_full", "real_functional"]], "Accepted outcomes (%)")
    axes[1].set_title("(b) Nested oracle comparison")
    save(fig, "figure06_paired_oracle", "Figure 6, recomputed from the printed counts.")

    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.5))
    counts = d["surgery"]["success_counts"]
    for ax, names, title in [(axes[0], ["PRE","REAL","UNDO","REINTRO"], "(a) Removal and reconstruction"),
                             (axes[1], ["PRE","WORKTREE","OUTSIDE","REAL"], "(b) Aggregate state coverage")]:
        vals = [100*counts[n]/1440 for n in names]
        ax.bar(names, vals, color=colors)
        for i,v in enumerate(vals):
            ax.text(i,v+1,f"{v:.1f}%\n({counts[names[i]]:,})",ha="center",fontsize=9)
        ax.set_ylim(0,95)
        ax.set_ylabel("Task success (%)")
        ax.set_title(title)
        ax.tick_params(axis="x",labelsize=8)
    save(fig,"figure07_state_interventions","Figure 7(a) and aggregate state coverage. Original Figure 7(b) stratum values are unavailable.")

    fig, axes = plt.subplots(1, 2, figsize=(11, 5))
    rows = d["policy"]
    labels = [r["controller"] for r in rows]
    pairs(axes[0], labels, [r["pre_success_pct"] for r in rows], [r["real_success_pct"] for r in rows])
    pairs(axes[1], labels, [r["pre_silent_pct"] for r in rows], [r["real_silent_pct"] for r in rows], "Silent error (%)")
    axes[0].set_title("(a) Controller success rates")
    axes[1].set_title("(b) Controller silent errors")
    save(fig,"figure08_controllers","Figure 8: manuscript percentages; run-level records unavailable.")

    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.5))
    for key,color,label in [("pre_success_pct",colors[0],"PRE"),("real_success_pct",colors[1],"REAL")]:
        axes[0].scatter([r["reads"] for r in d["inspection"] if r[key] is not None],
                        [r[key] for r in d["inspection"] if r[key] is not None],c=color,label=label,s=55)
    axes[0].axhline(56.8,color="#888888",linestyle=":",label="Read-3 REAL (56.8)")
    axes[0].set_xticks([0,1,3,6])
    axes[0].set_xlabel("Maximum task-state reads")
    axes[0].set_ylabel("Task success (%)")
    axes[0].set_ylim(50,80)
    axes[0].legend(frameon=False,fontsize=8)
    axes[0].set_title("(a) Numerically reported inspection rates")
    axes[0].text(.03,.96,"PRE at 1 read: not reported",transform=axes[0].transAxes,va="top",fontsize=8)
    x = [r["actions"] for r in d["resource"]]
    y = [r["interaction_pp"] for r in d["resource"]]
    axes[1].plot(x,y,marker="o",color=colors[3])
    for xx,yy in zip(x,y):
        axes[1].annotate(f"{yy:.1f}",(xx,yy),xytext=(0,7),textcoords="offset points",ha="center")
    axes[1].set_xticks(x)
    axes[1].set_ylim(0,28)
    axes[1].set_xlabel("Action budget (tokens/time scale jointly)")
    axes[1].set_ylabel("Inspect-3 vs Retry-1 interaction (pp)")
    axes[1].set_title("(b) Text-reported resource interactions")
    save(fig,"figure09_available_values","Available Figure 9(a) rates and text-reported interactions. The full Figure 9(b) controller curves cannot be reconstructed from printed numeric data.")

    fig,axes = plt.subplots(1,2,figsize=(10.5,4.6))
    rows=d["model_policy_advantage"]
    ypos=np.arange(len(rows))
    for key,color,shift,label in [("pre_pp",colors[0],-.15,"PRE"),("real_pp",colors[1],.15,"REAL")]:
        axes[0].scatter([r[key] for r in rows],ypos+shift,c=color,label=label)
        for i,r in enumerate(rows):
            axes[0].annotate(f"{r[key]:+.1f}",(r[key],i+shift),xytext=(5,0),textcoords="offset points",va="center",fontsize=9)
    axes[0].set_yticks(ypos,[r["model"] for r in rows])
    axes[0].invert_yaxis()
    axes[0].set_ylim(len(rows)+.4,-.6)
    axes[0].axvline(0,c="#999999",lw=.8)
    axes[0].set_xlim(-7,18)
    axes[0].set_xlabel("Inspect-3 minus Retry-1 (pp)")
    axes[0].legend(loc="lower right",fontsize=8,frameon=False)
    axes[0].set_title("(a) Protocol-specific policy advantage")
    paired=d["replication"]["pairing_real"]
    values=[100*v/720 for v in paired.values()]
    axes[1].bar(["Both\nsucceed","Retry-1\nonly","Inspect-3\nonly","Both\nfail"],values,color=colors)
    for i,(v,n) in enumerate(zip(values,paired.values())):
        axes[1].text(i,v+1,f"{v:.1f}%\n({n:,})",ha="center",fontsize=9)
    axes[1].set_ylim(0,70)
    axes[1].set_ylabel("Matched continuations (%)")
    axes[1].set_title("(b) Held-out REAL outcomes")
    save(fig,"figure10_transfer","Figure 10, printed model contrasts and exact held-out matched counts.")

    fig,ax=plt.subplots(figsize=(9.3,5.2))
    rows=d["categories"]
    pairs(ax,[r["category"] for r in rows],[r["pre_success_pct"] for r in rows],[r["real_success_pct"] for r in rows])
    ax.set_title("Table 5: state-category success rates")
    save(fig,"table05_category_rates","Visualization of Table 5. Build/cache is the category with higher REAL success.")

    document = ['<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>AfterState aggregate reproduction</title><style>body{max-width:1100px;margin:40px auto;padding:0 22px;color:#213047;font:16px/1.65 system-ui,sans-serif}h1{line-height:1.2}article{margin:38px 0;border-top:1px solid #ddd;padding-top:22px}svg{width:100%;height:auto}aside{padding:16px;background:#fff4da;border-left:4px solid #c28a26}code{font-size:14px}footer{color:#566}</style>',
                '<h1>AfterState: aggregate reproduction</h1><aside>Figures use manuscript aggregate data. Original run records, site snapshots, confidence intervals and some plotted values are unavailable.</aside>']
    for item in generated:
        svg=(output/(item["name"]+".svg")).read_text(encoding="utf-8")
        svg=svg[svg.index('<svg'):]
        document += ['<article><h2>'+html.escape(item["name"])+"</h2><p>"+html.escape(item["caption"])+"</p>",svg,"</article>"]
    document += ['<footer>Exact transcriptions: data/paper/aggregates.json. Arithmetic checks: reports/paper-audit.json. Missing entries remain null.</footer></html>']
    (output/"index.html").write_text("\n".join(document),encoding="utf-8")
    (output/"figure-manifest.json").write_text(json.dumps(generated,indent=2),encoding="utf-8")
    return generated
