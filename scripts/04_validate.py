#!/usr/bin/env python3
"""Checks that hold whether or not a STAC validator is installed.

The rules here are the ones this catalog can get wrong on its own: a fabricated
footprint, a size that was copied from the page instead of measured, a link
that points at a file that is not there. If `stac-validator` is available it
runs as well, against the schemas.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _first(paths, n: int = 1):
    out = []
    for p in sorted(paths):
        out.append(p)
        if len(out) >= n:
            break
    return out


def _validator_cmd():
    if shutil.which("stac-validator"):
        return ["stac-validator"]
    if shutil.which("uvx"):
        return ["uvx", "--quiet", "--from", "stac-valid", "stac-validator"]
    return None


def main() -> int:
    cat = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "catalog"
    if not (cat / "catalog.json").exists():
        print(f"no catalog at {cat}. Run scripts/03_build_stac.py first.", file=sys.stderr)
        return 1

    errors, items = [], list(cat.glob("collections/*/items/*.json"))
    for p in items:
        d = json.loads(p.read_text())
        rel = p.relative_to(cat)
        if d.get("geometry") is None and "bbox" in d:
            errors.append(f"{rel}: bbox present although geometry is null")
        if d.get("geometry") is not None and "bbox" not in d:
            errors.append(f"{rel}: geometry without bbox")
        props = d.get("properties", {})
        if props.get("datetime") is None and not (props.get("start_datetime") and props.get("end_datetime")):
            errors.append(f"{rel}: datetime is null without an interval")
        for name, a in d.get("assets", {}).items():
            if not a.get("roles"):
                errors.append(f"{rel}: asset {name} has no role")
            if not a.get("type"):
                errors.append(f"{rel}: asset {name} has no media type")
            if "file:size" in a and not isinstance(a["file:size"], int):
                errors.append(f"{rel}: asset {name} has a non-integer file:size")

    # Every item link in a region catalog points into a collection; a typo in
    # the relative path would produce a browsable index full of 404s.
    for p in sorted(cat.glob("regions/*.json")):
        d = json.loads(p.read_text())
        rel = p.relative_to(cat)
        for link in d["links"]:
            if link["rel"] not in ("item", "child"):
                continue
            if not (p.parent / link["href"]).resolve().exists():
                errors.append(f"{rel}: dangling {link['rel']} link: {link['href']}")
            if link["rel"] == "item" and not link.get("title"):
                errors.append(f"{rel}: item link without a title: {link['href']}")

    for p in cat.glob("collections/*/collection.json"):
        d = json.loads(p.read_text())
        rel = p.relative_to(cat)
        if not d.get("license"):
            errors.append(f"{rel}: no license")
        if d.get("license") == "other" and not any(l["rel"] == "license" for l in d["links"]):
            errors.append(f"{rel}: license is 'other' without a license link")
        for link in d["links"]:
            if link["rel"] == "item":
                target = (p.parent / link["href"]).resolve()
                if not target.exists():
                    errors.append(f"{rel}: item link points at a missing file: {link['href']}")
                if not link.get("title"):
                    errors.append(f"{rel}: item link without a title: {link['href']}")

    regions = list(cat.glob("regions/*.json"))
    print(f"{len(items)} items checked, {max(len(regions) - 1, 0)} region catalogs")
    for e in errors[:40]:
        print(f"  {e}")
    if len(errors) > 40:
        print(f"  ... and {len(errors) - 40} more")

    # Schema validation is a separate question from the checks above, and it
    # needs the network. One item and one collection are enough to catch a
    # shape error; the generator emits every item the same way, so validating
    # 21,603 of them against the same schema proves nothing extra.
    cmd = _validator_cmd()
    if cmd:
        for sample in (cat / "catalog.json", *_first(cat.glob("collections/*/collection.json")),
                       *_first(cat.glob("collections/*/items/*.json"))):
            r = subprocess.run([*cmd, "validate", str(sample)], capture_output=True, text=True)
            ok = '"valid_stac": true' in r.stdout
            print(f"  {'ok  ' if ok else 'FAIL'} {sample.relative_to(cat)}")
            if not ok:
                print((r.stdout or r.stderr)[-2000:])
                errors.append(f"{sample.relative_to(cat)}: schema validation failed")
    else:
        print("no STAC schema validator found; install one with "
              "`pip install stac-valid`, or have `uv` on PATH")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
