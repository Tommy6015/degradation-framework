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
    main(["run", "test_noise", "-i", str(src), "-o", str(dst),
          "-p", "sigma=0.1", "per_channel=false", "--seed", "3"])
    meta = json.loads(dst.with_suffix(".json").read_text(encoding="utf-8"))
    assert meta["seed"] == 3
    assert meta["steps"] == [{"name": "test_noise", "params": {"sigma": 0.1, "per_channel": False}}]


@pytest.mark.parametrize("args, message", [
    (["no_such"], "Unknown degradation"),
    (["test_noise", "-p", "nope=1"], "unknown params"),
    (["test_noise", "-p", "sigma=9"], "not in"),
    (["test_noise", "-p", "sigma"], "KEY=VALUE"),
    (["test_context", "-p", r"folder=D:\no\such folder"], "folder not found"),
])
def test_run_rejects_bad_input_before_any_work(tmp_path, image, args, message):
    src, dst = tmp_path / "in.png", tmp_path / "out.png"
    save_image(image, src)
    name, *rest = args
    with pytest.raises(SystemExit) as e:
        main(["run", name, "-i", str(src), "-o", str(dst), *rest])
    assert message in str(e.value.code)
    assert not dst.exists()


def test_run_takes_a_windows_folder_as_param(tmp_path, image):
    """-p folder=D:\\... : the value is read as YAML, a Windows path stays a plain string."""
    src, dst = tmp_path / "in.png", tmp_path / "out.png"
    save_image(image, src)
    main(["run", "test_context", "-i", str(src), "-o", str(dst), "-p", f"folder={tmp_path}"])
    meta = json.loads(dst.with_suffix(".json").read_text(encoding="utf-8"))
    assert meta["steps"][0]["params"] == {"folder": str(tmp_path)}
    assert meta["steps"][0]["info"]["folder"] == str(tmp_path)


def test_apply_rejects_bad_params_before_any_work(tmp_path, image):
    save_image(image, tmp_path / "in" / "a.png")
    cfg = tmp_path / "cfg.yaml"
    cfg.write_text("steps:\n  - name: test_noise\n    params: {sigma: 9}\n", encoding="utf-8")
    with pytest.raises(SystemExit) as e:
        main(["apply", "-c", str(cfg), "-i", str(tmp_path / "in"), "-o", str(tmp_path / "out")])
    assert "not in" in str(e.value.code)
    assert not (tmp_path / "out").exists()


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
