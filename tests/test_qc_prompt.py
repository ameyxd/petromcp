"""The QC prompt.

Two properties matter. First, the prompt must state the thresholds the config
actually holds — a prompt quoting one bound while the config holds another is
drift that is invisible and wrong toward false confidence. Second, it must not
present uncalibrated defaults as authority, because no practitioner has
reviewed them.

The curve set is also asserted here because it was wrong: the prompt described
an open-hole triple combo as GR/RHOB/NPHI/DT. A triple combo is resistivity +
density + neutron with gamma ray; sonic makes it a quad combo. So the original
both demanded a curve that is not part of the suite and omitted the measurement
that defines it.
"""

from __future__ import annotations

import pytest

from petromcp.config import QCThresholds
from petromcp.prompts.qc_a_well_log import PROMPT_NAME, PROMPT_TEMPLATE, build_prompt


def _flat(text: str) -> str:
    """Collapse wrapping, so a phrase test is not a line-width test.

    The prompt is hard-wrapped, so `"let the user judge"` appears as
    `"let the user\njudge"`. Asserting on the raw string makes the test fail
    when someone reflows a paragraph, which tells you nothing.
    """
    return " ".join(text.split())


def test_prompt_name_is_stable() -> None:
    """Hosts surface prompts by name; renaming breaks saved workflows."""
    assert PROMPT_NAME == "qc_a_well_log"


class TestTheCurveSetMatchesTheConventionalSuite:
    def test_resistivity_is_expected(self) -> None:
        """The measurement that defines a triple combo, and which the original
        prompt omitted entirely."""
        assert "resistivity" in _flat(build_prompt()).lower()

    def test_several_resistivity_mnemonics_are_offered(self) -> None:
        """Contractors name resistivity differently; demanding one mnemonic
        would flag a complete log as incomplete."""
        prompt = build_prompt()
        assert sum(m in prompt for m in ("RESD", "RT", "ILD")) >= 2

    def test_density_and_neutron_are_expected(self) -> None:
        prompt = build_prompt()
        assert "RHOB" in prompt and "NPHI" in prompt

    def test_sonic_is_described_as_optional_not_missing(self) -> None:
        """Adding sonic makes it a quad combo, so its absence is not a defect."""
        prompt = _flat(build_prompt())
        assert "DT" in prompt
        assert "quad combo" in prompt

    def test_defaults_do_not_list_sonic_as_expected(self) -> None:
        assert "DT" not in QCThresholds().expected_curves


class TestThePromptStatesTheConfiguredThresholds:
    def test_default_density_bounds_appear(self) -> None:
        prompt = build_prompt()
        assert "1.8" in prompt and "3.0" in prompt

    def test_custom_density_bounds_appear_instead(self) -> None:
        """The whole reason the prompt is built rather than hardcoded."""
        prompt = build_prompt(QCThresholds(rhob_min=2.0, rhob_max=2.9))
        assert "2.0-2.9" in prompt
        assert "1.8-3.0" not in prompt

    def test_custom_gap_threshold_appears(self) -> None:
        prompt = build_prompt(QCThresholds(gap_percentage_warn=5.0))
        assert "5.0%" in prompt

    def test_custom_curve_set_appears(self) -> None:
        prompt = build_prompt(QCThresholds(expected_curves=["GR", "PEF"]))
        assert "PEF" in prompt

    def test_no_threshold_is_hardcoded_past_the_config(self) -> None:
        """Every number in the prompt should move when the config moves. If a
        default value survives a fully-changed config, it was hardcoded."""
        changed = QCThresholds(
            rhob_min=1.0,
            rhob_max=9.9,
            nphi_min=0.1,
            nphi_max=0.9,
            gap_percentage_warn=42.0,
        )
        prompt = build_prompt(changed)
        for stale in ("1.8", "3.0", "1.0%"):
            assert stale not in prompt, f"hardcoded default {stale!r} survived"


class TestThePromptDoesNotOverclaim:
    def test_says_the_bounds_are_not_calibrated(self) -> None:
        """No practitioner has reviewed these. Presenting them as authority is
        the risk the SME review was meant to remove."""
        assert "not calibrated" in _flat(build_prompt()).lower()

    def test_points_at_the_config_so_they_can_be_changed(self) -> None:
        assert "config.json" in build_prompt()

    def test_tells_the_model_not_to_declare_a_definitive_defect(self) -> None:
        assert "let the user judge" in _flat(build_prompt()).lower()

    def test_still_asks_for_evidence(self) -> None:
        """The original prompt's best property: quote the output behind a flag."""
        assert "quoting the tool output" in _flat(build_prompt())

    def test_still_forbids_dumping_raw_values(self) -> None:
        assert "Do not dump raw curve values" in _flat(build_prompt())


def test_module_level_template_matches_the_default_render() -> None:
    assert build_prompt() == PROMPT_TEMPLATE


def test_the_server_serves_the_configured_prompt() -> None:
    import asyncio

    from petromcp.server import build_app

    prompts = asyncio.run(build_app(allowed_paths=[]).get_prompts())
    assert PROMPT_NAME in prompts


@pytest.mark.parametrize(
    "field", ["rhob_min", "rhob_max", "nphi_min", "nphi_max", "gap_percentage_warn"]
)
def test_every_threshold_is_configurable(field: str) -> None:
    """A threshold that cannot be overridden is a threshold that needs an SME."""
    assert field in QCThresholds.model_fields
