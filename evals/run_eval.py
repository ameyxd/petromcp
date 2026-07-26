"""Local eval runner.

Generates synthetic wells, calls petromcp tools against them, and checks the
tools surfaced the defects the generator recorded.

Expectations are not written in the scenario file. The generator emits a
ground-truth manifest beside each LAS, and the runner asserts against that, so
a change to the generator cannot leave a stale expectation behind. What the
scenario file declares is *which* wells to build and which check to run.

The manifest's honesty is guaranteed elsewhere: `tests/test_generator.py`
reads each written LAS back and verifies every recorded defect is really in
the file. Without that test this runner would be asserting against a claim
rather than a fact.
"""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

import numpy as np
import yaml

from examples.sample_data.facies import BIT_SIZE
from examples.sample_data.generate import generate, truth_path_for
from examples.sample_data.truth import WellTruth
from examples.sample_data.wells import CURVE_UNITS, WELLS
from petromcp.models.las import CurveSummary
from petromcp.models.shared import DepthRange
from petromcp.tools.compare import compare_well_logs
from petromcp.tools.las import read_las_curve, summarize_las_curves


def _build(well: str, work_dir: Path) -> tuple[Path, WellTruth]:
    las_path, _ = generate(WELLS[well], work_dir / f"{well}.las")
    truth = WellTruth.model_validate_json(truth_path_for(las_path).read_text())
    return las_path, truth


def _check_single_well_qc(well: str, work_dir: Path) -> list[str]:
    """Assert every recorded defect is visible through the tools."""
    las_path, truth = _build(well, work_dir)
    roots = [work_dir]
    summary: CurveSummary = summarize_las_curves(str(las_path), roots)
    by_name = {c.name: c for c in summary.curves}
    failures: list[str] = []

    if summary.well_name != truth.well:
        failures.append(f"well name {summary.well_name!r} != manifest {truth.well!r}")

    for name in truth.curves:
        if name not in by_name:
            failures.append(f"curve {name} in manifest but not reported by the tool")

    for d in truth.defects:
        if d.kind == "null_gap":
            curve = by_name.get(d.curve or "")
            if curve is None:
                failures.append(f"null_gap curve {d.curve} missing from summary")
            elif curve.gap_percentage <= 0.0:
                failures.append(
                    f"null_gap on {d.curve} at {d.top}-{d.base} not reflected in "
                    f"gap_percentage ({curve.gap_percentage}%)"
                )

        elif d.kind == "washout":
            cali = by_name.get("CALI")
            if cali is None or cali.max is None:
                failures.append("washout recorded but CALI not summarised")
            elif cali.max <= BIT_SIZE:
                failures.append(
                    f"washout at {d.top}-{d.base} not visible: CALI max "
                    f"{cali.max} <= bit size {BIT_SIZE}"
                )

        elif d.kind == "spike":
            curve = by_name.get(d.curve or "")
            if curve is None or curve.max is None:
                failures.append(f"spike curve {d.curve} missing from summary")
            elif d.magnitude is not None and curve.max < d.magnitude * 0.99:
                failures.append(
                    f"spike of {d.magnitude} on {d.curve} not visible: max {curve.max}"
                )

        elif d.kind == "flatline":
            # Not visible in a whole-curve summary, so read the interval itself.
            #
            # Pass the range explicitly rather than reading the whole curve and
            # slicing. An unscoped read downsamples to 500 samples, which both
            # thins a short interval down to a handful of points and — once any
            # null is filtered out of the values — shifts every later value
            # onto the wrong depth.
            if d.curve and d.top is not None and d.base is not None:
                data = read_las_curve(
                    str(las_path),
                    d.curve,
                    depth_range=DepthRange(start=d.top, stop=d.base),
                    allowed_paths=roots,
                )
                inside = np.asarray(
                    [v for v in data.values if v is not None], dtype=float
                )
                if inside.size < 2:
                    # Silently skipping here would let the scenario pass while
                    # checking nothing.
                    failures.append(
                        f"flatline on {d.curve} at {d.top}-{d.base}: only "
                        f"{inside.size} non-null sample(s), cannot verify"
                    )
                elif float(np.ptp(inside)) > 1e-9:
                    failures.append(
                        f"flatline on {d.curve} at {d.top}-{d.base} is not flat "
                        f"(spread {float(np.ptp(inside)):.6g} over {inside.size} samples)"
                    )

        elif d.kind == "unit_mismatch":
            curve = by_name.get(d.curve or "")
            if curve is None:
                failures.append(f"unit_mismatch curve {d.curve} missing from summary")
            elif curve.units != d.declared_unit:
                failures.append(
                    f"{d.curve} units {curve.units!r} != declared {d.declared_unit!r}"
                )

        elif d.kind == "missing_curve":
            if d.curve in by_name:
                failures.append(f"{d.curve} recorded missing but present in summary")

    return failures


def _check_compare_wells(well_a: str, well_b: str, work_dir: Path) -> list[str]:
    """Assert cross-well findings match what the two manifests imply."""
    path_a, truth_a = _build(well_a, work_dir)
    path_b, truth_b = _build(well_b, work_dir)
    report = compare_well_logs(str(path_a), str(path_b), [work_dir])
    failures: list[str] = []

    expected_only_a = sorted(set(truth_a.curves) - set(truth_b.curves))
    expected_only_b = sorted(set(truth_b.curves) - set(truth_a.curves))
    if report.unique_to_a != expected_only_a:
        failures.append(f"unique_to_a {report.unique_to_a} != expected {expected_only_a}")
    if report.unique_to_b != expected_only_b:
        failures.append(f"unique_to_b {report.unique_to_b} != expected {expected_only_b}")

    lo = max(truth_a.depth.start, truth_b.depth.start)
    hi = min(truth_a.depth.stop, truth_b.depth.stop)
    if report.depth_overlap is None:
        failures.append(f"no depth overlap reported; expected {lo}-{hi}")
    else:
        if abs(report.depth_overlap.start - lo) > 1e-6:
            failures.append(f"overlap start {report.depth_overlap.start} != {lo}")
        if abs(report.depth_overlap.stop - hi) > 1e-6:
            failures.append(f"overlap stop {report.depth_overlap.stop} != {hi}")

    # Every injected unit_mismatch on a shared curve must be flagged.
    for truth in (truth_a, truth_b):
        for d in truth.defects_for("unit_mismatch"):
            if d.curve not in report.common_curves:
                continue
            mismatched = {u.name for u in report.unit_diffs if not u.units_match}
            if d.curve not in mismatched:
                failures.append(
                    f"unit mismatch on {d.curve} "
                    f"({d.declared_unit} vs {CURVE_UNITS.get(d.curve or '')}) not flagged"
                )

    return failures


def run_scenario(scenario_path: Path, work_dir: Path) -> tuple[bool, list[str]]:
    scenario = yaml.safe_load(scenario_path.read_text())
    kind = scenario["kind"]
    spec = scenario["input"]

    if kind == "single_well_qc":
        failures = _check_single_well_qc(spec["well"], work_dir)
    elif kind == "compare_wells":
        failures = _check_compare_wells(spec["well_a"], spec["well_b"], work_dir)
    else:
        failures = [f"unknown scenario kind {kind!r}"]

    return (len(failures) == 0, failures)


def write_report(out_dir: Path, scenario_id: str, passed: bool, failures: list[str]) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{date.today().isoformat()}-{scenario_id}.md"
    lines = [f"# Eval {scenario_id}", "", f"Status: {'PASS' if passed else 'FAIL'}", ""]
    if failures:
        lines.append("## Failures")
        lines.extend(f"- {f}" for f in failures)
    else:
        lines.append("Every defect recorded in the generator manifest was surfaced.")
    out.write_text("\n".join(lines) + "\n")
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--scenario", action="append", default=None)
    p.add_argument("--all", action="store_true", help="run every scenario")
    p.add_argument("--work-dir", default=".eval_tmp")
    p.add_argument("--results", default="evals/results")
    args = p.parse_args(argv)

    scenario_dir = Path(__file__).parent / "scenarios"
    if args.all or not args.scenario:
        scenarios = sorted(scenario_dir.glob("*.yaml"))
    else:
        scenarios = [Path(s) for s in args.scenario]

    work = Path(args.work_dir).resolve()
    work.mkdir(parents=True, exist_ok=True)

    exit_code = 0
    for scenario_path in scenarios:
        scenario_id = yaml.safe_load(scenario_path.read_text())["id"]
        passed, failures = run_scenario(scenario_path, work)
        out = write_report(Path(args.results), scenario_id, passed, failures)
        print(f"{'PASS' if passed else 'FAIL'} {scenario_id} -> {out}")
        for f in failures:
            print(f"  - {f}")
        if not passed:
            exit_code = 1
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
