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
