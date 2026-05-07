import hashlib
from pathlib import Path

from examples.sample_data.generate import generate_well_01


def _digest(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def test_generator_is_deterministic(tmp_path: Path) -> None:
    a = tmp_path / "a.las"
    b = tmp_path / "b.las"
    generate_well_01(a, seed=42)
    generate_well_01(b, seed=42)
    assert _digest(a) == _digest(b)


def test_generator_writes_expected_curves(tmp_path: Path) -> None:
    p = tmp_path / "w.las"
    generate_well_01(p, seed=42)
    text = p.read_text()
    for mnemonic in ("GR", "RHOB", "NPHI", "DT", "CALI"):
        # lasio writes curve headers as "MNEM.unit" or "MNEM  .unit" (padded)
        assert any(
            line.lstrip().startswith(mnemonic) and "." in line
            for line in text.splitlines()
        )
