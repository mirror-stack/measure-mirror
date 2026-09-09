import importlib.util
import json
from pathlib import Path


def test_generic_linkage_explicitly_does_not_certify_content(tmp_path):
    source = Path(__file__).resolve().parents[1] / "stack" / "verify_self.py"
    spec = importlib.util.spec_from_file_location("depth_verify_self", source)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    p = tmp_path / "ledger.jsonl"
    p.write_text(json.dumps({"prev_seal": "genesis", "seal": "not-a-hash",
                            "result": "unverified content"}) + "\n")
    calls = []
    mod.generic_linkage(str(p), "ledger", lambda *args: calls.append(args))
    assert calls[0][0] == mod.OK
    assert "depth=LINKAGE_ONLY" in calls[0][3]
    assert "seals NOT recomputed" in calls[0][3]


def test_orchestrator_discloses_linkage_only_scope(tmp_path):
    import subprocess
    import sys
    source = Path(__file__).resolve().parents[1] / "stack" / "verify_all.py"
    ledgers = tmp_path / "ledgers"
    ledgers.mkdir()
    (ledgers / "demo.jsonl").write_text('{"prev_seal":"genesis","seal":"x"}\n')
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({"mm_ledgers": {}, "ledger_dir": str(ledgers)}))
    r = subprocess.run([sys.executable, str(source), "--config", str(cfg)],
                       capture_output=True, text=True)
    assert r.returncode == 0
    assert "linkage-only auto-included ledgers (1): demo.jsonl" in r.stdout
    assert "unverified: external-clock precedence, independent reproduction" in r.stdout
