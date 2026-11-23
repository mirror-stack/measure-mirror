# 5분 튜토리얼: 주장을 봉인하고, 실패하게 두기

kill 조건이 있는 주장을 사전등록하고, 결과 세 개를 감사하고, 원장을 조작해 보고, KILL을
기록합니다. 아래 출력은 measure-mirror v0.41.2에서 이 명령을 그대로 실행해 얻은 것입니다
(2026-11-23). 봉인 값과 시각은 실행할 때마다 달라집니다. 출력 문구는 영어 그대로 둡니다.

Python 3.10 이상과 git만 있으면 됩니다.

## 1. 설치 (약 1분)

아직 PyPI에는 없습니다. GitHub의 태그 릴리스를 설치합니다.

```bash
python -m venv mm-tutorial && . mm-tutorial/bin/activate      # Windows: mm-tutorial\Scripts\activate
pip install "git+https://github.com/mirror-stack/measure-mirror@v0.41.2"
mkdir mm-try && cd mm-try
```

## 2. 결과를 보기 전에 봉인하기

정확도(acc)가 우연(0.5)보다 낫다고 주장할 계획이라고 합시다. 성공 기준(0.60), 주장을 죽일
기준(0.55 미만), 필요한 시험 문항 수(200)를 지금 정합니다.

```bash
mm register my_model --metric acc --min-n 200 --baseline 0.5 --pass 0.60 \
           --kill-threshold 0.55 --kill-direction below --new-ledger
```

```
🔒 Sealed: my_model  metric=acc min_n=200 baseline=0.5  kill=acc < 0.55  seal=c08b475e…
```

`mm_ledger.jsonl`에 한 줄이 추가됩니다. `seal`은 이 줄과 직전 봉인을 묶은 SHA-256 해시라서,
나중에 숫자를 바꾸면 드러납니다. `--new-ledger`는 파일을 처음 만들 때 한 번만 필요합니다.

## 3. 정직한 결과 감사

```bash
mm audit my_model --acc 0.72 --n 500
```

```
   Overall: ✅ OK
   ✅ [④a small-sample CI] n=500, acc=0.720 → exact binomial p=0.000 ≤ 0.05 clears chance(0.5).
   ✅ [⑪ falsifiability] Kill condition not triggered: acc=0.72 ≥ 0.55.
```

## 4. 같은 주장이 실패하는 세 가지 경우

**결과가 나쁠 때.** 봉인한 kill 조건이 작동합니다.

```bash
mm audit my_model --acc 0.53 --n 500
```

```
   🔴 [⑪ falsifiability] Kill condition triggered: acc=0.53 < 0.55. Claim 'my_model' is falsified by its own pre-registered criterion.
```

**더 좋아 보이는 지표로 바꿀 때.**

```bash
mm audit my_model --metric f1 --acc 0.72 --n 500
```

```
   🔴 [① pre-registration(metric-swap)] Reported metric 'f1' ≠ registered 'acc'. Post-hoc swap. (seal=c08b475e…)
```

**약속보다 적은 문항으로 시험할 때.**

```bash
mm audit my_model --acc 0.72 --n 40
```

```
   🔴 [① pre-registration(min_n)] n=40 < registered min_n=200.
```

종료 코드: `main`(다음 릴리스)에서는 `mm audit`이 FAIL이 하나라도 있으면 1, OK나 WARN이면 0으로
끝나서 셸 스크립트나 CI 단계를 멈출 수 있습니다. 위에서 설치한 v0.41.2는 아직 FAIL이어도 0으로
끝나므로, CI에는 README의 pytest 연동(`assert_clean`)을 쓰세요.

## 5. 골대 옮기기 시도

원장에서 봉인된 통과 기준을 낮추고(아래 `sed`로, 또는 아무 편집기에서 `0.6`을 `0.5`로),
나쁜 결과를 다시 감사합니다.

```bash
cp mm_ledger.jsonl backup.jsonl
sed -i 's/"pass_threshold": 0.6/"pass_threshold": 0.5/' mm_ledger.jsonl   # macOS: sed -i ''
mm audit my_model --acc 0.53 --n 500
```

```
   🔴 [① seal-tamper] Seal mismatch for 'my_model'. Ledger modified.
```

복구: `cp backup.jsonl mm_ledger.jsonl`

이것으로 막지 **못하는** 것: 원장을 통째로 지우고 오늘 날짜로 새로 봉인하는 경우. 그 틈은
봉인 값을 다른 누군가가 들고 있을 때(외부 타임스탬프, 증인)만 닫힙니다. 봉인은 파일이
수정되지 않았다는 것을 증명할 뿐, 언제 쓰였는지는 증명하지 않습니다.

## 6. KILL을 숨기지 말고 기록하기

```bash
mm retract my_model --reason "KILL: acc=0.53 < sealed kill threshold 0.55"
```

```
🚫 Retracted: my_model  reason='KILL: acc=0.53 < sealed kill threshold 0.55'  seal=5d492ed9…
```

철회는 사전등록 뒤에 체인으로 이어집니다. 이후 이 주장을 감사하면 결과가 좋아 보여도
`🔴 [⑫ retraction-cascade] Claim 'my_model' has been retracted.` 가 나옵니다.

## 다음

- 실제 기록: [토큰 하나 쓰기 전에 자기 실험을 철회한 에이전트](../stack/CASE_STUDY_compute_governor_KO.md) (봉인된 원장 포함, 직접 검증 가능)
- 28개 프로브 전체: [GUIDE_KO.md](GUIDE_KO.md)
- 출력이 다르게 나왔나요? [재현 보고 열기](https://github.com/mirror-stack/measure-mirror/issues/new?template=reproduce-report.yml). 불일치 보고도 환영합니다.
