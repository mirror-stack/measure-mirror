"""Every report-printing `mm` subcommand exits 1 on a FAIL (0 on OK/WARN).

`mm audit` was fixed first (#78). verify, judge, negative, calibrate, certify and the
`mm <name>` shortcut printed FAIL / REJECTED and still exited 0, which a shell script or
CI step reads as success.
"""
import json
import subprocess
import sys

CLI = "import sys; from measure_mirror.mm import _cli; sys.argv[0] = 'mm'; _cli()"


def mm(cwd, *args):
    return subprocess.run([sys.executable, "-c", CLI, *args], cwd=cwd,
                          capture_output=True, encoding="utf-8")


def _register(cwd, cid, *extra):
    r = mm(cwd, "register", cid, "--metric", "acc", "--min-n", "200", "--baseline", "0.5",
           "--pass", "0.60", "--kill-threshold", "0.55", "--kill-direction", "below", *extra)
    assert r.returncode == 0, r.stderr


def test_verify_exits_1_on_fail(tmp_path):
    (tmp_path / "bad.json").write_text(json.dumps({"scores": [5] * 20}))
    (tmp_path / "good.json").write_text(json.dumps({"scores": [1, 2, 3, 4, 5] * 4}))
    bad = mm(tmp_path, "verify", "--file", "bad.json")
    assert "FAIL" in bad.stdout and bad.returncode == 1
    good = mm(tmp_path, "verify", "--file", "good.json")
    assert good.returncode == 0, good.stdout


def test_judge_exits_1_on_fail(tmp_path):
    (tmp_path / "bad.json").write_text(json.dumps({"scores": [5] * 20}))
    (tmp_path / "good.json").write_text(json.dumps({"scores": [1, 2, 3, 4, 5] * 4}))
    assert mm(tmp_path, "judge", "--file", "bad.json").returncode == 1
    assert mm(tmp_path, "judge", "--file", "good.json").returncode == 0


def test_negative_exits_1_on_fail(tmp_path):
    r = mm(tmp_path, "negative", "--angles", "only_one")
    assert "FAIL" in r.stdout and r.returncode == 1


def test_certify_exits_1_only_when_rejected(tmp_path):
    _register(tmp_path, "m", "--new-ledger")
    ok = mm(tmp_path, "certify", "m", "--acc", "0.72", "--n", "500")
    assert json.loads(ok.stdout)["verdict"].startswith("CERTIFIED") and ok.returncode == 0
    rejected = mm(tmp_path, "certify", "m", "--acc", "0.53", "--n", "500")
    assert json.loads(rejected.stdout)["verdict"] == "REJECTED" and rejected.returncode == 1
    unverified = mm(tmp_path, "certify", "never_registered")
    assert json.loads(unverified.stdout)["verdict"] == "UNVERIFIED"
    assert unverified.returncode == 0          # printed for a reader to judge, like WARN


def test_name_shortcut_exits_1_on_fail(tmp_path):
    _register(tmp_path, "m", "--new-ledger")
    (tmp_path / "m.json").write_text(json.dumps({"acc": 0.53, "n": 500}))
    r = mm(tmp_path, "m")
    assert "FAIL" in r.stdout and r.returncode == 1
    (tmp_path / "m.json").write_text(json.dumps({"acc": 0.72, "n": 500}))
    assert mm(tmp_path, "m").returncode == 0


def test_calibrate_passes_on_a_healthy_install(tmp_path):
    r = mm(tmp_path, "calibrate")
    assert r.returncode == 0, r.stdout[-500:]
