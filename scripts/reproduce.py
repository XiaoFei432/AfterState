import argparse
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument("--skip-demo",action="store_true")
args=parser.parse_args()
commands=[
    ["-m","afterstate","audit"],
    ["-m","afterstate","figures"],
    ["-m","pytest","-q"],
]
if not args.skip_demo:
    commands.append(["-m","afterstate","demo","--output","runs/demo"])
for command in commands:
    print("Running:"," ".join(["python"]+command),flush=True)
    subprocess.run([sys.executable]+command,cwd=ROOT,check=True)
print("Completed. Paper aggregate reproduction and new demo results have distinct provenance.")
