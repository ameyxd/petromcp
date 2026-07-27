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

## DLIS

DLIS (RP66 v1) is structurally richer than LAS. One physical file holds several
*logical files* (logging runs), each holding several *frames*, each holding
*channels*. A channel name is unique only within a frame, so every DLIS output
below reports the frame and logical file a channel came from — without those the
result looks addressable but is not.

### read_dlis_file

`read_dlis_file(path: str) -> DLISSummary`

Structure and metadata: every logical file, its frames, each frame's index type
and depth range, and channel counts. Never returns channel values.

Start here. A real DLIS can carry hundreds of channels across several frames,
and reading them to summarise would cost more than the answer is worth.

A file containing only a Storage Unit Label is valid and empty; it reports zero
logical files rather than failing. Anything actually corrupt — truncated, a
different format, a damaged body — raises with the file named.

### list_dlis_channels

`list_dlis_channels(path: str, frame: str | None = None) -> ChannelListing`

Every channel with its frame, logical file, units, long name, and sample count.
Pass `frame` to narrow a large file; an unknown frame name raises and lists the
frames that exist.

Sample counts, not statistics. Computing statistics means reading every curve,
which is exactly the cost `read_dlis_file` and this tool exist to avoid.

### read_dlis_channel

`read_dlis_channel(path, channel, frame=None, logical_file=None, depth_start=None, depth_stop=None) -> DLISChannelData`

Values for one channel, with its index. Defaults to a 500-sample downsample;
pass `depth_start` and `depth_stop` together for every sample in an interval.
Passing one without the other is an error, not a silent fallback.

`frame` and `logical_file` are optional when the channel name is unambiguous.
When it is not, the call **fails and names every candidate** rather than
choosing one — the values differ between frames, so a guess is a wrong answer
dressed as a right one. Pass `frame` on the retry.
