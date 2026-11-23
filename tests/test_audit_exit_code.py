"""`mm audit` exit status: 1 when any probe FAILs, 0 otherwise (OK or WARN)."""
import subprocess
import sys

CLI = "import sys; from measure_mirror.mm import _cli; sys.argv[0] = 'mm'; _cli()"


def mm(cwd, *args):
    return subprocess.run([sys.executable, "-c", CLI, *args], cwd=cwd,
                          capture_output=True, text=True)


def test_audit_exit_status(tmp_path):
    r = mm(tmp_path, "register", "m", "--metric", "acc", "--min-n", "200", "--baseline", "0.5",
           "--pass", "0.60", "--kill-threshold", "0.55", "--kill-direction", "below",
           "--new-ledger")
    assert r.returncode == 0, r.stderr

    ok = mm(tmp_path, "audit", "m", "--acc", "0.72", "--n", "500")
    assert "Overall: ✅ OK" in ok.stdout and ok.returncode == 0

    killed = mm(tmp_path, "audit", "m", "--acc", "0.53", "--n", "500")
    assert "Overall: 🔴 FAIL" in killed.stdout and killed.returncode == 1

    swapped = mm(tmp_path, "audit", "m", "--metric", "f1", "--acc", "0.72", "--n", "500")
    assert "Overall: 🔴 FAIL" in swapped.stdout and swapped.returncode == 1


def test_audit_from_file_also_exits_1_on_fail(tmp_path):
    mm(tmp_path, "register", "m", "--metric", "acc", "--min-n", "200", "--baseline", "0.5",
       "--pass", "0.60", "--new-ledger")
    (tmp_path / "m.json").write_text('{"claim_id": "m", "metric": "acc", "acc": 0.72, "n": 40}')
    r = mm(tmp_path, "audit", "--file", "m.json")
    assert "min_n" in r.stdout and r.returncode == 1
