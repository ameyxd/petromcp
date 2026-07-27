import json
from pathlib import Path

import pytest

from petromcp import cli


@pytest.fixture
def isolated_user_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    cfg_path = tmp_path / "config.json"
    monkeypatch.setattr(cli, "USER_CONFIG_PATH", cfg_path)
    return cfg_path


def test_config_init_creates_default(isolated_user_config: Path) -> None:
    rc = cli.main(["config", "init"])
    assert rc == 0
    assert isolated_user_config.exists()
    data = json.loads(isolated_user_config.read_text())
    assert data["allowed_paths"] == []
    assert data["logging"]["enabled"] is True


def test_config_init_errors_when_file_exists(isolated_user_config: Path) -> None:
    isolated_user_config.write_text(json.dumps({"allowed_paths": ["/x"]}))
    rc = cli.main(["config", "init"])
    assert rc == 2
    assert json.loads(isolated_user_config.read_text())["allowed_paths"] == ["/x"]


def test_config_show_prints_default_when_missing(
    isolated_user_config: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rc = cli.main(["config", "show"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "allowed_paths" in out


def test_config_show_prints_existing_file(
    isolated_user_config: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    isolated_user_config.write_text(json.dumps({"allowed_paths": ["/data"]}))
    rc = cli.main(["config", "show"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "/data" in out


def test_config_add_path_appends(isolated_user_config: Path) -> None:
    rc = cli.main(["config", "add-path", str(isolated_user_config.parent)])
    assert rc == 0
    data = json.loads(isolated_user_config.read_text())
    assert str(isolated_user_config.parent) in data["allowed_paths"]


def test_config_add_path_is_idempotent(isolated_user_config: Path) -> None:
    target = str(isolated_user_config.parent)
    cli.main(["config", "add-path", target])
    rc = cli.main(["config", "add-path", target])
    assert rc == 0
    data = json.loads(isolated_user_config.read_text())
    assert data["allowed_paths"].count(target) == 1


def test_config_remove_path_removes(isolated_user_config: Path) -> None:
    target = str(isolated_user_config.parent)
    cli.main(["config", "add-path", target])
    rc = cli.main(["config", "remove-path", target])
    assert rc == 0
    data = json.loads(isolated_user_config.read_text())
    assert target not in data["allowed_paths"]


def test_config_remove_path_idempotent_when_absent(isolated_user_config: Path) -> None:
    isolated_user_config.write_text(json.dumps({"allowed_paths": []}))
    rc = cli.main(["config", "remove-path", "/nope"])
    assert rc == 0


class TestConfigValidationHappensAtTheCli:
    """There used to be two config readers: the CLI's raw `json.loads` and
    `config.load_config`, which validates. A bad config written via the CLI
    therefore failed at server start, where the host swallows the traceback and
    reports only that the server would not launch."""

    def test_malformed_json_fails_at_the_cli(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        cfg = tmp_path / "config.json"
        cfg.write_text("{not json at all")
        monkeypatch.setattr(cli, "USER_CONFIG_PATH", cfg)
        with pytest.raises(SystemExit, match="not valid JSON"):
            cli.main(["config", "add-path", str(tmp_path)])

    def test_a_json_array_is_rejected(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        cfg = tmp_path / "config.json"
        cfg.write_text("[]")
        monkeypatch.setattr(cli, "USER_CONFIG_PATH", cfg)
        with pytest.raises(SystemExit, match="JSON object"):
            cli.main(["config", "add-path", str(tmp_path)])

    def test_a_value_the_server_would_reject_fails_at_the_cli(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`allowed_paths` must be a list of strings. A number there used to be
        written happily and only rejected at startup."""
        cfg = tmp_path / "config.json"
        cfg.write_text(json.dumps({"allowed_paths": [42]}))
        monkeypatch.setattr(cli, "USER_CONFIG_PATH", cfg)
        with pytest.raises(SystemExit, match="not a usable config"):
            cli.main(["config", "add-path", str(tmp_path)])

    def test_a_negative_rotation_size_fails_at_the_cli(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        cfg = tmp_path / "config.json"
        cfg.write_text(json.dumps({"allowed_paths": [], "logging": {"max_bytes": -1}}))
        monkeypatch.setattr(cli, "USER_CONFIG_PATH", cfg)
        with pytest.raises(SystemExit, match="not a usable config"):
            cli.main(["config", "add-path", str(tmp_path)])

    def test_a_valid_config_still_round_trips(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        cfg = tmp_path / "config.json"
        monkeypatch.setattr(cli, "USER_CONFIG_PATH", cfg)
        assert cli.main(["config", "init"]) == 0
        assert cli.main(["config", "add-path", str(tmp_path)]) == 0
        data = json.loads(cfg.read_text())
        assert str(tmp_path.resolve()) in data["allowed_paths"]

    def test_unknown_keys_are_preserved_rather_than_dropped(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A future config key written by a newer petromcp must survive an
        `add-path` from an older one."""
        cfg = tmp_path / "config.json"
        cfg.write_text(json.dumps({"allowed_paths": [], "future_option": "keep me"}))
        monkeypatch.setattr(cli, "USER_CONFIG_PATH", cfg)
        cli.main(["config", "add-path", str(tmp_path)])
        assert json.loads(cfg.read_text())["future_option"] == "keep me"
