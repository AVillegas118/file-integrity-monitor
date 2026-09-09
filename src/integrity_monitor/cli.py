"""Interfaz de terminal del monitor de integridad."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .core import IntegrityError, compare, load_baseline, save_baseline, scan_directory
from .models import ChangeReport


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="integrity-monitor",
        description="Detecta cambios en archivos mediante una línea base SHA-256.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    create = subparsers.add_parser("create", help="crear una línea base")
    create.add_argument("directory", type=Path, help="directorio que se observará")
    create.add_argument("--baseline", type=Path, required=True, help="archivo JSON de salida")

    check = subparsers.add_parser("check", help="comparar con una línea base")
    check.add_argument("directory", type=Path, help="directorio que se observará")
    check.add_argument("--baseline", type=Path, required=True, help="línea base existente")
    check.add_argument("--json", action="store_true", help="mostrar el resultado como JSON")
    return parser


def format_text(report: ChangeReport) -> str:
    if not report.has_changes:
        return "Sin cambios: los archivos coinciden con la línea base."

    lines = ["Cambios detectados:"]
    for label, paths in (
        ("NUEVO", report.added),
        ("MODIFICADO", report.modified),
        ("ELIMINADO", report.deleted),
    ):
        lines.extend(f"  [{label}] {path}" for path in paths)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    baseline_path = args.baseline.absolute()

    try:
        if args.command == "create":
            records = scan_directory(args.directory, excluded={baseline_path})
            save_baseline(baseline_path, records)
            print(f"Línea base creada: {len(records)} archivo(s) en {baseline_path}")
            return 0

        baseline = load_baseline(baseline_path)
        current = scan_directory(args.directory, excluded={baseline_path})
        report = compare(baseline, current)
        print(json.dumps(report.to_dict(), indent=2) if args.json else format_text(report))
        return 2 if report.has_changes else 0
    except IntegrityError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
