from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys


def dump(value, path=None):
    text = json.dumps(value, indent=2, ensure_ascii=True)
    if path:
        p=Path(path)
        p.parent.mkdir(parents=True,exist_ok=True)
        p.write_text(text+"\n",encoding="utf-8")
    else:
        print(text)


def main(argv=None):
    parser=argparse.ArgumentParser(description="AfterState aggregate artifact and executable reference protocol")
    sub=parser.add_subparsers(dest="command",required=True)
    for name in ["audit","figures"]:
        p=sub.add_parser(name)
        p.add_argument("--root",type=Path,default=Path.cwd(),help="artifact repository root")
        p.add_argument("--output",type=Path,default=Path("reports/paper-audit.json") if name=="audit" else Path("reports/figures"))
    p=sub.add_parser("demo",help="run six NEW controlled fixtures; no model/API required")
    p.add_argument("--output",type=Path,default=Path("runs/demo"))
    p.add_argument("--categories",nargs="+",choices=["package","venv","patch","database","build","generation"])
    p.add_argument("--mechanical",type=int,default=5)
    p.add_argument("--reference",type=int,default=3)
    p.add_argument("--repeats",type=int,default=1)
    p=sub.add_parser("analyze",help="analyze supplied linked run-level JSONL")
    p.add_argument("records",type=Path)
    p.add_argument("--output",type=Path)
    p.add_argument("--bootstrap",type=int,default=10000)
    p.add_argument("--seed",type=int,default=1729)
    p=sub.add_parser("select",help="freeze POLICY choices then evaluate disjoint REPLICATION")
    p.add_argument("policy",type=Path)
    p.add_argument("replication",type=Path)
    p.add_argument("--tie-order",nargs="+",required=True)
    p.add_argument("--output",type=Path)
    p.add_argument("--bootstrap",type=int,default=10000)
    p=sub.add_parser("sample",help="deterministic hash ordering of task IDs, not cohort recreation")
    p.add_argument("ids",type=Path,help="one canonical task ID per line")
    p.add_argument("--salt",default="pe-fse-v2")
    p.add_argument("--count",type=int,required=True)
    p.add_argument("--output",type=Path)
    p=sub.add_parser("run",help="paired controlled-fixture experiment with a custom adapter")
    p.add_argument("--adapter-command",type=Path,help="JSON file containing adapter executable argv")
    p.add_argument("--actions-file",type=Path,help="JSON list of scripted actions; no model involved")
    p.add_argument("--categories",nargs="+",default=["patch","database"],choices=["package","venv","patch","database","build","generation"])
    p.add_argument("--controllers",nargs="+",default=["Native"],choices=["Native","Retry-1","Inspect-1","Inspect-3","Inspect-6","Read-3","Reflexion","Self-Refine"])
    p.add_argument("--actions",type=int,default=40)
    p.add_argument("--repeats",type=int,default=3)
    p.add_argument("--feedback",choices=["raw","neutral","terse"],default="raw")
    p.add_argument("--configuration",default="custom-reference-adapter")
    p.add_argument("--output",type=Path,default=Path("runs/paired"))
    args=parser.parse_args(argv)
    try:
        if args.command=="audit":
            from .paper import audit
            result=audit(args.root)
            dump(result,args.output)
            print(f"{sum(c['passed'] for c in result['checks'])}/{len(result['checks'])} arithmetic checks passed; {args.output}")
            if not result["passed"]:
                return sys.exit(1)
        elif args.command=="figures":
            from .paper import figures
            generated=figures(args.root,args.output)
            print(f"Generated {len(generated)} figure groups (PNG/SVG/PDF) and self-contained index.html")
        elif args.command=="demo":
            from .demo import run_demo
            from .fixtures import CATEGORIES
            dump(run_demo(args.output,args.categories or CATEGORIES,args.mechanical,args.reference,args.repeats))
        elif args.command=="analyze":
            from .analysis import load_records,analyze
            dump(analyze(load_records(args.records),samples=args.bootstrap,seed=args.seed),args.output)
        elif args.command=="select":
            from .analysis import load_records,select_and_evaluate
            dump(select_and_evaluate(load_records(args.policy),load_records(args.replication),args.tie_order,args.bootstrap),args.output)
        elif args.command=="run":
            from .controllers import ScriptedAdapter,StdioAdapter,Budget
            from .experiments import run_pairs
            if bool(args.adapter_command)==bool(args.actions_file):
                raise ValueError("Choose exactly one of --adapter-command or --actions-file")
            path=args.adapter_command or args.actions_file
            value=json.loads(path.read_text(encoding="utf-8"))
            factory=(lambda: StdioAdapter(value)) if args.adapter_command else (lambda: ScriptedAdapter(value))
            records=run_pairs(factory,args.output,args.categories,args.controllers,args.repeats,
                              Budget.scaled(args.actions),args.feedback,args.configuration)
            print(f"Recorded {len(records)} NEW continuations to {args.output / 'runs.jsonl'}")
        else:
            import hashlib
            ids=args.ids.read_text(encoding="utf-8").splitlines()
            if len(set(ids))!=len(ids) or any(not x for x in ids) or not 0 < args.count <= len(ids):
                raise ValueError("IDs must be unique/nonempty; count must fit input")

            ordered=sorted(ids,key=lambda x: hashlib.sha256((args.salt+"\0"+x).encode()).hexdigest())
            dump({"salt":args.salt,"serialization":"salt + NUL + canonical_id", "selected":ordered[:args.count],
                  "note":"Hash-order helper only. Repository coverage/exclusions require original manifests."},args.output)
    except (ValueError,OSError,KeyError) as exc:
        parser.exit(2,f"afterstate: {exc}\n")
