import argparse
from pathlib import Path
import xml.etree.ElementTree as ET

parser=argparse.ArgumentParser()
parser.add_argument("report",type=Path)
args=parser.parse_args()
tree=ET.parse(args.report)
for suite in tree.iter("testsuite"):
    if int(suite.get("failures","0")) or int(suite.get("errors","0")):
        raise SystemExit("Do not release a failing report; preserve diagnostics locally and fix failures.")
    suite.attrib.pop("hostname",None)
    suite.attrib.pop("timestamp",None)
for skipped in tree.iter("skipped"):
    skipped.text=skipped.get("message","Skipped by platform condition")
tree.write(args.report,encoding="utf-8",xml_declaration=True)
