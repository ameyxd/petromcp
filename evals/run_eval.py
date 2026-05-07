"""Local eval runner. Generates synthetic data, calls petromcp tools, checks
results against the scenario's `expected` block. Writes a markdown report.
"""

from __future__ import annotations

import argparse
import importlib
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from petromcp.tools.las import summarize_las_curves


def _resolve_callable(spec: str) -> Any:
    module_name, attr = spec.split(":")
    return getattr(importlib.import_module(module_name), attr)


def run_scenario(scenario_path: Path, work_dir: Path) -> tuple[bool, list[str]]:
    scenario = yaml.safe_load(scenario_path.read_text())
    generator = _resolve_callable(scenario["input"]["generator"])
    seed = int(scenario["input"]["seed"])
    las_path = work_dir / "well.las"
    generator(las_path, seed=seed)

    summary = summarize_las_curves(str(las_path), [work_dir])
    by_name = {c.name: c for c in summary.curves}

    failures: list[str] = []
    for spec in scenario["expected"]["curves"]:
        name = spec["name"]
        c = by_name.get(name)
        if c is None:
            failures.append(f"missing curve {name}")
            continue
        if "units" in spec and c.units != spec["units"]:
            failures.append(f"{name}: units {c.units!r} != expected {spec['units']!r}")
        if "gap_percentage_max" in spec and c.gap_percentage > spec["gap_percentage_max"]:
            failures.append(
                f"{name}: gap {c.gap_percentage}% > max {spec['gap_percentage_max']}%"
            )
        if "gap_percentage_min" in spec and c.gap_percentage < spec["gap_percentage_min"]:
            failures.append(
                f"{name}: gap {c.gap_percentage}% < min {spec['gap_percentage_min']}%"
            )
    return (len(failures) == 0, failures)


def write_report(out_dir: Path, scenario_id: str, passed: bool, failures: list[str]) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{date.today().isoformat()}-{scenario_id}.md"
    lines = [f"# Eval {scenario_id}", "", f"Status: {'PASS' if passed else 'FAIL'}", ""]
    if failures:
        lines.append("## Failures")
        lines.extend(f"- {f}" for f in failures)
    out.write_text("\n".join(lines))
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--scenario", default="evals/scenarios/01_well_log_qc.yaml")
    p.add_argument("--work-dir", default=".eval_tmp")
    p.add_argument("--results", default="evals/results")
    args = p.parse_args(argv)

    work = Path(args.work_dir).resolve()
    work.mkdir(parents=True, exist_ok=True)
    scenario_path = Path(args.scenario)
    scenario_id = yaml.safe_load(scenario_path.read_text())["id"]

    passed, failures = run_scenario(scenario_path, work)
    out = write_report(Path(args.results), scenario_id, passed, failures)
    print(f"{'PASS' if passed else 'FAIL'} -> {out}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
