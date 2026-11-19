#!/usr/bin/env python3
"""CompatiCheck: checks de compatibilidad Windows/Linux.

Genera un reporte JSON y un resumen Markdown. No falla el build: los hallazgos
se reportan para que el equipo los priorice y corrija.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {".git", "reports", "__pycache__", ".venv", "venv"}
TEXT_EXT = {".py", ".md", ".txt", ".json", ".yml", ".yaml", ".sh", ".toml", ".cfg", ".ini"}
STDLIB = {
    "os", "sys", "re", "json", "math", "pathlib", "subprocess", "typing", "collections",
    "argparse", "shutil", "datetime", "time", "random", "stat", "io", "csv", "functools",
    "itertools", "dataclasses", "unittest", "logging", "platform", "socket", "hashlib",
}
LOCAL_MODULES = {"utils", "config_loader"}


def iter_files():
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        yield path


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def check_paths():
    findings = []
    settings = ROOT / "config" / "settings.json"
    if not settings.exists():
        return findings

    def walk(value, key=""):
        if isinstance(value, dict):
            for k, v in value.items():
                walk(v, k)
        elif isinstance(value, list):
            for item in value:
                walk(item, key)
        elif isinstance(value, str):
            if re.search(r"[A-Za-z]:\\|\\\\", value):
                findings.append({
                    "category": "rutas",
                    "file": rel(settings),
                    "detail": f'"{key}" usa una ruta con separadores Windows: {value}',
                })

    walk(json.loads(settings.read_text(encoding="utf-8")))
    return findings


def check_case():
    findings = []
    src = ROOT / "src"
    if not src.exists():
        return findings
    exact_names = {p.name for p in src.glob("*.py")}
    for py in src.glob("*.py"):
        text = py.read_text(encoding="utf-8", errors="replace")
        pattern = r"^\s*(?:from\s+([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)\s+import|import\s+([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*))"
        for match in re.finditer(pattern, text, re.M):
            module = (match.group(1) or match.group(2) or "").split(".")[0]
            if not module or module in STDLIB:
                continue
            if f"{module}.py" in exact_names:
                continue
            candidates = [p.name for p in src.glob("*.py") if p.stem.lower() == module.lower()]
            if candidates:
                findings.append({
                    "category": "mayúsculas",
                    "file": rel(py),
                    "detail": f"importa '{module}' pero el archivo es '{candidates[0]}'",
                })
    return findings


def check_crlf():
    findings = []
    for path in iter_files():
        if path.suffix.lower() not in {".txt", ".md"}:
            continue
        data = path.read_bytes()
        if b"\r\n" in data:
            findings.append({
                "category": "saltos de línea",
                "file": rel(path),
                "detail": "el archivo usa CRLF; se espera LF para Linux",
            })
    return findings


def check_permissions():
    findings = []
    scripts = sorted((ROOT / "scripts").glob("*.sh"))
    if not scripts:
        return findings
    try:
        out = subprocess.run(
            ["git", "ls-files", "-s", "scripts/*.sh"],
            cwd=ROOT, capture_output=True, text=True, check=False,
        ).stdout
        modes = {}
        for line in out.splitlines():
            parts = line.split()
            if len(parts) >= 4:
                modes[parts[3]] = parts[0]
        for script in scripts:
            mode = modes.get(f"scripts/{script.name}", "")
            if mode == "100644":
                findings.append({
                    "category": "permisos",
                    "file": rel(script),
                    "detail": "el script no tiene bit de ejecución (modo 100644)",
                })
            elif not mode and not os.access(script, os.X_OK):
                findings.append({
                    "category": "permisos",
                    "file": rel(script),
                    "detail": "el script no es ejecutable en este entorno",
                })
    except FileNotFoundError:
        for script in scripts:
            if not os.access(script, os.X_OK):
                findings.append({
                    "category": "permisos",
                    "file": rel(script),
                    "detail": "el script no es ejecutable en este entorno",
                })
    return findings


def check_dependencies():
    findings = []
    req = ROOT / "requirements.txt"
    declared = set()
    if req.exists():
        for line in req.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            name = re.split(r"[<>=!~\[]", line, maxsplit=1)[0].strip().lower()
            if name:
                declared.add(name)
    src = ROOT / "src"
    if not src.exists():
        return findings
    for py in src.glob("*.py"):
        text = py.read_text(encoding="utf-8", errors="replace")
        pattern = r"^\s*(?:from\s+([A-Za-z_]\w*)|import\s+([A-Za-z_]\w*))"
        for match in re.finditer(pattern, text, re.M):
            module = (match.group(1) or match.group(2) or "").lower()
            if not module or module in STDLIB or module in LOCAL_MODULES:
                continue
            if module not in declared:
                findings.append({
                    "category": "dependencias",
                    "file": rel(py),
                    "detail": f"importa '{module}' pero no está en requirements.txt",
                })
    return findings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", default="reports/report.json")
    args = parser.parse_args()

    checks = [check_paths, check_case, check_crlf, check_permissions, check_dependencies]
    findings = []
    for check in checks:
        findings.extend(check())

    counts = Counter(f["category"] for f in findings)
    order = ["rutas", "mayúsculas", "saltos de línea", "permisos", "dependencias"]
    env_name = "Windows" if os.name == "nt" else "Linux"

    print("CompatiCheck · reporte de compatibilidad")
    print(f"Entorno: {env_name}")
    print(f"Hallazgos: {len(findings)}")
    for f in findings:
        print(f"  - [{f['category']}] {f['file']}: {f['detail']}")

    report_path = ROOT / args.report
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps({
        "environment": env_name,
        "findings": findings,
        "counts": dict(counts),
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        f"## CompatiCheck · compat-check ({env_name})",
        "",
        "| Categoría | Hallazgos |",
        "|---|---:|",
    ]
    for category in order:
        lines.append(f"| {category.capitalize()} | {counts.get(category, 0)} |")
    lines.append(f"| **Total** | **{len(findings)}** |")
    lines.append("")
    lines.append("> Los hallazgos se reportan para priorización; el build no se bloquea.")
    (ROOT / "reports" / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Reporte: {report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
