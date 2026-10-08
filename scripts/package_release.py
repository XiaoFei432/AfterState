import argparse
import hashlib
from pathlib import Path
import re
import zipfile

ROOT=Path(__file__).resolve().parents[1]
EXCLUDED={".git",".venv","__pycache__",".pytest_cache","work","runs","build","dist"}
TEXT_SUFFIXES={".py",".md",".json",".jsonl",".csv",".txt",".html",".svg",".yml",".toml",".xml"}


def release_files():
    return sorted(p for p in ROOT.rglob("*") if p.is_file()
                  and not (set(p.relative_to(ROOT).parts)&EXCLUDED)
                  and not any(part.endswith(".egg-info") for part in p.relative_to(ROOT).parts)
                  and p.suffix not in {".pyc",".pyo",".zip"}
                  and p.name!="MANIFEST.sha256")


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",type=Path,default=ROOT.parent/"afterstate-artifact.zip")
    args=parser.parse_args()
    files=release_files()
    patterns=[r"[A-Za-z]:[\\/]+(?:Users|Documents and Settings)[\\/]+",r"/"+r"home/[^/\s]+/",r"gh[pousr]_[A-Za-z0-9]{20,}",r"sk-[A-Za-z0-9]{24,}"]
    for p in files:
        if p.suffix in TEXT_SUFFIXES:
            content=p.read_text(encoding="utf-8")
            for pattern in patterns:
                if re.search(pattern,content,re.IGNORECASE):
                    raise SystemExit("Potential personal path or credential in "+p.relative_to(ROOT).as_posix())
    manifest=ROOT/"MANIFEST.sha256"
    manifest.write_text("".join(hashlib.sha256(p.read_bytes()).hexdigest()+"  "+p.relative_to(ROOT).as_posix()+"\n" for p in files),encoding="utf-8")
    files.append(manifest)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(args.output,"w",zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for p in files:
            info=zipfile.ZipInfo("afterstate/"+p.relative_to(ROOT).as_posix(),(2026,1,1,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=0o100644 << 16
            archive.writestr(info,p.read_bytes())
    print(f"Packaged {len(files)} files ({args.output.stat().st_size:,} bytes)")
    print("SHA256:",hashlib.sha256(args.output.read_bytes()).hexdigest())

if __name__=="__main__":
    main()
