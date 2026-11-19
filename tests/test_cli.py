"""Command line (degfw), called in-process."""

import json

import pytest

from degradation_fw import available
from degradation_fw.cli import main
from degradation_fw.core.io import save_image
from degradation_fw.core.registry import commands
from degradation_fw.core.weights import manifest


def test_list_shows_every_degradation(capsys):
    main(["list"])
    out = capsys.readouterr().out
    for name in available():
        assert name in out


def test_run_applies_one_degradation(tmp_path, image):
    src, dst = tmp_path / "in.png", tmp_path / "out.png"
    save_image(image, src)
    main(["run", "gaussian_noise", "-i", str(src), "-o", str(dst),
          "-p", "sigma=0.1", "per_channel=false", "--seed", "3"])
    meta = json.loads(dst.with_suffix(".json").read_text(encoding="utf-8"))
    assert meta["seed"] == 3
    assert meta["steps"] == [{"name": "gaussian_noise", "params": {"sigma": 0.1, "per_channel": False}}]


@pytest.mark.parametrize("args, message", [
    (["no_such"], "Unknown degradation"),
    (["gaussian_noise", "-p", "nope=1"], "unknown params"),
    (["gaussian_noise", "-p", "sigma=9"], "not in"),
    (["gaussian_noise", "-p", "sigma"], "KEY=VALUE"),
])
def test_run_rejects_bad_input_before_any_work(tmp_path, image, args, message):
    src, dst = tmp_path / "in.png", tmp_path / "out.png"
    save_image(image, src)
    name, *rest = args
    with pytest.raises(SystemExit) as e:
        main(["run", name, "-i", str(src), "-o", str(dst), *rest])
    assert message in str(e.value.code)
    assert not dst.exists()


def test_commands_registered_by_degradations_are_added():
    """degfw fog comes from weather/fog.py; building the CLI loads no model."""
    assert "fog" in {c.name for c in commands()}
    with pytest.raises(SystemExit) as e:
        main(["fog", "--help"])
    assert e.value.code == 0


def test_weights_lists_every_file(capsys):
    try:
        main(["weights"])
    except SystemExit:  # exit code 1 if a file is missing on this machine
        pass
    out = capsys.readouterr().out
    for wid in manifest():
        assert wid in out
