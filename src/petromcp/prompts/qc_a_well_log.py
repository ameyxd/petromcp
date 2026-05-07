"""qc_a_well_log: walks Claude through standard well-log QC."""

PROMPT_NAME = "qc_a_well_log"

PROMPT_TEMPLATE = """\
You are reviewing a well log. Use the petromcp tools to:

1. Call `read_las_file` to identify the well, depth range, and curves present.
2. Call `summarize_las_curves` to surface min/max/mean/stddev and the gap
   percentage on each curve.
3. Flag anything unusual: missing curves a complete log normally has
   (GR, RHOB, NPHI, DT for an open-hole triple combo; CALI for hole condition),
   gaps above 1%, values outside expected ranges (e.g. RHOB outside 1.8-3.0,
   GR negative, CALI wildly variable), and unit mismatches.
4. If the user gave you a depth interval of interest, use `read_las_curve`
   with that interval to pull the actual values; otherwise stay at the summary
   level and note that detail is available on request.

Be concise. Do not dump raw values into the conversation. Quote the petromcp
tool outputs that justify each flag you raise.
"""
