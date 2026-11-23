"""docs/TUTORIAL.md shows real CLI output. Keep the lines it quotes true."""
import json
import subprocess
import sys

CLI = "import sys; from measure_mirror.mm import _cli; sys.argv[0] = 'mm'; _cli()"


def mm(cwd, *args):
    r = subprocess.run([sys.executable, "-c", CLI, *args], cwd=cwd,
                       capture_output=True, text=True)
    return r.stdout + r.stderr


def test_tutorial_steps(tmp_path):
    out = mm(tmp_path, "register", "my_model", "--metric", "acc", "--min-n", "200",
             "--baseline", "0.5", "--pass", "0.60", "--kill-threshold", "0.55",
             "--kill-direction", "below", "--new-ledger")
    assert "🔒 Sealed: my_model" in out and "kill=acc < 0.55" in out

    assert "Overall: ✅ OK" in mm(tmp_path, "audit", "my_model", "--acc", "0.72", "--n", "500")

    out = mm(tmp_path, "audit", "my_model", "--acc", "0.53", "--n", "500")
    assert "Kill condition triggered: acc=0.53 < 0.55" in out
    assert "acc=0.530 < registered pass_threshold=0.600" in out

    out = mm(tmp_path, "audit", "my_model", "--metric", "f1", "--acc", "0.72", "--n", "500")
    assert "Reported metric 'f1' ≠ registered 'acc'. Post-hoc swap." in out

    out = mm(tmp_path, "audit", "my_model", "--acc", "0.72", "--n", "40")
    assert "n=40 < registered min_n=200." in out

    led = tmp_path / "mm_ledger.jsonl"
    good = led.read_text()
    assert '"pass_threshold": 0.6' in good            # the string the sed step edits
    led.write_text(good.replace('"pass_threshold": 0.6', '"pass_threshold": 0.5'))
    assert "Seal mismatch for 'my_model'. Ledger modified." in mm(
        tmp_path, "audit", "my_model", "--acc", "0.53", "--n", "500")
    led.write_text(good)

    out = mm(tmp_path, "retract", "my_model", "--reason",
             "KILL: acc=0.53 < sealed kill threshold 0.55")
    assert "🚫 Retracted: my_model" in out
    out = mm(tmp_path, "audit", "my_model", "--acc", "0.72", "--n", "500")
    assert "Claim 'my_model' has been retracted." in out
    assert [json.loads(l).get("_type") for l in led.read_text().splitlines()] == [None, "retraction"]
