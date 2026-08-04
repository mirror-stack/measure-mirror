# 🪞 Measurement Mirror — 프로브 완전 가이드

> **대상 독자**: 각 프로브가 무엇을 하는지, 언제 써야 하는지, 출력을 어떻게 읽어야 하는지
> 알고 싶은 연구자·ML 엔지니어·리뷰어.
>
> **관련 파일**: [README_KO](../README_KO.md) (API 레퍼런스) ·
> [CHANGELOG](../CHANGELOG.md) · [CHRONICLE](CHRONICLE.md) (개발 연대기)
>
> **English version**: [GUIDE.md](GUIDE.md)
>
> **범위**: 이 가이드는 **28개 프로브** 전체를 다룹니다. 아래에 나오는 "4개 프로브"
> 같은 표현은 특정 그룹의 **부분 수치**이지 총계가 아닙니다.

---

## 철학: 양방향 거울

대부분의 평가 무결성 도구는 **거짓양성**만 잡습니다 — 실제보다 좋아 보이는 결과.
Measurement Mirror는 양방향을 모두 잡습니다:

| 방향 | 실패 예시 | 거울의 반응 |
|---|---|---|
| 거짓양성 | n=9, acc=55.6%를 획기적 성과로 보고 | ④a Wilson CI가 우연 수준임을 적발 |
| **거짓음성** | 실험 1회 실패 → "이 접근법은 죽었다" | ⑬ negative_audit가 독립 각도 ≥3개 요구 |
| **판정자 착시** | LLM 판정자가 항상 첫 번째 응답을 선택 | ⑮ judge_bias_check가 위치 편향 적발 |

성급한 음성 종결은 조작된 양성만큼 나쁩니다. 둘 다 연구 자원을 낭비하고
분야 전체를 잘못된 방향으로 이끄는 허상입니다.

---

## 주장 생애주기

```
① preregister               ← 결과를 보기 전에 기준을 봉인
        │
        ▼
㉗ prereg_lint               ← 연산을 쓰기 전에 봉인의 품질을 린트
        │                       (kill-condition 누수 · 선언우연 이하 바 ·
        ▼                        비구조화 kill · 저 n · 체크 미선언)
    실험 실행
        │
        ▼
audit / full_audit           ← 결과가 나온 후 전체 프로브 실행
  ├─ ④a 통계 유효성
  ├─ ①  사전등록 확인
  ├─ ⑩  GRIM 산술 확인
  ├─ ⑪  반증가능성 / kill-condition
  └─ ⑫  철회 cascade
        │
        ├── 양성 결론 → publish + anchor (외부 해시 보관)
        │
        ├── 음성 결론 → negative_audit (⑬) 로 종결 게이트
        │                 독립 각도 ≥ min_angles 필요
        │                 │
        │                 ▼
        │              나중에 무효화 시: retract() → cascade_check()
        │
        └── LLM judge 평가 → judge_run()이 ⑭⑮⑯⑰ 자동 발화
                              체인 연결 엔트리를 원장에 봉인
```

---

## 검증 3단계

| 단계 | 방법 | 용도 |
|---|---|---|
| **풀 검증** | `mm.verify(ledger, data)` / `mm verify --file data.json` | 원샷 감사 — `data`에 입력이 있는 모든 프로브 실행 |
| **그룹단위 검증** | `mm.verify(ledger, data, groups=["judge"])` / `--groups judge` | 하나의 검증 관심사에 집중 |
| **개별검증** | `mm.grim_check(...)`, `mm.judge_swap_check(...)` 등 | 정밀 제어, 커스텀 파이프라인 |

검증 그룹 (`mm verify --list-groups` 또는 `mm.GROUPS`):

| 그룹 | 프로브 | 답하는 질문 |
|---|---|---|
| `ledger` | ① ⑫ + 체인 | 사전등록 기록이 무결하고 철회되지 않았나? |
| `stats` | ④ ⑤ ⑦ ⑧ ⑨ ⑩ | 숫자가 통계적으로 진짜인가? |
| `design` | ② ③ ⑥ ⑪ | 실험이 공정하게 설계됐나? |
| `negative` | ⑬ | 이 음성 종결이 성급하지 않나? |
| `judge` | ⑭ ⑮ ⑯ ⑰ ⑱ | LLM 판정자가 신뢰할 만한가? |
| `ranking` | ⑲ ⑳ | 리더보드가 진짜인가? |

`verify()`는 입력 주도형입니다: `data` 딕셔너리에 키가 있는 프로브만 실행되므로,
풀 검증은 입력 누락으로 에러나지 않습니다 — 데이터가 지원하는 만큼만 돕니다.
`group_of(finding)`으로 어떤 Finding이든 소속 그룹을 알 수 있습니다.

---

## 프로브 레퍼런스

프로브는 잡아내는 무결성 실패의 종류별로 묶었습니다.

---

### Group 1 — 사전등록 & 원장 무결성

#### ① `preregister` / `audit`

**잡아내는 것**: 사후 지표 교체 · 표본 미달 · 조작된 기준 · pass-threshold 미달

사전등록은 결과를 보기 *전에* 평가 계획을 봉인합니다. SHA-256 봉인과 체인 링크가
위변조를 탐지 가능하게 만듭니다: 사후에 어떤 필드든 변경하면 감지됩니다.

```python
# 실험 전
mm.preregister("ledger.jsonl", "my_model",
               metric="acc",          # 커밋하는 단 하나의 지표
               min_n=200,             # 허용되는 최소 표본 크기
               baseline=0.5,          # 공정한 비교 기준선
               pass_threshold=0.60)   # 성공을 주장하기 위한 최소 기준

# 실험 후
findings = mm.audit("ledger.jsonl", "my_model",
                    reported_metric="acc",   # 등록된 지표와 일치해야 함
                    reported_acc=0.72,
                    n=500)
mm.report("my_model", findings)
```

**`audit()` 출력 레벨:**
- `FAIL [① pre-registration(metric-swap)]` — `acc` 등록 후 `f1` 보고
- `FAIL [① pre-registration(min_n)]` — `n=9 < 등록된 min_n=200`
- `FAIL [① pre-registration(pass-threshold)]` — 스스로 설정한 기준 미달
- `FAIL [① seal-tamper]` — 등록 후 원장 파일 수정됨

**흔한 실수**: `metric="acc"`로 등록 후, 나중에 더 좋아 보이는 지표(`f1`, `auc`)를
보고. 봉인이 몇 달 후에도 이것을 잡아냅니다.

---

#### ① `verify_chain`

**잡아내는 것**: 삭제된 엔트리 · 삽입된 엔트리 · 어떤 엔트리든 내용 수정

```python
findings = mm.verify_chain("ledger.jsonl")
mm.report("원장 무결성", findings)
```

체인이 작동하는 원리: 모든 엔트리가 자신의 봉인을 계산하기 전에
*이전* 엔트리의 SHA-256인 `prev_seal`을 포함합니다. N번 엔트리를 삭제하면
N+1번 엔트리에서 체인이 끊깁니다. 가짜 엔트리를 삽입해도 끊깁니다.

**실행 시점**: 모든 실험 후 CI에서, 그리고 결과 게재 전에.

---

#### `anchor` (유틸리티)

**잡아내는 것**: 원장 파일 통째 교체 — 체인 해시가 혼자서는 잡지 못하는 유일한 공격

체인 해시는 파일 *안의* 수정을 감지합니다. 그러나 누군가 파일을 통째로 삭제하고
새로 시작하면, 기술적으로 체인은 유효합니다(새 genesis). `anchor_hash`(전체 파일
바이트의 SHA-256)가 이것을 잡아냅니다.

```python
# 변조 방지 스냅샷 출력 — 신뢰하는 곳에 파이프
a = mm.anchor("ledger.jsonl")
# → {"_type": "anchor", "anchor_hash": "sha256hex...", "chain_ok": true, ...}
```

```bash
# 게재 전 외부 저장소에 파이프
mm anchor | gh gist create -               # GitHub Gist 타임스탬프
mm anchor >> ~/Dropbox/mm_anchors.jsonl    # 로컬 백업
mm anchor --pretty                          # 사람이 읽기 쉬운 형태
```

**권장 사항**: 결과를 게재하기 직전에 `mm anchor`를 실행하세요. 외부 타임스탬프가
게재 시점에 원장이 무엇을 담고 있었는지를 증명합니다.

#### ㉗ `prereg_lint` — 연산 전, 봉인의 품질

`falsifiability_check`(⑪)는 kill-condition이 *존재하는지*를 묻습니다. `prereg_lint`는
봉인이 **자동 검사가 발화할 만큼 제대로 됐는지, 바가 의미 있는지**를 묻습니다 —
무의미 연산이 새는 결함 클래스들:

| 레벨 | 결함 |
|---|---|
| FAIL | kill-condition 문장이 `metric` 필드로 누수(잘못된 호출 — 사람 눈엔 기준이 보이나 파서엔 없음) |
| FAIL | pass 바가 선언된 우연(chance) 이하(넘어도 아무것도 증명 못 함; `chance=` 필요 — `baseline`만으론 바닥 아님) |
| WARN | 정량 kill을 구조화된 `kill_threshold` 없이 자유텍스트로만 → 영원히 자동평가 불가 |
| WARN | `min_n`이 소표본 바닥(20) 미만 |
| INFO | `pre_seal_checks` 미선언(reachability-smoke · mass-balance-audit · neutral-control · manipulation-check · positive-control) |

```python
mm.preregister("ledger.jsonl", "my_model",
               metric="acc", min_n=240, baseline=0.5, pass_threshold=0.60,
               kill_threshold={"metric": "acc", "threshold": 0.55, "direction": "below"},
               pre_seal_checks=["reachability-smoke", "neutral-control"])

for f in mm.prereg_lint("ledger.jsonl", "my_model"):   # claim_id=None → 전 주장 린트
    print(f)
```

의도적으로 `verify()` 우산·그룹에 **넣지 않았습니다**: 이것은 *연산 전* 체크이고,
`verify()`/`audit()`은 보고 시점에 돕니다. MCP `mm_register` 안에서 자동 발화하며(응답에
lint 동봉), mirror-stack compute 게이트는 ㉗ FAIL에 BLOCK합니다. FAIL이면 **새 claim_id로
고쳐서 재봉인** — first-write-wins라 이미 봉인된 것은 고칠 수 없습니다.

---

### Group 2 — 통계 유효성

#### ④a Wilson CI (`audit` 내부)

**잡아내는 것**: 통계적으로 우연과 구별 불가한 결과 (소표본 신기루)

Wilson 스코어 신뢰구간은 작은 n에서 정규근사보다 정확합니다.
95% CI가 기준선을 포함하면 결과는 통계적으로 무의미합니다.

```python
# audit() 내부에서 자동 실행
findings = mm.audit("ledger.jsonl", "my_model",
                    reported_metric="acc", reported_acc=0.72, n=15)
# ⚠️  [④a small-sample CI] n=15, acc=0.72 → 95%CI [0.467, 0.887]
#     ⊃ baseline(0.5). 우연과 구별 불가.
```

**경험 법칙**: n=15에서는 acc=0.72도 0.5와 구별되지 않습니다.
+10pp 개선을 유의미하게 보이려면 n≥200이 필요합니다.

---

#### ⑧ `power_check`

**잡아내는 것**: 관심 있는 최소 효과를 탐지하기에 n이 너무 작음 (거짓음성 가드)

이것이 거울의 핵심 **거짓음성 프로브**입니다. 통계적 검정력이 부족한 실험에서
나온 음성 결과는 의미가 없습니다 — 진짜 효과를 놓쳤을 수 있습니다.

```python
f = mm.power_check(n=50, baseline=0.5, min_detectable_effect=0.05)
# ⚠️  [⑧ power] n=50은 80% 검정력으로 Δ=+0.05 탐지에 부족.
#     필요 n≥388. (α=0.05, power=0.80)

# 다양한 효과 크기에서 80% 검정력에 필요한 n:
# Δ=+0.20 → n≈50  |  Δ=+0.10 → n≈200  |  Δ=+0.05 → n≈388

# full_audit에서 활성화
findings = mm.full_audit("ledger.jsonl", "my_model", ...,
                          min_detectable_effect=0.05)
```

**흔한 실수**: n=30으로 Δ=+0.05에 대해 테스트한 후 "이 방법은 도움이 안 된다"
(음성 결론)를 종결. 검정력이 14%였으므로 진짜 효과를 놓쳤을 확률이 86%입니다.

---

#### ⑨ `multiple_comparisons_check`

**잡아내는 것**: 같은 원장에서 k>1 실험을 할 때의 다중비교 문제

5개 실험을 돌려 가장 좋은 것을 고르면, 실효 α는 0.05가 아니라
1 − (1−0.05)^5 ≈ 0.23입니다. Bonferroni 교정은 테스트당 α/k를 요구합니다.

```python
f = mm.multiple_comparisons_check("ledger.jsonl", alpha=0.05)
# ⚠️  [⑨ multiple-comparisons] 원장에 k=5개 실험.
#     Bonferroni 교정 α = 0.010 (0.05가 아님). 더 엄격한 기준 사용.

# full_audit에서 활성화
findings = mm.full_audit("ledger.jsonl", "my_model", ...,
                          check_multiplicity=True)
```

**참고**: 같은 `claim_id`의 재등록은 k=1로 카운트(first-write-wins 정책과 일관).
서로 다른 claim_id만 카운트됩니다.

---

### Group 3 — 비교 정직성

#### ② `baseline_fairness`

**잡아내는 것**: 허약한 기준선 · 동점 결과 · 역전된 비교

의도적으로 약한 기준선 대비 "강한 개선"은 개선이 아닙니다.
오차 범위 안에 드는 "더 좋은" 결과는 동점입니다.

```python
# 허약한 기준선: 내 모델이 망가진 경쟁자를 이김
f = mm.baseline_fairness("random_baseline", 0.60, 0.50)   # OK — 명확한 승리
f = mm.baseline_fairness("vs_gru_ode",      0.998, 0.996)  # FAIL — 동점 (Δ=0.002)

# 역전: 내가 짐
f = mm.baseline_fairness("strong_model", 0.72, 0.86)  # FAIL — 기준선 승

# 이진이 아닌 지표 (낮을수록 좋음, 예: MSE)
f = mm.baseline_fairness("vs_baseline_mse", 0.12, 0.15, higher_better=False)
```

**레벨:**
- `FAIL [② fair-baseline] X wins` — 기준선이 나를 능가
- `FAIL [② fair-baseline] Tied` — Δ < margin (기본값 0.01)
- `OK` — 명확한 승리

---

#### ⑦ `too_good_check`

**잡아내는 것**: 추가 검토가 필요한 의심스럽게 큰 개선

"너무 좋아 보이면, 그게 보통 사실입니다": 데이터 누수, 평가셋 오염,
보상/지표 정렬 버그가 흔한 원인입니다.

```python
f = mm.too_good_check("my_model", claimed=0.95, baseline=0.50)
# ⚠️  [⑦ too-good] 기준선 대비 Δ=+0.45 — 의심스럽게 큼.
#     조사: 데이터 누수? 보상 해킹? 지표 정렬 버그?
```

기본 임계값: Δ > 0.30이면 WARN. `full_audit()` 내부에서 항상 자동 실행됩니다.

---

### Group 4 — 데이터 & 지표 무결성

#### ③ `gaming_check`

**잡아내는 것**: 훈련 보상/손실에 평가 지표가 직접 포함됨

평가 지표를 직접 최적화하면 결과는 자기충족적입니다: 모델은 기저 과제를
학습했기 때문이 아니라, 지표를 최적화하도록 훈련됐기 때문에 좋은 점수를 받습니다.

```python
f = mm.gaming_check(metric="accuracy",
                    reward_terms=["cross_entropy", "accuracy"])
# 🔴 [③ gaming] 'accuracy'가 reward_terms에 포함됨.
#    결과는 자기충족적 — 지표가 훈련 목적함수에 직접 있음.

f = mm.gaming_check(metric="bleu", reward_terms=["rl_reward", "fluency"])
# ✅ OK — bleu가 보상에 없음
```

---

#### ④a `leakage_check`

**잡아내는 것**: 훈련/테스트 세트 중복 (데이터 오염)

소량의 중복도 정확도를 크게 부풀릴 수 있습니다. 아이템을 해싱하여 교집합을
계산합니다 — 해시 가능한 아이템 타입이면 모두 작동합니다.

```python
# 문자열 아이템
train = ["문장 A", "문장 B", "문장 C"]
test  = ["문장 C", "문장 D", "문장 E"]
f = mm.leakage_check(train, test)
# 🔴 [④a leakage] 테스트 아이템의 1/3 (33.3%)이 훈련셋에 있음.

# 정수, 튜플, 해시 가능한 모든 타입 작동
f = mm.leakage_check(list(range(100)), list(range(50, 150)))  # 50% 중복 → FAIL
```

---

#### ⑤ `multiseed_check`

**잡아내는 것**: 시드 간 불안정한 신호 · 기준선이 시드 범위 안에 들어옴

acc=0.48~0.72 범위로 시드마다 결과가 달라지면 신뢰할 수 없습니다.
기준선이 시드 범위 안에 있으면, 다른 초기화에서 결과가 우연과 구별되지 않습니다.

```python
f = mm.multiseed_check([0.48, 0.72, 0.65], baseline=0.5)
# 🔴 [⑤ multi-seed] 기준선 0.500이 시드 범위 [0.480, 0.720] 안에 있음.
#    우연 이상의 신호가 강건하지 않음.

f = mm.multiseed_check([0.68, 0.71, 0.72], baseline=0.5)   # OK
f = mm.multiseed_check([0.70, 0.85, 0.75], baseline=0.5,
                        cv_threshold=0.05)  # CV 임계값 조정
```

**규칙**: CV(변동계수) > 10%이면 기본으로 WARN.

---

#### ⑥ `scope_check`

**잡아내는 것**: 검증된 범위보다 넓게 주장 (과대 일반화)

"과제 A에서 작동" ≠ "일반 추론". `claimed_scope`는 `tested_scope`의 부분집합이거나
같아야 합니다.

```python
f = mm.scope_check(claimed_scope=["reasoning", "math"],
                   tested_scope=["musr_task_a"])
# 🔴 [⑥ scope] 과대주장: {'reasoning', 'math'} 미검증.
#    검증됨: {'musr_task_a'} 뿐.

f = mm.scope_check(claimed_scope=["task_a"],
                   tested_scope=["task_a", "held_out_b"])  # OK
```

---

#### ⑩ `grim_check`

**잡아내는 것**: 산술적으로 불가능한 정확도/평균 값 — 조작되었거나 n을 잘못 기재한 가능성

GRIM (Granularity-Related Inconsistency of Means): `acc = k/N`이 어떤 정수 k에
대해 성립한다면(`N = n·items`), `round(k/N, d) == acc`가 반드시 성립해야 합니다.
이를 만족하는 정수 k가 없다면 그 값은 불가능합니다. 비율·퍼센트·정수(리커트 등)
데이터의 평균에 모두 작동합니다.

```python
f = mm.grim_check(reported_acc=0.33, n=10)
# 🔴 [⑩ GRIM] acc=0.33은 n=10에서 산술적으로 불가능.
#    round(k/10, 2) = 0.33을 만족하는 정수 k 없음.
#    (후보: k=3 → 0.30, k=4 → 0.40). 수치 조작 또는 n 오기재.

f = mm.grim_check(reported_acc=0.30, n=10)   # OK — round(3/10, 2) = 0.30

# 다문항 척도의 평균: granularity는 n·items
f = mm.grim_check(5.90, n=40, items=3)        # N=120

# 소수점 자리수 자동 추론; n_decimals로 재정의 가능
f = mm.grim_check(0.333, n=10, n_decimals=3)
```

**`audit()` 내부에서 자동 실행** — FAIL만 추가, OK는 조용히 통과.

> **범위 — 소표본 전용.** GRIM의 힘은 *granularity*에서 나옵니다: N이 작으면
> 도달 가능한 값이 몇 개뿐이라 불가능한 값이 튀어나옵니다. N이 커지면 도달 가능한
> 값이 빽빽이 채워져 GRIM은 눈이 멉니다 — d자리로 보고된 값은 `N ≳ 10^d`(예:
> 2자리 평균에서 n ≥ 100)부터 아무것도 못 잡습니다. 또한 *산술적* 불가능만 잡지
> *분포적* 조작은 못 잡습니다: 대규모 조작 데이터셋(예: AI 생성)은 보통 GRIM을
> 통과하고, 대신 디지트 패턴/분포 포렌식에 걸립니다(여기 범위 밖). **실증 확인**:
> 무작위 2자리 평균은 n=20에서 ~79%가 GRIM-불가능이지만 n≥100에서는 ~0%.
> GRIM은 소표본 산술 게이트이지 범용 사기 탐지기가 아닙니다.

---

### Group 5 — 주장 생애주기

이 세 프로브가 "주장 생애주기 무결성" 시스템의 핵심입니다.
셋을 합치면 Measurement Mirror가 "통계 체크리스트"에서
**무엇이 주장됐고, 무엇이 그 주장을 죽일 수 있으며, 기반이 무너졌는지**를
추적하는 감사 인프라로 바뀝니다.

---

#### ⑪ `falsifiability_check`

**잡아내는 것**: 반증 불가능한 주장 (kill-condition 없음) · 이미 자기부정한 주장

kill-condition 없는 주장은 원칙적으로 틀렸음을 증명할 수 없습니다 — 반증불가능합니다.
등록된 `kill_threshold`를 결과가 발화시키는 주장은 게재 시점에 *자기부정*됩니다.

```python
# 실험 전 kill-condition 등록
mm.preregister("ledger.jsonl", "my_model",
               metric="acc", min_n=200, baseline=0.5, pass_threshold=0.60,
               # 사람이 읽는 설명 (선택사항이지만 권장)
               kill_condition="held-out 테스트에서 정확도 0.55 미만",
               # 구조화 형태: audit 시점에 자동 평가 (권장)
               kill_threshold={"metric": "acc",
                                "threshold": 0.55,
                                "direction": "below"})

# audit 시 — ⑪ 자동 실행
findings = mm.audit("ledger.jsonl", "my_model",
                    reported_metric="acc", reported_acc=0.50, n=500)
# 🔴 [⑪ falsifiability] Kill condition triggered: acc=0.5 < 0.55.
#    Claim 'my_model' is falsified by its own pre-registered criterion.

# 단독 확인 (전체 audit 전 또는 특정 쿼리용)
f = mm.falsifiability_check("ledger.jsonl", "my_model", reported_acc=0.50)
```

**레벨:**
- `FAIL` — kill_threshold 등록됨 AND reported_acc가 발화
- `WARN` — kill-condition 아예 없음 ("반증불가능") OR threshold 설정됐지만 결과 미제공
- `OK` — threshold 미발화, 또는 텍스트 전용 조건 등록됨

**direction 파라미터:**
- `"below"`: `reported_acc < threshold`일 때 FAIL (정확도형, 높을수록 좋음)
- `"above"`: `reported_acc > threshold`일 때 FAIL (오류형, 예: MSE, 낮을수록 좋음)

**CLI:**
```bash
mm register my_model --metric acc --min-n 200 --baseline 0.5 --pass 0.60 \
  --kill "정확도 0.55 미만이면 사망" \
  --kill-threshold 0.55 --kill-direction below
```

---

#### ⑫ `cascade_check` + `retract`

**잡아내는 것**: 철회된 기반 위에 세워진 주장 (오래된 전이 의존성)

연구는 누적됩니다. 주장 B는 주장 A 위에 세워지는 경우가 많습니다. 주장 A가 철회되면
(데이터셋 오염 발견, 방법론 결함 발견), A에 의존하는 모든 주장은 자동으로 STALE로
표시되어야 합니다 — 설령 수년 후에 게재된 것이라도.

```python
# 실험 전 의존 관계 등록
mm.preregister("ledger.jsonl", "dataset_v1",
               metric="quality_score", min_n=100, baseline=0.0, pass_threshold=0.8)
mm.preregister("ledger.jsonl", "v1로_훈련된_모델",
               metric="acc", min_n=200, baseline=0.5, pass_threshold=0.60,
               depends_on=["dataset_v1"])            # ← 의존성 봉인
mm.preregister("ledger.jsonl", "논문_결과",
               metric="acc", min_n=500, baseline=0.5, pass_threshold=0.70,
               depends_on=["v1로_훈련된_모델"])       # ← 전이 체인

# 나중에: 데이터셋 오염 발견
mm.retract("ledger.jsonl", "dataset_v1",
           reason="전처리 단계에서 훈련/테스트 12% 중복 발견")

# Cascade check — 의존성 체인을 직접 알 필요 없음
f = mm.cascade_check("ledger.jsonl", "논문_결과")
# ⚠️  [⑫ retraction-cascade] Claim '논문_결과' is STALE:
#     depends (transitively) on retracted claim(s): 'dataset_v1'

f = mm.cascade_check("ledger.jsonl", "dataset_v1")
# 🔴 [⑫ retraction-cascade] Claim 'dataset_v1' has been retracted.
```

**cascade_check 레벨:**
- `FAIL` — 주장 자체가 철회됨
- `WARN` — 주장이 STALE (전이 의존성이 철회됨)
- `OK` — 철회 위험 없음

**핵심 특성:**
- 철회 엔트리는 **체인 연결**됩니다 — 철회 기록 삭제 시 `verify_chain()`이 감지.
  조용히 철회를 없애는 것이 불가능합니다.
- 전파는 **게재 순서와 무관** — 2019년 데이터셋을 기반으로 한 2020년 논문이
  2024년에 철회되면 즉시 STALE로 표시.
- **`audit()` 내부에서 자동 실행** (WARN/FAIL만 추가).

**CLI:**
```bash
# 의존성 포함 등록
mm register model_v2 --metric acc --min-n 200 --baseline 0.5 --pass 0.60 \
  --depends-on dataset_v1 baseline_eval

# 철회
mm retract dataset_v1 --reason "훈련/테스트 중복 발견"
```

---

#### ⑬ `negative_audit`

**잡아내는 것**: 성급한 음성 종결 (각도가 부족한 Resolved-Negative)

연구에서 가장 잡기 어려운 거짓음성: 단 한 번의 음성 실험 후 "X는 작동하지 않는다"
선언. 단일 실패는 frame 결함일 수 있으며, 보편적 벽이 아닙니다. 음성 결론이
신뢰받으려면 여러 독립 각도가 수렴해야 합니다.

```python
# 각 각도는 동일한 가설을 다른 관점에서 테스트하는 별개의 독립 실험
# (다른 데이터셋, 방법론, 조건)
for angle_id in ["oee_wave_ode", "oee_bilinear_coev", "oee_alife_sim",
                  "oee_gray_scott", "oee_hp_folding"]:
    mm.preregister("ledger.jsonl", angle_id,
                   metric="oee_score", min_n=50, baseline=0.5, pass_threshold=0.0)

# 모든 각도가 음성으로 수렴한 후 — 종결 게이트
f = mm.negative_audit("ledger.jsonl",
                      angles=["oee_wave_ode", "oee_bilinear_coev",
                               "oee_alife_sim", "oee_gray_scott", "oee_hp_folding"],
                      min_angles=3)
# ✅ [⑬ negative-audit] 5/5 independent pre-registered angle(s) verified —
#    negative conclusion is supported.

# 선택사항: 음성 결론이 과대 일반화되지 않았는지 범위 확인
f = mm.negative_audit("ledger.jsonl",
                      angles=["oee_wave_ode", "oee_bilinear_coev", "oee_alife_sim"],
                      conclusion_scope=["all_substrates", "all_ALife"],
                      tested_scope=["in_silico_digital"])
# 🔴 [⑬ negative-audit] conclusion scope includes untested domain(s):
#    ['all_substrates', 'all_ALife'].
```

**레벨:**
- `FAIL` — `min_angles`보다 각도 수가 적음 (성급종결 위험)
- `FAIL` — 각도가 사전등록되지 않음 (독립 증거로 신뢰 불가)
- `FAIL` — `conclusion_scope ⊄ tested_scope` (과대 일반화된 음성)
- `WARN` — 각도 수는 충분하지만 일부 철회됨 (약화된 케이스)
- `OK` — 전체 통과

**CLI:**
```bash
mm negative \
  --angles oee_wave_ode oee_bilinear_coev oee_alife_sim \
  --min-angles 3
```

**`full_audit()`를 통한 활성화:**
```python
findings = mm.full_audit("ledger.jsonl", "main_claim", ...,
                          angles=["exp1", "exp2", "exp3"])
# ⑬ 결과가 자동으로 추가됨
```

---

### 그룹 6 — LLM-as-a-Judge 프로브 ⑭⑮⑯⑰

이 4개 프로브는 평가받는 모델이 아니라 **판정자 자체**를 감사합니다.
LLM 판정자는 숫자 지표로는 잡을 수 없는 고유한 실패 패턴을 가집니다:
확률적 뒤집기, 위치 편향, 런 간 불일치, 퇴화 점수 분포.

4개 프로브는 모두 `mm.py`에 있어 의존성이 없으며 점수 리스트를 직접 받습니다.
선택 모듈 `judge.py`는 LLM 호출과 4개 프로브 연결을 자동 처리합니다.

**설치:**
```bash
pip install "measure-mirror[judge]"   # openai · anthropic 패키지 추가
```

---

#### ⑭ `judge_consistency_check`

**잡아내는 것**: 재실행 시 동일 아이템에 다른 판정을 내리는 확률적 판정자.

동일 아이템에 판정자를 두 번 실행했을 때 뒤집기 비율이 높으면 판정자 출력은 노이즈입니다.
노이즈 점수로 만든 순위는 집계 수치가 안정적으로 보여도 의미가 없습니다.

```python
# score_pairs: [(런1 점수, 런2 점수), ...] — 동일 아이템 2회 판정
# pairwise: 0 = A 승, 1 = B 승
# rating: 정수 점수

score_pairs = [(1, 1), (0, 0), (1, 1), (0, 0), (1, 0)]  # 1회 뒤집기 / 5
f = mm.judge_consistency_check(score_pairs, flip_threshold=0.20)
# ✅ [⑭ judge-consistency] Judge flip rate 20.0% ≤ 20.0% (1/5 flips). Consistent.

score_pairs_bad = [(1, 0), (0, 1), (1, 0), (0, 1), (1, 0)]  # 전부 뒤집힘
f = mm.judge_consistency_check(score_pairs_bad, flip_threshold=0.20)
# 🔴 [⑭ judge-consistency] Judge flip rate 100.0% > 20.0%.
#    Judge is unreliable — scores cannot be trusted.
```

**파라미터:**
| 파라미터 | 기본값 | 설명 |
|---|---|---|
| `score_pairs` | 필수 | `[(런1, 런2), ...]` — 아이템당 1쌍 |
| `flip_threshold` | 0.20 | 허용 최대 뒤집기 비율 |

**레벨:**
- `FAIL` — flip_rate > flip_threshold
- `WARN` — 빈 score_pairs (판단 불가)
- `OK` — flip_rate ≤ flip_threshold

---

#### ⑮ `judge_bias_check`

**잡아내는 것**: 내용에 관계없이 A 또는 B 위치를 체계적으로 선호하는 판정자.

pairwise 평가에서 판정자는 고정된 순서(A, B)로 응답을 받습니다.
편향된 판정자는 "첫 번째 답이 더 좋다"라는 지름길을 씁니다.
이는 선호되는 위치를 차지하는 후보를 부당하게 유리하게 만듭니다.

```python
# pairwise_results: [0, 1, 0, ...] — 0 = A 승, 1 = B 승

results = [0, 1, 0, 1, 0, 1, 0, 1, 0, 1]  # 50/50 — 편향 없음
f = mm.judge_bias_check(results)
# ✅ [⑮ judge-bias] Position A win rate 50.0% — no significant position bias.

results = [0, 0, 0, 0, 0, 0, 0, 0, 0, 1]  # A가 90% 승
f = mm.judge_bias_check(results, bias_threshold=0.60)
# 🔴 [⑮ judge-bias] Position A win rate 90.0% > 60.0%.
#    Strong position bias detected (9/10 items favor A).
```

**완화 방법**: 각 쌍을 양방향(AB, BA)으로 실행하고 평균냅니다.
편향 없는 판정자라면 순서 변경 시 판정 빈도가 반전돼야 합니다.

**파라미터:**
| 파라미터 | 기본값 | 설명 |
|---|---|---|
| `pairwise_results` | 필수 | `[0, 1, ...]` — 비교당 1결과 |
| `bias_threshold` | 0.60 | 위치 편향 플래그 임계값 |

**레벨:**
- `FAIL` — A 또는 B 승률 > bias_threshold
- `WARN` — 빈 results
- `OK` — 양방향 승률 모두 임계값 이하

---

#### ⑯ `inter_rater_agreement`

**잡아내는 것**: 두 판정자(또는 동일 판정자의 두 런)가 우연 수준을 넘어 불일치.

Cohen's κ는 무작위 우연으로 기대되는 일치 이상의 일치를 측정합니다.
κ ≈ 0이면 두 평가자는 사실상 독립적인 난수 변수입니다 — 점수를 평균내거나
단일 신호로 보고하는 것이 의미를 잃습니다.

| κ | 해석 |
|---|---|
| < 0.20 | 불량 — 사실상 무작위 |
| 0.20 – 0.40 | 보통 |
| 0.40 – 0.60 | 중간 (기본 임계값) |
| 0.60 – 0.80 | 양호 |
| > 0.80 | 거의 완벽 |

```python
# ratings_matrix: [(판정자1_점수, 판정자2_점수), ...] — 아이템당 1행

# 완전 일치
matrix = [(1, 1), (0, 0), (1, 1), (0, 0), (1, 1)]
f = mm.inter_rater_agreement(matrix)
# ✅ [⑯ inter-rater] Cohen's κ=1.000 ≥ 0.40 — acceptable inter-rater agreement.

# 보통 일치 (κ ≈ 0.33 < 0.40)
matrix = [(0, 0), (0, 1), (0, 0), (1, 1), (1, 0), (1, 1)]
f = mm.inter_rater_agreement(matrix, min_kappa=0.40)
# ⚠️ [⑯ inter-rater] Cohen's κ=0.333 < 0.40 — fair agreement only.

# 불량 일치 → FAIL
matrix = [(0, 1), (1, 0), (0, 1), (1, 0), (0, 1)]
f = mm.inter_rater_agreement(matrix)
# 🔴 [⑯ inter-rater] Cohen's κ=-1.000 < 0.20 — poor agreement.
```

**파라미터:**
| 파라미터 | 기본값 | 설명 |
|---|---|---|
| `ratings_matrix` | 필수 | `[(r1, r2), ...]` — ≥ 3 아이템 필요 |
| `min_kappa` | 0.40 | 허용 최소 κ |

**레벨:**
- `FAIL` — κ < 0.20 또는 아이템 < 3
- `WARN` — 0.20 ≤ κ < min_kappa
- `OK` — κ ≥ min_kappa

---

#### ⑰ `judge_score_sanity`

**잡아내는 것**: 거의 모든 것에 동일한 점수를 부여하는 퇴화 판정자.

판별력이 사실상 없는 판정자는 신호를 제공하지 않습니다.
그 점수로 만든 순위는 무작위 순위와 동등합니다.

```python
# scores: [8, 7, 8, 9, ...] — 한 판정자의 모든 점수

# 건강한 분포
scores = [3, 7, 5, 8, 4, 6, 9, 2, 7, 5, 3, 8, 6, 4, 7]
f = mm.judge_score_sanity(scores)
# ✅ [⑰ judge-score-sanity] 8 distinct values across 15 scores (53.3% unique).

# 퇴화: 전원 동점
scores = [8] * 20
f = mm.judge_score_sanity(scores)
# 🔴 [⑰ judge-score-sanity] All 20 scores identical (8).
#    Judge is not discriminating — scores are meaningless.

# 근사 퇴화: 95%가 8
scores = [8] * 19 + [7]
f = mm.judge_score_sanity(scores)
# ⚠️ [⑰ judge-score-sanity] 95% of scores are '8' — near-degenerate distribution.
```

**파라미터:**
| 파라미터 | 기본값 | 설명 |
|---|---|---|
| `scores` | 필수 | 한 판정자 런의 모든 점수 목록 |
| `min_unique_ratio` | 0.10 | 총 점수 대비 고유값 비율 최솟값 |

**레벨:**
- `FAIL` — 전원 동점
- `WARN` — 최다 값 집중 > 90% 또는 고유 비율 < min_unique_ratio
- `OK` — 분포 양호

---

#### ⑱ `judge_swap_check`

**잡아내는 것**: 판정이 *슬롯*을 따르고 내용을 따르지 않는 판정자 — 가장 어려운
케이스인 "결정론적·균형적·내용 무시" 판정자(다른 모든 프로브 통과) 포함.

각 쌍을 두 번 판정합니다: (A, B) 순서로 한 번, 위치를 교환한 (B, A)로 한 번.
내용을 읽는 판정자는 판정을 뒤집어야 합니다 — 같은 응답이 어느 슬롯에서든 이겨야
하니까. 판정이 슬롯에 머무르면 내용이 아닌 위치를 읽고 있는 것입니다.

```
lock = forward[i] == swapped[i]   (같은 슬롯이 두 번 다 승리)

lock_rate ≈ 0.0  → 내용 주도   (판정이 응답을 따라감)   → OK
lock_rate ≈ 0.5  → 노이즈      (어느 쪽도 안 따라감)    → WARN
lock_rate ≈ 1.0  → 위치 고착   (판정이 슬롯을 따라감)   → FAIL
```

**승률 집계(⑮)로 부족한 이유** — 응답을 전혀 안 읽는 결정론적 판정자(예: 프롬프트만
보고 결정)는 완벽히 일관되고(⑭ OK), 승률도 균형이고(⑮ OK), 자기 자신과 일치하고
(⑯ κ=1.0), 점수도 다양합니다(⑰ OK). 오직 스왑만이 정체를 드러냅니다:

```python
# 내용 주도 판정자: 스왑하면 모든 판정이 뒤집힘
forward = [0, 1, 0, 1, 0, 1]
swapped = [1, 0, 1, 0, 1, 0]
f = mm.judge_swap_check(forward, swapped)
# ✅ [⑱ judge-swap] Position-lock rate 0.0% ≤ 35.0%. Content-driven.

# 내용 무시 판정자: 양방향 판정이 동일
forward = [0, 1, 0, 1, 0, 1]
swapped = [0, 1, 0, 1, 0, 1]
f = mm.judge_swap_check(forward, swapped)
# 🔴 [⑱ judge-swap] Position-lock rate 100.0% > 65.0%.
#    판정자가 내용이 아닌 위치를 읽고 있음.
```

`python examples/demo_judge.py`를 실행하면 mock 내용-무시 판정자가 ⑭⑮⑯⑰을
전부 통과하고 ⑱에만 적발되는 것을 볼 수 있습니다 — API 키 불필요.

**파라미터:**
| 파라미터 | 기본값 | 설명 |
|---|---|---|
| `forward_results` | 필수 | `[0, 1, ...]` — 원래 (A, B) 순서 승자 |
| `swapped_results` | 필수 | `[0, 1, ...]` — 교환된 (B, A) 순서 승자 |
| `position_lock_threshold` | 0.65 | lock_rate 초과 시 FAIL |
| `noise_threshold` | 0.35 | lock_rate 초과 시 WARN |

{0, 1} 밖의 값(-1 파싱 실패 등)이 포함된 쌍은 제외됩니다.

**레벨:**
- `FAIL` — lock_rate > position_lock_threshold 또는 길이 불일치
- `WARN` — 노이즈 밴드 내 lock_rate 또는 유효 쌍 없음
- `OK` — lock_rate ≤ noise_threshold

---

#### `judge_run` — 자동 오케스트레이션 (`judge.py`)

`judge_run`은 점수 수집의 번거로움을 없애줍니다. judge 함수를 호출하고,
4개 프로브를 자동으로 발화한 뒤, 체인 연결된 `_type: judge_run` 엔트리를
원장에 봉인합니다.

```python
from measure_mirror.judge import anthropic_judge, openai_judge, judge_run

# 1단계: judge callable 생성
judge_fn = anthropic_judge(
    model="claude-opus-4-8",
    system_prompt="당신은 엄격하고 공정한 평가자입니다.",
    pairwise=True,   # True = A/B 비교; False = 1-10 점수
)

# 2단계: 아이템 준비
pairs = [
    {"prompt": "경사하강법을 설명하세요",
     "a": "모델 A의 응답", "b": "모델 B의 응답"},
    ...
]

# 3단계: 실행 + 자동 프로브
result = judge_run(
    "mm_ledger.jsonl",   # 원장 경로 — 엔트리가 체인 연결·봉인됨
    "my_llm_eval_v1",    # claim_id — 사전등록 엔트리와 연결
    judge_fn=judge_fn,
    items=pairs,
    runs=2,               # 아이템당 2회 호출 → ⑭ + ⑯ 활성화
    pairwise=True,        # ⑮ 편향 검사 활성화
    swap_positions=True,  # AB→BA 추가 패스 → ⑱ 스왑 검사 활성화
)

for f in result["findings"]:
    print(f"  {f.level}  [{f.probe}]  {f.msg}")

print(result["scores"])        # 런-1 점수 (아이템당 1개)
print(result["score_pairs"])   # (런1, 런2) 쌍 — runs=1이면 None
print(result["ledger_entry"])  # 봉인된 원장 엔트리
```

**반환값 키:**

| 키 | 타입 | 내용 |
|---|---|---|
| `findings` | `list[Finding]` | 프로브 결과 (⑭⑮⑯⑰⑱ + `judge-parse`) |
| `scores` | `list[int]` | 런-1 원시 점수 (아이템당 1개, -1 포함 가능) |
| `score_pairs` | `list[tuple]` or `None` | `(런1, 런2)` 쌍; `runs=1`이면 `None` |
| `swap_scores` | `list[int]` or `None` | 교환 순서 점수; `swap_positions` 아니면 `None` |
| `parse_failures` | `int` | 파싱 불가로 제외된 아이템 수 |
| `n_items` | `int` | 평가된 아이템 수 |
| `runs` | `int` | 반복 횟수 |
| `pairwise` | `bool` | pairwise 모드 여부 |
| `ledger_entry` | `dict` | 원장에 추가된 체인 연결 엔트리 |

**조건별 활성 프로브:**

| 프로브 | 조건 |
|---|---|
| ⑭ `judge_consistency_check` | `runs ≥ 2`일 때 항상 |
| ⑮ `judge_bias_check` | `pairwise=True`일 때 항상 |
| ⑯ `inter_rater_agreement` | **자동발화 안 함** — 단독 전용, 서로 다른 두 판정자용 (같은 판정자 재실행은 ⑭의 몫) |
| ⑰ `judge_score_sanity` | 항상 |
| ⑱ `judge_swap_check` | `swap_positions=True`일 때 (pairwise 전용) |
| `judge-parse` | 파싱 실패율 >10% 시 WARN; 전부 실패 시 FAIL |

**파싱 실패 처리** — 파싱 불가 응답은 -1로 기록됩니다. 어느 런에서든 -1이 나온
아이템은 모든 프로브에서 제외되어, 파싱 노이즈가 ⑮ 편향이나 ⑰ 건전성 결과를
왜곡할 수 없습니다. 제외 수는 원장 엔트리(`parse_failures`)에 기록됩니다.

---

### 그룹 7 — 순위 무결성 ⑲⑳

판정자 프로브(그룹 6)는 개별 판정을 감사합니다. 이 두 프로브는 그 판정으로 만든
**순위 자체**를 감사합니다 — 대부분의 발표 주장이 실제로 사는 리더보드 레이어입니다.

---

#### ⑲ `judge_transitivity_check`

**잡아내는 것**: pairwise 토너먼트의 순환 선호(A>B>C>A) — 일관된 품질 척도가
없는 판정자.

판정자가 셋 이상의 모델을 쌍별 비교로 순위 매길 때, 집계된 선호는 이행적 순서를
이뤄야 합니다. 순환이 있으면 그 판정으로 만든 리더보드는 대진 순서의 산물입니다:
브래킷을 다른 순서로 돌리면 다른 챔피언이 나옵니다.

```python
# matches: [(모델a, 모델b, 승자), ...] — 승자 0 = 첫째, 1 = 둘째
# 같은 쌍의 반복 대진은 다수결로 집계됩니다.

matches = [("gpt", "claude", 0),     # gpt > claude
           ("claude", "llama", 0),   # claude > llama
           ("gpt", "llama", 0)]      # gpt > llama — 이행적 ✓
f = mm.judge_transitivity_check(matches)
# ✅ [⑲ judge-transitivity] 3개 모델 선호 그래프가 비순환 — 일관된 순위 존재.

matches = [("gpt", "claude", 0),
           ("claude", "llama", 0),
           ("llama", "gpt", 0)]      # llama > gpt — 순환!
f = mm.judge_transitivity_check(matches)
# 🔴 [⑲ judge-transitivity] 순환 선호 적발: gpt > claude > llama > gpt.
#    판정자에게 일관된 품질 척도가 없음.
```

정확히 동률인 쌍(양방향 동수 승리)은 엣지를 만들지 않아 거짓 순환을 일으킬 수
없으며, OK 메시지에 제외된 동률 수가 보고됩니다.

**레벨:**
- `FAIL` — 순환 1개 이상 (예시 경로 표시)
- `WARN` — 모델 3개 미만 또는 대진 없음
- `OK` — 선호 그래프 비순환

---

#### ⑳ `ranking_stability_check`

**잡아내는 것**: 순위 신기루 — 같은 크기 표본을 다시 뽑으면 뒤집히는
"모델 A가 B를 이김" 주장.

부트스트랩 리샘플링: 아이템 인덱스를 복원추출로 `n_boot`회 다시 뽑아 관측된
승자가 얼마나 자주 승자로 유지되는지 측정합니다. 결정론적(시드 고정 RNG) —
같은 입력은 항상 같은 Finding을 내어 거울의 재현성 규율을 지킵니다.

```python
# 같은 아이템에 대한 두 모델의 아이템별 점수 (인덱스로 짝지음)
scores_a = [9, 8, 9, 9, 8, 9, 8, 9]   # 일관되게 높음
scores_b = [3, 2, 3, 2, 3, 2, 3, 2]   # 일관되게 낮음
f = mm.ranking_stability_check(scores_a, scores_b)
# ✅ [⑳ ranking-stability] 순위 'A > B'가 1000회 부트스트랩 중 100.0% 유지 (n=8).

scores_a = [5, 9, 1, 8, 2, 7, 3]      # 고분산,
scores_b = [6, 1, 9, 2, 8, 3, 7]      # 합계 거의 동률
f = mm.ranking_stability_check(scores_a, scores_b)
# 🔴 [⑳ ranking-stability] 순위가 1000회 중 52.4%만 유지 (n=7). 순위는 노이즈.
```

**파라미터:**
| 파라미터 | 기본값 | 설명 |
|---|---|---|
| `scores_a`, `scores_b` | 필수 | 짝지어진 아이템별 점수; 동일 길이, ≥ 5 아이템 |
| `n_boot` | 1000 | 부트스트랩 횟수 |
| `seed` | 0 | RNG 시드 (결정론) |
| `min_stability` | 0.95 | 요구되는 승자 유지 비율 |

**레벨:**
- `FAIL` — 길이 불일치 · 합계 동률 · 안정성 < 0.80
- `WARN` — 아이템 5개 미만 · 0.80 ≤ 안정성 < min_stability
- `OK` — 안정성 ≥ min_stability

---

## 유틸리티 레퍼런스

### `calibrate` (보정)

자가 테스트: 5가지 합성 알려진-좋음/나쁨 케이스를 실행하고 예상 결과를 검증.
실제 결과를 감사하기 전에 거울 자체에 회귀가 없음을 확인합니다.

```python
findings = mm.calibrate()
mm.report("거울 건강 상태", findings)
# ✅ [⚙ calibrate] 5/5 synthetic cases correct — mirror is calibrated.
```

```bash
mm calibrate
```

**`witness()` 전 또는 CI에서** 도구가 올바르게 작동하는지 확인하기 위해 실행.

---

### `witness` (증인 실행)

커맨드를 실행하고, 출력을 캡처하며, 변조 방지 실행 기록을 봉인합니다.
어떤 커맨드가, 언제, 정확히 무엇을 생성했는지를 증명합니다.

```python
entry = mm.witness("ledger.jsonl", "my_model",
                   ["python", "evaluate.py", "--model", "my_model"])
# stdout/stderr/returncode가 바뀌면 entry["output_hash"]가 달라짐
# 엔트리는 체인 연결됨 — 삭제 시 verify_chain()이 감지
```

```bash
# CLI: 먼저 보정 후 실행 및 봉인 (--no-calibrate로 보정 건너뜀)
mm run my_model -- python evaluate.py --model my_model
```

**활용**: 결과 게재 전에 평가 스크립트의 정확한 출력을 봉인. 누군가 수치에 의문을
제기하면, 증인 기록이 스크립트가 무엇을 생성했는지 증명합니다.

---

### `retract` (철회)

체인 연결 철회 엔트리를 추가합니다. 위의 [⑫ cascade_check](#-cascade_check--retract)를 참조하세요.

---

### `certificate` (인증서)

주장의 전체 무결성 상태를 논문·README·릴리스 노트에 삽입 가능한 하나의
검증 가능 산출물로 압축해 봉인된 인증서를 발행합니다.

```python
# 구조 인증서 (사전등록 봉인 + 체인 + 철회 상태)
cert = mm.certificate("ledger.jsonl", "my_model")

# 완전 인증서 — 감사 결과까지 포함
findings = mm.audit("ledger.jsonl", "my_model",
                    reported_metric="acc", reported_acc=0.72, n=500)
cert = mm.certificate("ledger.jsonl", "my_model", findings=findings)
```

```bash
mm certify my_model --pretty                  # 구조만
mm certify my_model --acc 0.72 --n 500        # + 감사 결과 포함
mm certify my_model | gh gist create -        # 외부 공개
```

| 판정 | 발동 조건 |
|---|---|
| `REJECTED` | 체인 파손 · 봉인 변조 · 철회됨 · FAIL 존재 |
| `UNVERIFIED` | 사전등록 없음 |
| `CERTIFIED-WITH-WARNINGS` | 오래된 의존성 또는 WARN 존재 |
| `CERTIFIED` | 모든 검사 통과 |

핵심 속성:
- 원장의 `anchor_hash`를 포함 — 인증서는 **특정 원장 상태 하나**를 보증.
  원장 변경 후에는 재발행 필요.
- 인증서 자체가 봉인됨(SHA-256) — 필드 수정은 즉시 탐지.
- 원장에 추가되지 않음; `anchor()`처럼 출력 산출물.

---

### `badge` (배지)

인증서를 임베드 가능한 배지로 렌더링합니다 — verdict의 시각화.

```python
cert = mm.certificate("ledger.jsonl", "my_model")
mm.badge(cert)                 # markdown — README용 shields.io 이미지
mm.badge(cert, fmt="svg")      # 자체완결 SVG, 오프라인 작동
```

```bash
mm certify my_model --badge markdown >> README.md
mm certify my_model --badge svg > badge.svg
```

| 판정 | 색상 |
|---|---|
| `CERTIFIED` | brightgreen |
| `CERTIFIED-WITH-WARNINGS` | yellow |
| `UNVERIFIED` | lightgrey |
| `REJECTED` | red |

SVG 버전은 인증서 `seal`과 anchor-hash 접두사를 `<title>` 툴팁에 내장합니다 —
모든 배지는 자신이 렌더링한 봉인 인증서로 추적 가능합니다. SVG 형식은 외부
서비스가 필요 없습니다.

---

## 워크플로우

### 워크플로우 1: 정직한 연구 논문

분류 결과에 대한 엔드-투-엔드 흐름.

```python
from measure_mirror import mm

LEDGER = "experiment_ledger.jsonl"

# ─── 1. 실험 전 ──────────────────────────────────────────────
mm.preregister(LEDGER, "bert_sentiment",
               metric="acc",
               min_n=500,
               baseline=0.5,
               pass_threshold=0.70,
               kill_condition="held-out에서 정확도 0.65 미만",
               kill_threshold={"metric": "acc",
                                "threshold": 0.65,
                                "direction": "below"},
               depends_on=["sst2_dataset_v3"])   # 데이터셋 의존성

# ─── 2. 실행 및 증인 기록 (선택사항이지만 권장) ───────────────
mm.witness(LEDGER, "bert_sentiment",
           ["python", "train_and_eval.py", "--dataset", "sst2"])

# ─── 3. 결과가 나온 후 ───────────────────────────────────────
findings = mm.full_audit(
    LEDGER, "bert_sentiment",
    reported_metric="acc", reported_acc=0.78, n=872,
    baseline=0.5,
    competing_name="LogReg 기준선", competing_acc=0.73,     # ②
    reward_terms=["cross_entropy"],                          # ③
    train_items=train_ids, test_items=test_ids,              # ④a 누수
    seed_results=[0.77, 0.78, 0.79],                         # ⑤
    claimed_scope=["sentiment"],                             # ⑥
    tested_scope=["sst2", "yelp_polarity"],
    min_detectable_effect=0.03,                              # ⑧
    check_multiplicity=True,                                 # ⑨
)
mm.report("BERT 감성분석", findings)

# ─── 4. 제출 전 앵커 ─────────────────────────────────────────
import subprocess
subprocess.run(["mm", "anchor", "--pretty"], check=True)
# → gist, s3, dropbox에 파이프하여 타임스탬프된 외부 증명 생성
```

---

### 워크플로우 2: pytest를 이용한 CI 게이트

```python
# conftest.py
pytest_plugins = ["measure_mirror.pytest_plugin"]

# test_eval_integrity.py
from measure_mirror import mm
from measure_mirror.pytest_plugin import assert_clean

LEDGER = "production_ledger.jsonl"

def test_model_integrity():
    findings = mm.audit(LEDGER, "prod_model_v3",
                        reported_metric="acc", reported_acc=0.78, n=1000)
    assert_clean(findings)   # FAIL findings → pytest 실패 → CI 빨간불

def test_ledger_chain():
    findings = mm.verify_chain(LEDGER)
    assert_clean(findings)

def test_mirror_health():
    findings = mm.calibrate()
    assert_clean(findings)
```

---

### 워크플로우 3: Resolved-Negative 결론 종결

```python
LEDGER = "oee_research_ledger.jsonl"

# 각 독립 각도를 실험 전 등록
angles = [
    ("oee_angle_wave",     "wave ODE — 연속 장"),
    ("oee_angle_bilinear", "bilinear 공진화"),
    ("oee_angle_alife",    "디지털 ALife (DISHTINY 스타일)"),
    ("oee_angle_folding",  "HP 단백질 폴딩 경관"),
    ("oee_angle_gs",       "Gray-Scott 반응-확산"),
]
for cid, desc in angles:
    mm.preregister(LEDGER, cid,
                   metric="oee_score", min_n=50, baseline=0.5, pass_threshold=0.0,
                   kill_condition=f"{desc}: OEE가 임계값 이상")

# ... 5개 실험 모두 실행, 모두 음성으로 수렴 ...

# 음성 종결 게이트
f = mm.negative_audit(LEDGER,
                      angles=[cid for cid, _ in angles],
                      min_angles=3,
                      conclusion_scope=["in_silico_자생_OEE"],
                      tested_scope=["digital_field", "alife_sim",
                                    "protein_HP", "reaction_diffusion"])
mm.report("OEE Resolved-Negative", [f])

# 최종 음성 결론 앵커
import subprocess, json
snap = json.loads(subprocess.check_output(["mm", "anchor", "--ledger", LEDGER]))
print(f"앵커됨: {snap['anchor_hash'][:12]}...")
```

---

### 워크플로우 4: 철회 및 cascade 정리

```python
LEDGER = "shared_lab_ledger.jsonl"

# ─── 기준 데이터셋에서 오염 발견 ─────────────────────────────
mm.retract(LEDGER, "imagenet_baseline_v1",
           reason="전처리 단계에서 훈련/테스트 12% 중복 발견")

# ─── 이제 오래된(STALE) 게재 결과 확인 ───────────────────────
published_claims = ["vit_paper_2023", "resnet_ablation", "downstream_nlp"]

for claim_id in published_claims:
    f = mm.cascade_check(LEDGER, claim_id)
    if f.level != "OK":
        print(f"⚠️  {claim_id}: {f.msg}")

# 출력:
# ⚠️  vit_paper_2023: Claim 'vit_paper_2023' is STALE: depends (transitively)
#     on retracted claim(s): 'imagenet_baseline_v1'
# ⚠️  downstream_nlp: Claim 'downstream_nlp' is STALE: ...
```

---

### 워크플로우 5: MCP 에이전트 연동

MCP 호환 AI(Claude Code, Cursor, Windsurf 등)가 모든 프로브를 대화 중에
직접 호출할 수 있습니다. 에이전트가 코드를 작성하지 않고도 주장을 감사할 수 있습니다.

```json
// .mcp.json
{
  "mcpServers": {
    "measure-mirror": {
      "command": "python",
      "args": ["-m", "measure_mirror.mcp_server"],
      "cwd": "/path/to/measure-mirror"
    }
  }
}
```

에이전트 대화 예시:
```
사용자: "내 모델이 n=200에서 SQuAD 87.3% 나왔어요. 믿을 수 있나요?"

에이전트: [mm_register, mm_audit 호출]
→ ⚠️  [④a small-sample CI] n=200, acc=0.873 → 95%CI [0.820, 0.915]
   기준선(0.5) 초과. OK.
→ ⚠️  [⑦ too-good] 기준선 대비 Δ=+0.373 — 의심스럽게 큼.
   조사: 데이터 누수? 보상 해킹?

[mm_grim_check 호출: reported_acc=0.873, n=200]
→ 🔴 FAIL — n=200에서 acc=0.873을 만족하는 정수 k 없음.
   round(175/200, 3) = 0.875 ≠ 0.873.

"87.3%은 n=200에서 GRIM 불가능한 값입니다. n 또는 acc 중 하나가 잘못 보고됐습니다."
```

---

## 빠른 참조표

| # | 함수 | 잡아내는 것 | `audit()` 자동 실행? |
|---|---|---|---|
| ① | `preregister`/`audit` | 지표 교체, min_n, pass 기준, 봉인 위변조 | ✅ |
| ① | `verify_chain` | 엔트리 삭제/삽입/위변조 | 수동 |
| ② | `baseline_fairness` | 허약/동점/역전된 기준선 | `full_audit` |
| ③ | `gaming_check` | 지표가 보상/손실에 직접 포함 | `full_audit` |
| ④a | Wilson CI (내부) | 소표본 우연 수준 결과 | ✅ |
| ④a | direction (내부) | 기준선보다 나쁨 (역신호) | ✅ |
| ④a | `leakage_check` | 훈련∩테스트 중복 | `full_audit` |
| ⑤ | `multiseed_check` | 불안정한 시드, 기준선이 범위 안 | `full_audit` |
| ⑥ | `scope_check` | 과대 일반화된 주장 | `full_audit` |
| ⑦ | `too_good_check` | 의심스럽게 큰 Δ | `full_audit` |
| ⑧ | `power_check` | n이 효과 탐지에 부족 | `full_audit` |
| ⑨ | `multiple_comparisons_check` | k>1 실험 Bonferroni 경보 | `full_audit` |
| ⑩ | `grim_check` | 산술 불가능 수치 | ✅ (FAIL만) |
| ⑪ | `falsifiability_check` | kill-condition 없음; 발화된 kill threshold | ✅ (사전등록 유효 시) |
| ㉗ | `prereg_lint` | 기형 봉인: kill-condition 누수, 선언우연 이하 바, 비구조화 kill, 저 n, 체크 미선언 | 독립 실행 (연산 전; MCP `mm_register`에서 자동) |
| ⑫ | `cascade_check` | 철회된 주장 또는 오래된 의존성 | ✅ (WARN/FAIL만) |
| ⑬ | `negative_audit` | 성급한 음성 종결; 범위 초과 | `full_audit(angles=...)` |
| ⑭ | `judge_consistency_check` | LLM 판정자 뒤집기율 초과 (신뢰 불가 판정자) | 단독 |
| ⑮ | `judge_bias_check` | 판정자가 A 또는 B 위치를 체계적으로 선호 | 단독 |
| ⑯ | `inter_rater_agreement` | Cohen's κ 미달 (평가자 간 일치도 부족) | 단독 |
| ⑰ | `judge_score_sanity` | 판정자가 동일/근사 점수만 부여 (퇴화 분포) | 단독 |
| ⑱ | `judge_swap_check` | 판정이 내용 아닌 슬롯을 따름 (AB→BA 스왑) | `judge_run(swap_positions=True)` |
| ⑲ | `judge_transitivity_check` | 토너먼트의 A>B>C>A 순환 선호 | 단독 / `mm judge` |
| ⑳ | `ranking_stability_check` | 부트스트랩 리샘플링에서 뒤집히는 순위 | 단독 / `mm judge` |
| — | `anchor` | 원장 파일 완전 교체 | 수동 (게재 전) |
| — | `calibrate` | 거울 자체의 회귀 | 수동 (`witness` 전) |
| — | `witness` | 실행 기록: 무엇이 실행됐고, 언제, 출력 해시 | 수동 |
| — | `retract` | 철회 기록 생성 (체인 연결) | 수동 |
| — | `certificate` | 주장당 봉인된 판정 산출물 (anchor 고정) | 수동 (게재 전) |
| — | `badge` | 임베드 가능한 verdict 배지 (markdown / SVG) | 수동 (`mm certify --badge`) |

**코드베이스 전체 심각도 정책:**
- `FAIL` — 하드 스톱; 결과가 무효이거나 자기모순
- `WARN` — 주의 필요; 결과가 유효할 수 있지만 검토 필요
- `OK` — 이 항목은 통과; 이 차원은 깨끗함

---

## 위협 모델 — 측정거울이 못 잡는 것

측정거울을 고의 조작에 대해 레드팀했습니다. 설계상 집니다. 이 섹션은 그 패배의
정직한 지도입니다 — `OK`를 믿기 전에 읽으세요.

**근본 한계: 측정거울은 *내적 일관성*을 검사하지 *원천 진실성*을 검사하지 않습니다.**
보고된 숫자들이 서로/산술과 모순되지 않는지는 검증하지만, 그 숫자가 진짜 실험에서
나왔는지는 검증 못 합니다. 모든 숫자를 *일관되게* 지어내면 전체 감사가 `OK`를
반환합니다. 이건 고칠 수 있는 버그가 아닙니다 — 조작이 내적으로 일관되면 어떤
도구도 보고된 숫자만으로는 사기를 탐지 못 합니다.

검증된 레드팀 결과:

| 공격 | 결과 |
|---|---|
| GRIM 통과하는 가짜 평균 (큰 `n`, 값을 `k/N`에 스냅) | **통과** — GRIM은 소`N` 게이트(⑩ 범위 참조) |
| 완전 조작 연구: 사전등록·큰 `n`·공정 baseline·kill-condition·안정 시드 | **`full_audit` OK 통과** — 모든 숫자를 일관되게 지어냄 |
| 거짓말하는 스크립트를 `witness()` | **통과** — witness는 *스크립트가 실행돼 이 출력을 냈다*를 봉인하지, 출력이 *진실*임을 봉인 못 함 |

모든 방어(사전등록·audit·witness·anchor)는 데이터·코드가 정직하다는 가정 위에
섭니다. 측정거울은 *기록(paper trail)*을 단단하게 하지 *근저의 진실*을 단단하게
하지 않습니다.

**그래도 사는 것 — 사기가 겸손하도록 강요됩니다.** 통과하려면 거짓말이 겸손해야
합니다. 욕심을 부리면 프로브가 잡습니다:

| 욕심낸 거짓말 | 잡는 프로브 |
|---|---|
| baseline 대비 의심스럽게 큰 Δ | ⑦ `too_good_check` |
| 작은 표본 | ⑩ `grim_check`, ④a Wilson CI |
| 불안정/비현실적으로 완벽한 시드 | ⑤ `multiseed_check` |
| 검증보다 넓은 주장 | ⑥ `scope_check` |

그러니 측정거울의 진짜 일은 **작정한 사기를 잡는 게 아니라**(드물고 풀 수 없는
경우) **정직한 자기기만을 잡는 것**입니다 — p-해킹, 체리픽, 소`n` 과신, 성급한
종결. 이게 연구 부정직의 *흔한* 형태이고, 도구가 그걸 잡습니다. `OK`는
*"숫자가 내적으로 정직하고 과대하지 않다"*로 읽으세요, 절대 *"이건 진실이다"*로
읽지 마세요.

*(이 지도는 도구가 깨질 때까지 레드팀해서 그렸습니다 — 우리가 도구에 할 수 있는
가장 측정거울다운 일이었습니다.)*

---

*스스로의 프로젝트를 정직하게 죽이는 과정에서 만들어졌습니다. 제작자들이 자신들에게 먼저 적용했습니다.*  
*→ [개발 연대기](CHRONICLE.md)*
