# Tools reference

## read_las_file

`read_las_file(path: str) -> LASSummary`

Returns header-level metadata: well name, operator, depth start/stop/step,
depth units, list of curves with their units and ranges, total depth points,
and a gap summary. Does not return raw curve data.

## summarize_las_curves

`summarize_las_curves(path: str) -> CurveSummary`

Per-curve statistics: min, max, mean, stddev, gap percentage, units. Useful
for quick QC.

## read_las_curve

`read_las_curve(path: str, curve_name: str, depth_start: float | None = None, depth_stop: float | None = None) -> CurveData`

Returns depths and values for one curve. Default is a downsampled view
capped at 500 samples. Pass `depth_start` and `depth_stop` together to get
every point inside that interval with no downsampling.

## qc_a_well_log (prompt)

Walks Claude through a standard well-log QC pass. Invoke from the prompt
picker in your host application.

## compare_well_logs

`compare_well_logs(path_a: str, path_b: str) -> ComparisonReport`

Compares two LAS files. Reports common curves, curves unique to each file,
depth-range overlap, per-curve unit consistency, and human-readable issue
flags suitable for the LLM to quote. Strict case-sensitive matching on
mnemonics and units; a normalisation layer can be added later if
real-world use turns up false mismatches.

## convert_units

`convert_units(value: float, from_unit: str, to_unit: str) -> float`

Converts a value between supported petroleum units. Strict case-sensitive
matching: `Ft` is not `ft`. Raises `UnitConversionError` for unsupported
pairs. Call `list_supported_units` rather than relying on this list staying
current:

- Length: ft <-> m
- Pressure: psi <-> kPa, psi <-> bar
- Volume: bbl <-> m3
- Temperature: degF <-> degC
- Permeability: mD <-> m2

## list_supported_units

`list_supported_units() -> SupportedUnits`

Every pair `convert_units` accepts, both directions, each labelled with its
physical quantity. Derived from the same table the converter uses, so it
cannot advertise a pair that would then be rejected.

Prefer this over guessing at unit spellings: matching is strict and
case-sensitive, and a wrong guess costs a failed tool call.
