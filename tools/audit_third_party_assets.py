from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import re
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "1.0"
REQUIREMENT = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)(.*)$")
MEDIA_EXTENSIONS = {
    ".gif", ".jpeg", ".jpg", ".mp3", ".mp4", ".otf", ".pdf", ".png",
    ".pptx", ".svg", ".ttf", ".webp", ".woff", ".woff2", ".xlsx",
}


def normalize_name(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value).lower()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_manifest(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _parse_requirements(path: Path, manifest_path: str, scope: str) -> set[tuple[str, ...]]:
    declarations: set[tuple[str, ...]] = set()
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or line.startswith(("-r", "--requirement")):
            continue
        match = REQUIREMENT.fullmatch(line)
        if match is None:
            raise ValueError(f"unsupported requirement declaration in {manifest_path}: {line}")
        name, specifier = match.groups()
        declarations.add((
            "python", normalize_name(name), manifest_path, scope, specifier.strip()
        ))
    return declarations


def actual_declarations(root: Path, manifest: dict[str, Any]) -> set[tuple[str, ...]]:
    declarations: set[tuple[str, ...]] = set()
    for source in manifest["dependency_manifests"]:
        relative = source["path"]
        path = root / relative
        if source["ecosystem"] == "python":
            declarations.update(_parse_requirements(path, relative, source["scope"]))
            continue
        package = json.loads(path.read_text(encoding="utf-8"))
        for section, scope in (("dependencies", "runtime"), ("devDependencies", "development")):
            for name, specifier in package.get(section, {}).items():
                declarations.add(("npm", name, relative, scope, specifier))
    return declarations


def inventoried_declarations(manifest: dict[str, Any]) -> set[tuple[str, ...]]:
    declarations: set[tuple[str, ...]] = set()
    for dependency in manifest["direct_dependencies"]:
        ecosystem = dependency["ecosystem"]
        name = normalize_name(dependency["name"]) if ecosystem == "python" else dependency["name"]
        for declaration in dependency["declarations"]:
            declarations.add((
                ecosystem, name, declaration["manifest"], declaration["scope"],
                declaration["specifier"],
            ))
    return declarations


def tracked_files(root: Path) -> list[str]:
    completed = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=root, capture_output=True, check=True,
    )
    values = [
        value.decode("utf-8").replace("\\", "/")
        for value in completed.stdout.split(b"\0") if value
    ]
    return [value for value in values if (root / value).is_file()]


def _matches(path: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatchcase(path, pattern) for pattern in patterns)


def _installed_node_licenses(
    root: Path, frontend_root: str
) -> tuple[Counter[str], dict[str, set[str]], list[str]]:
    store = root / frontend_root / "node_modules" / ".pnpm"
    if not store.is_dir():
        return Counter(), {}, [f"installed dependency store is missing: {store}"]
    packages: set[tuple[str, str, str]] = set()
    errors: list[str] = []
    for store_entry in store.iterdir():
        package_root = store_entry / "node_modules"
        if not package_root.is_dir():
            continue
        candidates: list[Path] = []
        for child in package_root.iterdir():
            if child.name.startswith("@") and child.is_dir():
                candidates.extend(grandchild for grandchild in child.iterdir())
            else:
                candidates.append(child)
        for candidate in candidates:
            metadata_path = candidate / "package.json"
            if not metadata_path.is_file():
                continue
            try:
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                continue
            name = metadata.get("name")
            version = metadata.get("version")
            license_value = metadata.get("license")
            if isinstance(license_value, dict):
                license_value = license_value.get("type")
            if not isinstance(license_value, str) or not license_value.strip():
                errors.append(f"installed package lacks a license expression: {name}@{version}")
                continue
            packages.add((str(name), str(version), license_value.strip()))
    by_name: dict[str, set[str]] = {}
    for name, _, license_value in packages:
        by_name.setdefault(name, set()).add(license_value)
    return Counter(license_value for _, _, license_value in packages), by_name, errors


def audit_manifest(
    root: Path, manifest: dict[str, Any], *, check_installed: bool = False
) -> dict[str, Any]:
    errors: list[str] = []
    if manifest.get("schema_version") != SCHEMA_VERSION:
        errors.append("unsupported asset inventory schema_version")
    required_top = {
        "project", "copyright_holder", "repository_license", "dependency_manifests",
        "direct_dependencies", "lockfiles", "assets", "coverage_patterns",
        "installed_node_review",
    }
    missing_top = sorted(required_top - set(manifest))
    if missing_top:
        errors.append("manifest is missing fields: " + ", ".join(missing_top))
        return {"status": "failed", "errors": errors}

    notice = (root / "NOTICE").read_text(encoding="utf-8")
    expected_notice = f"Copyright 2026 {manifest['copyright_holder']}"
    if expected_notice not in notice:
        errors.append(f"NOTICE must contain: {expected_notice}")
    if "contributors" in notice.lower():
        errors.append("NOTICE still uses an ambiguous contributors copyright holder")
    license_text = (root / "LICENSE").read_text(encoding="utf-8")
    if manifest["repository_license"] != "Apache-2.0" or "Apache License" not in license_text:
        errors.append("repository LICENSE and inventory must both identify Apache-2.0")

    dependency_ids: set[tuple[str, str]] = set()
    for dependency in manifest["direct_dependencies"]:
        key = (dependency.get("ecosystem", ""), normalize_name(dependency.get("name", "")))
        if key in dependency_ids:
            errors.append(f"duplicate direct dependency: {key[0]}:{key[1]}")
        dependency_ids.add(key)
        if not dependency.get("license"):
            errors.append(f"dependency has no license expression: {key[0]}:{key[1]}")
        if not str(dependency.get("source_url", "")).startswith("https://"):
            errors.append(f"dependency has no HTTPS upstream source: {key[0]}:{key[1]}")
        if not dependency.get("declarations"):
            errors.append(f"dependency has no manifest declaration: {key[0]}:{key[1]}")
    try:
        actual = actual_declarations(root, manifest)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        errors.append(str(exc))
        actual = set()
    inventoried = inventoried_declarations(manifest)
    for declaration in sorted(actual - inventoried):
        errors.append("dependency declaration is not inventoried: " + repr(declaration))
    for declaration in sorted(inventoried - actual):
        errors.append("inventoried dependency declaration is stale: " + repr(declaration))

    for lockfile in manifest["lockfiles"]:
        path = root / lockfile["path"]
        if not path.is_file():
            errors.append(f"lockfile is missing: {lockfile['path']}")
        elif sha256_file(path) != lockfile["sha256"]:
            errors.append(f"lockfile hash changed; refresh license review: {lockfile['path']}")

    asset_ids: set[str] = set()
    asset_patterns: list[str] = []
    for asset in manifest["assets"]:
        asset_id = asset.get("asset_id")
        if not isinstance(asset_id, str) or not asset_id or asset_id in asset_ids:
            errors.append("asset IDs must be non-empty and unique")
        asset_ids.add(str(asset_id))
        patterns = asset.get("path_patterns")
        if not isinstance(patterns, list):
            errors.append(f"asset {asset_id} path_patterns must be a list")
            patterns = []
        asset_patterns.extend(patterns)
        for field in ("category", "origin", "rights_status", "license_or_terms", "redistribution"):
            if not isinstance(asset.get(field), str) or not asset[field].strip():
                errors.append(f"asset {asset_id} requires {field}")

    try:
        tracked = tracked_files(root)
    except (OSError, subprocess.CalledProcessError) as exc:
        errors.append(f"cannot enumerate tracked files: {exc}")
        tracked = []
    must_cover = {
        path for path in tracked
        if _matches(path, manifest["coverage_patterns"])
        or Path(path).suffix.lower() in MEDIA_EXTENSIONS
    }
    for path in sorted(must_cover):
        if not _matches(path, asset_patterns):
            errors.append(f"repository asset is not inventoried: {path}")
    for asset in manifest["assets"]:
        if asset.get("expected_matches", True) and not any(
            _matches(path, asset["path_patterns"]) for path in tracked
        ):
            errors.append(f"asset pattern matches no tracked file: {asset['asset_id']}")

    installed_summary: dict[str, int] | None = None
    allowed = set(manifest["installed_node_review"]["allowed_license_expressions"])
    conditional = {
        item.get("expression")
        for item in manifest["installed_node_review"].get("conditional_obligations", [])
        if isinstance(item, dict) and isinstance(item.get("condition"), str)
        and item["condition"].strip()
    }
    for expression in allowed:
        if "LGPL" in expression and expression not in conditional:
            errors.append(f"reviewed reciprocal license lacks a distribution condition: {expression}")
    if check_installed:
        installed, installed_by_name, installed_errors = _installed_node_licenses(
            root, manifest["installed_node_review"]["frontend_root"]
        )
        errors.extend(installed_errors)
        for expression in sorted(set(installed) - allowed):
            errors.append(f"installed dependency license is not reviewed: {expression}")
        for dependency in manifest["direct_dependencies"]:
            if dependency["ecosystem"] != "npm":
                continue
            observed = installed_by_name.get(dependency["name"])
            if not observed:
                errors.append(f"direct npm dependency is not installed: {dependency['name']}")
            elif dependency["license"] not in observed:
                errors.append(
                    f"direct npm dependency license changed: {dependency['name']} "
                    f"expected {dependency['license']}, observed {sorted(observed)}"
                )
        installed_summary = dict(sorted(installed.items()))

    return {
        "status": "passed" if not errors else "failed",
        "project": manifest["project"],
        "direct_dependency_count": len(dependency_ids),
        "tracked_asset_count": len(must_cover),
        "lockfile_count": len(manifest["lockfiles"]),
        "installed_license_counts": installed_summary,
        "limitations": [
            "Metadata audit is not legal advice or proof of upstream title.",
            "Re-run the installed audit and preserve upstream notices before shipping dependency binaries.",
        ],
        "errors": errors,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit direct dependencies and repository assets")
    parser.add_argument(
        "--manifest", type=Path, default=Path("config/third_party_assets.json")
    )
    parser.add_argument("--check-installed", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(__file__).resolve().parents[1]
    manifest_path = args.manifest if args.manifest.is_absolute() else root / args.manifest
    result = audit_manifest(root, load_manifest(manifest_path), check_installed=args.check_installed)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
