"""Concurrent appenders must not fork the chain.

Every append reads the head seal and then writes a line pointing at it. Before the
ledger lock, two processes could read the same head and both append after it; the
honest second line was then reported by verify_chain() as "deleted/inserted".
Reproduced 2026-11-24 with 4 processes x 50 preregister() calls: 109-150 chain-break
FAILs in each of 3 runs.

Real processes (not threads), because the bug is between processes: cron jobs and
sibling agents appending to one ledger.
"""
import json
import os
import subprocess
import sys
import textwrap

from measure_mirror import mm

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

WRITER = textwrap.dedent("""
    import sys
    from measure_mirror import mm, judge
    path, wid, n = sys.argv[1], sys.argv[2], int(sys.argv[3])
    for j in range(n):
        k = j % 3
        if k == 0:
            mm.preregister(path, f"w{wid}_{j}", metric="acc", min_n=10,
                           baseline=0.5, pass_threshold=0.6)
        elif k == 1:
            mm.retract(path, f"w{wid}_{j - 1}", "concurrency test")
        else:
            judge._seal_judge_run(path, {"_type": "judge_run", "claim_id": f"w{wid}_{j}"})
""")


def _run_writers(path, workers=4, per_worker=30):
    env = dict(os.environ)
    env["PYTHONPATH"] = ROOT + os.pathsep + env.get("PYTHONPATH", "")
    procs = [subprocess.Popen([sys.executable, "-c", WRITER, path, str(w), str(per_worker)],
                              env=env, stderr=subprocess.PIPE, text=True)
             for w in range(workers)]
    for p in procs:
        _, err = p.communicate(timeout=120)
        assert p.returncode == 0, err


def test_concurrent_appenders_keep_one_chain(tmp_path):
    path = str(tmp_path / "ledger.jsonl")
    _run_writers(path, workers=4, per_worker=30)

    findings = mm.verify_chain(path)
    assert [f.level for f in findings] == ["OK"], findings
    with open(path, encoding="utf-8") as f:
        lines = [json.loads(l) for l in f if l.strip()]
    assert len(lines) == 4 * 30                      # nothing lost, nothing doubled
    assert len({e["prev_seal"] for e in lines}) == len(lines)   # no two entries share a parent


def test_lock_is_released_after_a_failed_append(tmp_path):
    path = str(tmp_path / "ledger.jsonl")

    class Unserializable:
        pass

    try:
        mm._append_sealed(path, {"claim_id": "x", "bad": Unserializable()})
    except TypeError:
        pass
    # If the lock leaked, this would wait out the timeout and raise TimeoutError.
    with mm._ledger_lock(path, timeout=1.0):
        pass
    mm.preregister(path, "ok", metric="acc", min_n=10, baseline=0.5, pass_threshold=0.6)
    assert [f.level for f in mm.verify_chain(path)] == ["OK"]


def test_held_lock_times_out_instead_of_forking(tmp_path):
    path = str(tmp_path / "ledger.jsonl")
    holder = subprocess.Popen(
        [sys.executable, "-c",
         "import sys,time; sys.path.insert(0, sys.argv[2]);"
         "from measure_mirror import mm\n"
         "with mm._ledger_lock(sys.argv[1]):\n"
         "    print('held', flush=True); time.sleep(5)",
         path, ROOT],
        stdout=subprocess.PIPE, text=True)
    try:
        assert holder.stdout.readline().strip() == "held"
        try:
            with mm._ledger_lock(path, timeout=0.3):
                raise AssertionError("acquired a lock another process holds")
        except TimeoutError:
            pass
    finally:
        holder.kill()
        holder.wait()


def test_entry_line_layout_unchanged(tmp_path):
    """prev_seal stays where preregister() always put it (after pass_threshold)."""
    path = str(tmp_path / "ledger.jsonl")
    mm.preregister(path, "c1", metric="acc", min_n=10, baseline=0.5,
                   pass_threshold=0.6, kill_condition="acc < 0.55")
    keys = list(json.loads(open(path, encoding="utf-8").readline()))
    assert keys == ["ts", "claim_id", "metric", "min_n", "baseline", "pass_threshold",
                    "prev_seal", "kill_condition", "seal"]
