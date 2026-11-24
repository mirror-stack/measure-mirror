# Five-minute tutorial: seal a claim, then let it fail

You will preregister a claim with a kill-condition, audit three results against it, tamper
with the ledger, and record a KILL. Every output below was produced by running these exact
commands on measure-mirror v0.41.2 (2026-11-23). Your seals and timestamps will differ.

Needs Python 3.10+ and git. No other dependencies.

## 1. Install (about 1 minute)

measure-mirror is not on PyPI yet, so install the tagged release from GitHub:

```bash
python -m venv mm-tutorial && . mm-tutorial/bin/activate      # Windows: mm-tutorial\Scripts\activate
pip install "git+https://github.com/mirror-stack/measure-mirror@v0.41.2"
mkdir mm-try && cd mm-try
```

## 2. Seal the claim before you look at results

Say you will claim your model beats chance (0.5) on accuracy. Decide now what counts as
success (0.60) and what would kill the claim (below 0.55), and how many test items you need (200).

```bash
mm register my_model --metric acc --min-n 200 --baseline 0.5 --pass 0.60 \
           --kill-threshold 0.55 --kill-direction below --new-ledger
```

```
🔒 Sealed: my_model  metric=acc min_n=200 baseline=0.5  kill=acc < 0.55  seal=c08b475e…
```

This appended one line to `mm_ledger.jsonl`. The `seal` is a SHA-256 hash over that line and
the previous seal, so changing any of these numbers later is detectable.
`--new-ledger` is needed only once, to create the file.

## 3. Audit an honest result

```bash
mm audit my_model --acc 0.72 --n 500
```

```
🪞 Audit: my_model
   Overall: ✅ OK
   ✅ [④a small-sample CI] n=500, acc=0.720 → exact binomial p=0.000 ≤ 0.05 clears chance(0.5).
   ✅ [⑪ falsifiability] Kill condition not triggered: acc=0.72 ≥ 0.55.
```

## 4. Three ways the same claim fails

**The result is bad.** The kill-condition you sealed fires:

```bash
mm audit my_model --acc 0.53 --n 500
```

```
   Overall: 🔴 FAIL
   🔴 [④a small-sample CI] n=500, acc=0.530 → exact binomial p=0.195 > 0.05 vs chance(0.5). Indistinguishable from chance.
   🔴 [① pre-registration(pass-threshold)] acc=0.530 < registered pass_threshold=0.600. (seal=c08b475e…)
   🔴 [⑪ falsifiability] Kill condition triggered: acc=0.53 < 0.55. Claim 'my_model' is falsified by its own pre-registered criterion.
```

**You switch to a metric that looks better.**

```bash
mm audit my_model --metric f1 --acc 0.72 --n 500
```

```
   🔴 [① pre-registration(metric-swap)] Reported metric 'f1' ≠ registered 'acc'. Post-hoc swap. (seal=c08b475e…)
```

**You test on fewer items than you promised.**

```bash
mm audit my_model --acc 0.72 --n 40
```

```
   🔴 [① pre-registration(min_n)] n=40 < registered min_n=200.
```

Exit status: on `main` (next release), `mm audit` exits 1 when any probe FAILs and 0 for OK
or WARN, so it can stop a shell script or CI step. So do `mm verify`, `mm judge`,
`mm negative`, `mm calibrate` and the `mm <name>` shortcut; `mm certify` exits 1 when the
verdict is REJECTED. v0.41.2, installed above, still exits 0
even on FAIL; with it, use the pytest integration in the README (`assert_clean`) for CI.

## 5. Try to move the goalposts

Lower the sealed pass threshold by editing the ledger (with `sed` as below, or change `0.6` to `0.5` in any text editor), then audit the bad result again:

```bash
cp mm_ledger.jsonl backup.jsonl
sed -i 's/"pass_threshold": 0.6/"pass_threshold": 0.5/' mm_ledger.jsonl   # macOS: sed -i ''
mm audit my_model --acc 0.53 --n 500
```

```
   Overall: 🔴 FAIL
   🔴 [④a small-sample CI] n=500, acc=0.530 → exact binomial p=0.195 > 0.05 vs chance(0.5). Indistinguishable from chance.
   🔴 [① seal-tamper] Seal mismatch for 'my_model'. Ledger modified.
```

Restore it: `cp backup.jsonl mm_ledger.jsonl`.

What this does **not** stop: someone deleting the whole ledger and sealing a new one with
today's date. Only a copy of the seal held by someone else (an external timestamp, a witness)
closes that gap. The seal proves the file was not edited, not when it was written.

## 6. Record the KILL instead of hiding it

```bash
mm retract my_model --reason "KILL: acc=0.53 < sealed kill threshold 0.55"
```

```
🚫 Retracted: my_model  reason='KILL: acc=0.53 < sealed kill threshold 0.55'  seal=5d492ed9…
```

The retraction is chained after the preregistration. Any later audit of this claim, even a
good-looking one, now reports `🔴 [⑫ retraction-cascade] Claim 'my_model' has been retracted.`

## Next

- See a real record: [an agent that retracted its own experiment before spending a token](https://github.com/mirror-stack/measure-mirror/blob/main/stack/CASE_STUDY_compute_governor.md), with the sealed ledger bundled so you can verify it.
- All 28 probes: [GUIDE.md](https://github.com/mirror-stack/measure-mirror/blob/main/docs/GUIDE.md).
- Something here did not match what you saw? [Open a reproduce report](https://github.com/mirror-stack/measure-mirror/issues/new?template=reproduce-report.yml). Mismatches are useful.
