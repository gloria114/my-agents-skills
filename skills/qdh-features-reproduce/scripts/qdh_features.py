"""Portable command line entry point for qdh feature reproduction."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Sequence

from skill_paths import (
    REQUIRED_SKILL_FOLDERS,
    dependency_paths,
    identity,
    skills_root,
    source_hashes,
)


def selftest() -> dict[str, Any]:
    from feature_build import worker_pool_selftest
    from feature_runtime import selftest as runtime_selftest
    from factor_excel import selftest as excel_selftest
    from factor_indicator import selftest as indicator_selftest
    from feature_publish import transaction_selftest

    dependencies = dependency_paths()
    wh6 = subprocess.run(
        [sys.executable, "-B", "-X", "utf8", str(dependencies["wh6_selftest.py"])],
        cwd=str(Path(os.environ.get("TEMP", Path.cwd()))),
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
    )
    if wh6.returncode != 0:
        raise RuntimeError(f"WH6 sibling selftest failed: {wh6.stderr[-2000:]}")
    runtime = runtime_selftest()
    indicator = indicator_selftest()
    excel = excel_selftest()
    # Executable instructions must not depend on an agent-specific home layout.
    forbidden = (
        "." + "codex",
        "." + "claude",
        "." + "cc-switch",
        "." + "gemini",
        "." + "opencode",
        ":" + "\\" + "Users" + "\\",
        ":" + "/" + "Users" + "/",
        ":" + "\\" + "qdh",
        ":" + "/" + "qdh",
        "USER" + "PROFILE",
        "CODEX" + "_HOME",
    )
    violations: list[str] = []
    bundle_root = skills_root()
    inspected: list[Path] = []
    for folder in REQUIRED_SKILL_FOLDERS:
        skill_root = bundle_root / folder
        inspected.append(skill_root / "SKILL.md")
        inspected.extend(sorted((skill_root / "scripts").glob("*.py")))
        inspected.extend(sorted((skill_root / "references").glob("*.md")))
    for path in inspected:
        text = path.read_text(encoding="utf-8")
        if any(value.lower() in text.lower() for value in forbidden):
            violations.append(str(path.relative_to(bundle_root)))
    if violations:
        raise RuntimeError(f"agent-specific path literal: {violations}")
    return {
        "status": "PASS", "qdh_write_count": 0, "path_portable": True,
        "platform": "windows",
        "identity": identity(), "source_semantic_sha256": __import__("wh6_common").canonical_json_sha256(source_hashes()),
        "wh6_selftest": "PASS", "indicator_selftest": indicator.get("status", "PASS"),
        "excel_selftest": excel.get("status", "PASS"), "combined_runtime": runtime,
        "worker_pool": worker_pool_selftest(), "publisher_transaction": transaction_selftest(),
    }


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    sub = root.add_subparsers(dest="command", required=True)
    sub.add_parser("selftest")
    preflight = sub.add_parser("preflight")
    preflight.add_argument("--qdh-root", required=True); preflight.add_argument("--ch-url", required=True); preflight.add_argument("--workers", type=int, default=4)
    build = sub.add_parser("build")
    build.add_argument("--qdh-root", required=True); build.add_argument("--run-root", required=True); build.add_argument("--ch-url", required=True); build.add_argument("--workers", type=int, default=4)
    build.add_argument("--symbols"); build.add_argument("--timeframes"); build.add_argument("--resume", action="store_true")
    for name in ("validate", "finalize"):
        item = sub.add_parser(name)
        item.add_argument("--qdh-root", required=True); item.add_argument("--run-root", required=True); item.add_argument("--ch-url", required=True); item.add_argument("--workers", type=int, default=4)
        if name == "validate": item.add_argument("--mode", choices=("structure", "full"), default="structure")
    for name in ("publish", "verify-live", "recover"):
        item = sub.add_parser(name)
        item.add_argument("--qdh-root", required=True); item.add_argument("--run-root", required=True); item.add_argument("--ch-url", required=True); item.add_argument("--workers", type=int, default=4)
        if name == "publish":
            item.add_argument("--execute", action="store_true"); item.add_argument("--confirm-run-id"); item.add_argument("--confirm-ready-sha256")
        if name == "recover":
            item.add_argument("--confirm-run-id", required=True); item.add_argument("--confirm-ready-sha256", required=True)
    return root


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.command == "selftest":
        print(json.dumps(selftest(), ensure_ascii=False, indent=2)); return 0
    if args.command == "preflight":
        from feature_build import preflight
        print(json.dumps(preflight(args.qdh_root, args.ch_url, args.workers), ensure_ascii=False, indent=2)); return 0
    if args.command == "build":
        from feature_build import command_build
        return command_build(args)
    if args.command in ("validate", "finalize"):
        from feature_validate import command_finalize, command_validate
        return command_validate(args) if args.command == "validate" else command_finalize(args)
    from feature_publish import command_publish, command_recover, command_verify
    if args.command == "publish":
        return command_publish(args)
    if args.command == "verify-live":
        return command_verify(args)
    return command_recover(args)


if __name__ == "__main__":
    raise SystemExit(main())
