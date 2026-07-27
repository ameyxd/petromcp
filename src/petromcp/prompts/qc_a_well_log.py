"""qc_a_well_log: walks Claude through standard well-log QC.

The prompt is built from `QCThresholds` rather than hardcoding numbers, so the
thresholds a user configures are the thresholds the model is told to apply. A
prompt that stated one bound while the config held another would be the worst
kind of drift: invisible, and wrong in the direction of false confidence.

It also states plainly that the thresholds are conventional defaults rather
than calibrated values. petromcp cannot know the basin, and a QC pass that
presents an uncalibrated bound as authority is more dangerous than one that
says what it is.
"""

from __future__ import annotations

from petromcp.config import QCThresholds

PROMPT_NAME = "qc_a_well_log"


def build_prompt(qc: QCThresholds | None = None) -> str:
    """Render the QC prompt for a set of thresholds."""
    t = qc or QCThresholds()
    resistivity = ", ".join(t.resistivity_mnemonics[:4])
    expected = ", ".join(t.expected_curves)
    optional = ", ".join(t.optional_curves)
    hole = ", ".join(t.hole_condition_curves)

    return f"""\
You are reviewing a well log. Use the petromcp tools to:

1. Call `read_las_file` to identify the well, depth range, and curves present.
2. Call `summarize_las_curves` for min, max, mean, stddev, and gap percentage
   on each curve.
3. Flag anything unusual, quoting the tool output that justifies each flag:

   - **Missing curves.** An open-hole triple combo measures three families:
     resistivity, bulk density, and neutron porosity, with gamma ray for
     correlation. Expect {expected}, plus a resistivity curve — contractors
     name it differently, so accept any of {resistivity} or a similar
     mnemonic. Expect {hole} for hole condition.
     Sonic ({optional}) is *not* part of a triple combo; a suite with sonic is
     a quad combo, so its absence is worth a note rather than a flag.
   - **Gaps** above {t.gap_percentage_warn}% on any curve.
   - **Values outside plausible bounds**: bulk density outside
     {t.rhob_min}-{t.rhob_max} g/cm3, neutron porosity outside
     {t.nphi_min}-{t.nphi_max} v/v, negative gamma ray, or a caliper reading
     far from bit size.
   - **Unit mismatches**, especially a porosity curve declared in percent while
     carrying fractions, or the reverse.

4. If the user named a depth interval, use `read_las_curve` over that interval
   for the actual values. Otherwise stay at the summary level and say that
   detail is available on request.

State clearly that these bounds are conventional defaults, not calibrated to
any basin, and that they live in `~/.petromcp/config.json` under `qc` if the
user wants to change them. Do not present a threshold breach as a definitive
defect — report what the data does and what bound it crossed, and let the user
judge.

Be concise. Do not dump raw curve values into the conversation.
"""


#: Rendered with the defaults, for callers that want the plain string.
PROMPT_TEMPLATE = build_prompt()
