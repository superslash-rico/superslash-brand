#!/usr/bin/env python3
"""Read portable brand configuration and verify original asset hashes."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]


def load_brand(root: Path | str | None = None):
    root = Path(root or SKILL_ROOT).resolve()
    data = json.loads((root / "assets/brand.json").read_text(encoding="utf-8"))
    if data.get("schema_version") != 1:
        raise ValueError("Unsupported brand configuration version")
    return data


def asset_path(relative: str, root: Path | str | None = None) -> Path:
    base = (Path(root or SKILL_ROOT) / "assets").resolve()
    path = (base / relative).resolve()
    if not path.is_relative_to(base):
        raise ValueError("Asset path leaves the brand package")
    if not path.is_file():
        raise FileNotFoundError(path)
    return path


def verify_assets(root: Path | str | None = None):
    root = Path(root or SKILL_ROOT).resolve()
    manifest = json.loads((root / "assets/asset-manifest.json").read_text(encoding="utf-8"))
    errors = []
    for entry in manifest["files"]:
        try:
            path = asset_path(entry["path"], root)
            if path.stat().st_size != entry["bytes"]:
                errors.append(f"Size changed: {entry['path']}")
            if hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
                errors.append(f"Hash changed: {entry['path']}")
        except (ValueError, FileNotFoundError) as exc:
            errors.append(str(exc))
    return {"ok": not errors, "checked": len(manifest["files"]), "errors": errors}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    result = verify_assets() if args.verify else {"skill_root": str(SKILL_ROOT), "brand": load_brand()}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.verify and not result["ok"]:
        raise SystemExit(1)
