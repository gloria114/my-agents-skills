"""Portable discovery and identity locks for sibling factor skills."""

from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPT_DIR.parent

REQUIRED_SKILL_FOLDERS = (
    "wh6-factor-reproduce",
    "indicator-py-factor-reproduce",
    "excel-factor-reproduce",
    "tv-factor-reproduce",
    "qdh-features-reproduce",
)


LOCKED_DEPENDENCIES: dict[str, tuple[str, str]] = {
    "wh6_candidate.py": (
        "wh6-factor-reproduce/scripts/wh6_candidate.py",
        "849c460a50864e05744211abe3e269b2e7e957312ee92ed2c432fbef4f89514e",
    ),
    "wh6_formulas_v2.py": (
        "wh6-factor-reproduce/scripts/wh6_formulas_v2.py",
        "e71c1d3be8c43c0c5e1ec0ac9fc204b471d07e527292b37571c08bc489439d8a",
    ),
    "wh6_primitives.py": (
        "wh6-factor-reproduce/scripts/wh6_primitives.py",
        "9313b87f57138b9775ad502f8970d91bd81439e02f8056242561d2a822e39061",
    ),
    "wh6_common.py": (
        "wh6-factor-reproduce/scripts/wh6_common.py",
        "8c6d496d391aa978c9d7d33ff1523b6532a89e0e0cae40c7df2fadaffeb46353",
    ),
    "wh6_selftest.py": (
        "wh6-factor-reproduce/scripts/wh6_selftest.py",
        "be1220eb0159fb8ed6dbf72c9601a3684aa65bf8ef40f38f7b0d293ec5a5136d",
    ),
    "factor_indicator.py": (
        "indicator-py-factor-reproduce/scripts/factor_indicator.py",
        "817b6531f19e33c5dea3307afca56314a8396f01034b03f53205e87ac49dc2d1",
    ),
    "indicator_contract.json": (
        "indicator-py-factor-reproduce/references/indicator-py-locked-59-contract.json",
        "633bf61bf71e7ef8d75cea3e65621a69177ce20bd3d856f72ed9ea777d3e9097",
    ),
    "factor_excel.py": (
        "excel-factor-reproduce/scripts/factor_excel.py",
        "6792fd6d0c394a214012edc4a758b76342e30e91658752312c3cab1475e414e3",
    ),
    "excel_contract.json": (
        "excel-factor-reproduce/references/excel-locked-66-contract.json",
        "b88be9f680c17fa3e7375c8df9ead1b7e95953a7127f2813f10b1cca00dd58e2",
    ),
    "factor_tv.py": (
        "tv-factor-reproduce/scripts/factor_tv.py",
        "7e0e77b7735165459c1b94db46393cb5f9c206cdf7391530b3af4c5f5e2b390d",
    ),
    "tv_contract.json": (
        "tv-factor-reproduce/references/tv-locked-142-contract.json",
        "b89b95a4a2eaa7110fe2b1813767d0b73f051ddc21982a67701ace03eb79192c",
    ),
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def skills_root() -> Path:
    """Resolve the shared five-skill directory without an agent-home convention."""

    override = os.environ.get("QDH_FEATURE_SKILLS_ROOT")
    raw = Path(override).expanduser() if override else SKILL_ROOT.parent
    if not raw.is_absolute():
        raise RuntimeError("skills root must be absolute")
    root = raw.resolve(strict=True)
    if not root.is_dir():
        raise RuntimeError(f"skills root is not a directory: {root}")
    missing = [name for name in REQUIRED_SKILL_FOLDERS if not (root / name).is_dir()]
    if missing:
        raise RuntimeError(
            "shared skills root must contain the complete five-skill bundle; "
            f"missing={missing}"
        )
    if (root / "qdh-features-reproduce").resolve(strict=True) != SKILL_ROOT:
        raise RuntimeError(
            "QDH_FEATURE_SKILLS_ROOT points to a different orchestrator generation"
        )
    return root


def dependency_paths(*, verify_hashes: bool = True) -> dict[str, Path]:
    root = skills_root()
    result: dict[str, Path] = {}
    for label, (relative, expected) in LOCKED_DEPENDENCIES.items():
        path = root / Path(relative)
        if not path.is_file():
            raise RuntimeError(f"required sibling skill artifact missing: {relative}")
        actual = sha256_file(path)
        if verify_hashes and actual != expected:
            raise RuntimeError(
                f"locked sibling artifact changed: {relative}: "
                f"expected={expected}, actual={actual}"
            )
        result[label] = path
    return result


def activate_import_paths() -> dict[str, Path]:
    paths = dependency_paths()
    directories = [
        paths["wh6_candidate.py"].parent,
        paths["factor_indicator.py"].parent,
        paths["factor_excel.py"].parent,
        paths["factor_tv.py"].parent,
        SCRIPT_DIR,
    ]
    for directory in reversed(directories):
        value = str(directory)
        if value not in sys.path:
            sys.path.insert(0, value)
    return paths


def source_files() -> dict[str, Path]:
    """Return every executable source sealed into a run manifest."""

    result = dependency_paths()
    for name in (
        "skill_paths.py",
        "feature_runtime.py",
        "feature_build.py",
        "feature_validate.py",
        "feature_publish.py",
        "qdh_features.py",
    ):
        path = SCRIPT_DIR / name
        if not path.is_file():
            raise RuntimeError(f"orchestration source missing: {path}")
        result[name] = path
    return result


def source_hashes() -> dict[str, str]:
    return {label: sha256_file(path) for label, path in source_files().items()}


def identity() -> dict[str, Any]:
    paths = dependency_paths()
    return {
        "skills_root": str(skills_root()),
        "path_portable": True,
        "platform": "windows",
        "discovery": "QDH_FEATURE_SKILLS_ROOT or installed sibling directory",
        "absolute_user_path_dependencies": False,
        "locked_dependencies": {
            label: {
                "relative_path": LOCKED_DEPENDENCIES[label][0],
                "sha256": sha256_file(path),
            }
            for label, path in paths.items()
        },
    }
