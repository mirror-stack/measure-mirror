# 🪞 Measurement Mirror

<p align="center">
  <img src="docs/measure_mirror_og.png" alt="Measurement Mirror" width="500">
</p>

[![CI](https://github.com/mirror-stack/measure-mirror/actions/workflows/ci.yml/badge.svg)](https://github.com/mirror-stack/measure-mirror/actions/workflows/ci.yml)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![core deps: zero](https://img.shields.io/badge/core%20deps-zero-brightgreen.svg)](pyproject.toml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)

**AI 평가 주장의 거짓양성과 거짓음성을 자동으로 적발합니다.**  
훈련 불요 · 결정론적 · 코어는 stdlib만 사용 (Python 3.10+). 선택 모듈 `judge`·`subspace`는 의존성이 있습니다.

> 스스로의 연구를 정직하게 죽이는 과정에서 만들어진 도구입니다.  
> 만든 사람들이 자신에게 먼저 실행해봤습니다. → [🦋 탄생 배경](docs/CHRONICLE.md)

**[📖 프로브 완전 가이드 →](docs/GUIDE_KO.md)** — 28개 프로브 전체 설명·예제·워크플로우
**[📜 MIRROR-SPEC v1.1 →](docs/SPEC_KO.md)** — 원장 포맷·검증 프로토콜의 규범 명세(2026-07-02 비준·2026-07-17 개정; 이 패키지는 그 참조구현. 규범 정본은 [영어판](docs/SPEC.md))
**[🦋 측정착시 도감 →](catalog/README_KO.md)** — 측정이 만든 이를 속인 실제 봉인 사례 72표본(게이밍·자가적발·거짓음성 가드·오염)

> **🪞🔎🪪 New — 미러스택** ([`stack/`](stack/)): measure-mirror는 자율연구 에이전트용 3거울
> 무결성 스택(주장·행동·출처)의 *주장* 층입니다. 규약 5개 + `verify-all` 한 명령으로 묶이며,
> 실제 사례연구를 동봉했습니다:
> **[측정 토큰 한 푼도 쓰기 전에 스스로 실험을 철회한 에이전트](stack/CASE_STUDY_compute_governor_KO.md)**
> — 사전등록 → 검정력 체크가 설계 교정 → 적대 amendment → 선행연구 철회까지, 체인봉인된
> 원장 실물 포함(직접 검증 가능). 스택이 보증하는 것과 — 어떤 도구도 줄 수 없는 단 하나
> (독립성) — 는 네 기둥으로 정리돼 있습니다: **[PILLARS_KO.md](stack/PILLARS_KO.md)**
> (무결성 · 불소거 · 반증가능성 · 검증가능성). measure-mirror 본체는 그대로입니다(기능동결
> 코어 — 스택은 프로브가 아니라 규약을 추가).

| 도구 | 감사 대상 | 질문 |
|---|---|---|
| 🪞 **measure-mirror** (현재 위치) | AI 평가 주장 | **주장이 정직한가?** |
| 🪪 [action-mirror](https://github.com/mirror-stack/action-mirror) | 에이전트 행동 | 누가 뭘 했나, **증명 가능하게**? |
| 🔎 [provenance-mirror](https://github.com/mirror-stack/provenance-mirror) | 콘텐츠 진위 | **출처**가 증명되나? |
| 👁 [mirror-witness](https://github.com/mirror-stack/mirror-witness) | 운영자 간 증인 게시판 | 또 **누가 증인** 섰나? |

💬 **[Discussions](https://github.com/orgs/mirror-stack/discussions)** — 질문 · 아이디어 · 독립 재현 공유 환영.

---

## 문제

AI/ML 논문은 일상적으로 과장된 주장을 합니다. 가장 흔한 실패 패턴:

| 착시 | 발생 방식 |
|---|---|
| 소표본 신기루 | n=9, acc=55.6%를 획기적 성과로 보고 |
| 사후 지표 교체 | 정확도로 등록하고, 더 좋아 보이는 F1으로 보고 |
| 허약한 기준선 | 의도적으로 약한 경쟁자와 비교 |
| 데이터 누설 | 훈련/테스트 중복으로 수치 부풀리기 |
| 범위 과대 일반화 | "작업 A에서 동작" → "일반 추론 가능"으로 주장 |

Measurement Mirror는 이것들을 **구조적으로** 잡아냅니다. 의견이 아닌 규칙과 통계로.

> **정확히 무엇을 하나(그리고 안 하나).** *당신이 준 입력*에 결정론 검사를 돌립니다 — **입력 구동**이지
> 자율 결함탐색기가 아닙니다. 산술·통계 프로브(소표본 CI·GRIM·검정력·다중비교)는 완전 결정론. 그러나
> 설계결함 프로브(crippled baseline·gaming·scope)는 당신이 *선언한* baseline/reward항/scope에만 발동 —
> **숨긴 결함은 자율로 못 찾고**, 진짜 catch의 상당수는 여전히 *당신의 판단*입니다([규율](https://github.com/mirror-stack/measure-mirror/tree/main/stack/DISCIPLINE_KO.md) 가이드).
> 정직을 *증명 가능*하게 하지, *강제*하지 않습니다.

---

## 설치

```bash
pip install -e .                        # 코어 — stdlib만, 외부 의존성 없음
pip install -e ".[mcp]"                 # + AI 에이전트용 MCP 서버
pip install -e ".[judge]"               # + LLM-as-a-Judge 러너 (openai / anthropic)
pip install -e ".[subspace]"            # + ㉘ 부분공간 실행기 = B층 (numpy)
pip install -e ".[test]"                # + pytest 플러그인
pip install -e ".[mcp,judge,subspace,test]"   # 전부
```

CLI 진입점: `mm`  
MCP 진입점: `mm-mcp`

---

## 빠른 시작

### CLI

```bash
# Step 1 — 실험 실행 전: 기준 봉인
#   kill-condition을 반드시 포함 — 실패할 수 없는 주장은 반증 불가능합니다
mm register my_model --metric acc --min-n 200 --baseline 0.5 --pass 0.60 \
           --kill-threshold 0.55 --kill-direction below

# Step 2 — 평가 후: 봉인된 기준에 대해 결과를 감사
mm audit my_model --acc 0.72 --n 500   # 결과를 인라인으로 — 따로 만들 파일 없음

# …또는 직접 작성한 결과 파일로 감사:
echo '{"claim_id":"my_model","metric":"acc","acc":0.72,"n":500}' > my_model.json
mm my_model                            # my_model.json 자동 로드
mm audit --file my_model.json          # 임의 경로는 --file
```

`my_model.json` 형식: `{"claim_id": "my_model", "metric": "acc", "acc": 0.72, "n": 500}`

### Python API

```python
from measure_mirror import mm

LEDGER = "mm_ledger.jsonl"

# ① 실험 전 — 기준 봉인 (SHA-256 위변조 감지)
mm.preregister(LEDGER, "my_model",
               metric="acc", min_n=200, baseline=0.5, pass_threshold=0.60)

# ② 평가 후 — 7종 probe 일괄 감사
findings = mm.full_audit(
    LEDGER, "my_model",
    reported_metric="acc", reported_acc=0.72, n=500,
    baseline=0.5,
    competing_name="strong_baseline", competing_acc=0.68,   # ② 공정성
    reward_terms=["cross_entropy"],                          # ③ 게이밍 검사
    train_items=train_set, test_items=test_set,              # ④ 누설
    seed_results=[0.70, 0.72, 0.74],                         # ⑤ 다시드
    claimed_scope=["reasoning"], tested_scope=["task_a"],    # ⑥ scope
)
mm.report("my_model", findings)

# 개별 probe
mm.report("공정성", [mm.baseline_fairness("vs GRU", 0.72, 0.68)])
mm.report("누설",   [mm.leakage_check(train_items, test_items)])
mm.report("다시드", [mm.multiseed_check([0.70, 0.72, 0.74], baseline=0.5)])
```

### 회귀/연속 지표

MSE, Pearson r, RMSE 등 이진이 아닌 지표:

```python
findings = mm.continuous_audit(
    LEDGER, "my_regressor",
    reported_metric="mse", reported_value=0.10,
    baseline_value=0.15, n=500,
    higher_better=False,   # 낮을수록 좋음
    std=0.02,              # 선택: 효과크기 검사 활성화
)
mm.report("회귀 모델", findings)
```

### pytest 통합 (CI 게이트)

```python
# conftest.py
pytest_plugins = ["measure_mirror.pytest_plugin"]

# test_eval.py
from measure_mirror import mm
from measure_mirror.pytest_plugin import assert_clean

def test_my_model_is_real():
    findings = mm.audit("ledger.jsonl", "my_model",
                        reported_metric="acc", reported_acc=0.78, n=1000)
    assert_clean(findings)   # FAIL findings → 테스트 실패 → CI 빨간불
```

---

## 검증 3단계

28개 프로브를 외울 필요 없습니다 — 사용법은 정확히 세 가지입니다:

```bash
# 풀 검증 — 한 번에, 적용 가능한 모든 프로브 자동 실행
mm verify --file results.json

# 그룹단위 검증 — 검증 그룹으로 좁히기
mm verify --file results.json --groups stats judge
mm verify --list-groups

# 개별검증 — 아무 프로브나 직접 호출 (Python)
mm.grim_check(reported_acc=0.33, n=10)
```

```python
from measure_mirror import mm

# 풀: data에 있는 키 기준으로 프로브가 자동 활성화
findings = mm.verify("ledger.jsonl", {
    "claim_id": "my_model", "acc": 0.72, "n": 500,        # → ledger + stats
    "seed_results": [0.70, 0.72, 0.74],                    # → ⑤
    "scores": [3, 7, 5, 8, 4],                             # → judge ⑰
})

# 그룹: 같은 data, judge 그룹만
findings = mm.verify("ledger.jsonl", data, groups=["judge"])
```

`verify()`는 입력이 존재하는 프로브만 실행합니다 — 키가 없으면 안 돌고,
키를 추가하면 그만큼 더 돕니다. `data` 키는 JSON 파일 형식과 동일합니다.

## 검증 그룹별 Probe 목록

### `ledger` — 사전등록·원장 무결성

| Probe | # | 잡아내는 것 |
|---|---|---|
| `preregister` / `audit` | ① | 사후 지표 교체 · 표본 미달 · 원장 위변조 |
| `verify_chain` | ① | 엔트리 삭제/삽입 · 원장 위변조 |
| `cascade_check` | ⑫ | 주장 자신 또는 전이 의존성 철회 → FAIL/WARN 오래됨 |

### `stats` — 통계 유효성

| Probe | # | 잡아내는 것 |
|---|---|---|
| `audit` — Wilson CI | ④a | 통계적으로 우연과 구별 불가 (소표본) |
| `audit` — direction | ④a | 기준선보다 낮은 성능 (역신호) |
| `multiseed_check` | ⑤ | 불안정한 신호 / 운 좋은 시드 |
| `too_good_check` | ⑦ | 기준선 대비 지나치게 큰 개선폭 |
| `power_check` | ⑧ | n이 너무 작아 진짜 효과를 못 잡음 (거짓음성 가드) |
| `multiple_comparisons_check` | ⑨ | 같은 레저에 k>1 실험 → Bonferroni 교정 경보 |
| `grim_check` | ⑩ | 보고된 acc × n이 정수 k와 일치 불가 (수치 조작 적발) |

### `design` — 실험 설계 공정성

| Probe | # | 잡아내는 것 |
|---|---|---|
| `baseline_fairness` | ② | 허약한 / 동점 / 역전된 기준선 |
| `gaming_check` | ③ | 보상/손실에 평가 지표 직접 포함 (자기충족) |
| `leakage_check` | ④a | 훈련∩테스트 데이터 오염 |
| `scope_check` | ⑥ | 주장 범위 > 검증 범위 (과대 일반화) |
| `falsifiability_check` | ⑪ | kill-condition 없음→반증불가; kill_threshold 발화→주장 사망 |

### 봉인 품질 린트 ㉗ — 독립 실행, 연산 *전*에

| Probe | # | 잡아내는 것 |
|---|---|---|
| `prereg_lint` | ㉗ | 봉인의 *품질*(존재 여부가 아니라): kill-condition이 `metric` 필드로 누수(잘못된 호출 — 사람 눈엔 기준이 보이나 파서엔 없음), 정량 kill을 구조화된 `kill_threshold` 없이 자유텍스트로만 기재, pass 바가 선언된 우연(chance) 이하, `min_n`이 소표본 바닥 미만, 봉인 전 기계 체크 미선언 |

> ㉗은 의도적으로 `verify()` 우산·그룹에 **넣지 않았습니다**: 이것은 *연산 전* 체크(봉인 직후, 연산을 쓰기 전에 실행)이고, `verify()`/`audit()`은 보고 시점에 돕니다. `mm_register` 안에서 자동 발화하며(응답에 lint 동봉), mirror-stack compute 게이트는 ㉗ FAIL에 BLOCK합니다. 봉인 전에 돌린 값싼 체크는 `preregister(..., pre_seal_checks=["reachability-smoke", "mass-balance-audit", "neutral-control", "manipulation-check", "positive-control"])`로 선언하세요 — 미선언이면 INFO 넛지. 근거: 실제 실험 아크가 정확히 이 결함 클래스들로 무의미 연산을 잃었습니다(semantic-fuel 세포 아크, 2026-07; 자가적발 3건 도감 봉인).

### `negative` — 음성 종결 게이트

| Probe | # | 잡아내는 것 |
|---|---|---|
| `negative_audit` | ⑬ | 음성 결론에 독립 각도 부족·미등록 각도·범위 초과 탐지 |

### `subspace` — "이득이 소수 방향에 있다" 류 주장

⚠️ **재계산기가 아니라 선언 감사기입니다.** 제출된 표만 읽고 기저나 모델은 보지 않으므로, `energy_kept`를 거짓으로 적으면 통과합니다. 표 내부 정합 법칙 C1~C4는 거짓 표의 **비용을 올릴 뿐 구멍을 닫지 않습니다.**

| 프로브 | # | 탐지 |
|---|---|---|
| `subspace_claim_check` | ㉘ | 비트재현 앵커 미선언 · 팔 간 잔존 에너지 불일치 · 자유도 대조 부재 · target이 널 사다리를 못 넘음(짝지은 부호뒤집기 순열검정, n ≤ 14는 2ⁿ 완전열거) · 증서 미달 `matched_null` 팔(붕괴로도 생존으로도 세지 않음) · 격자 포화 · 기저를 추정한 표본으로 효과까지 평가 |

🔴 **한 실험 가문에서만 검증됐고, 두 번째 가문이 그 일반화를 죽였다.** 같은 심은 레시피를 다른 실기질(타 아크의 768차원 DINO 임베딩·봉인 `5c78e503`·결과 am `2ab6eab7`)에서 재생하니 **사전확약 바 1.0에 8/10**(FP=1·FN=1). 핵심 실패: **㉘에는 역할 뒤바꾼 주장에 대한 방어가 없었다** — `relabeled_dof`가 1기질에서 통과한 건 거기서 셔플 팔이 널을 못 이겼기 때문이지 기제가 있어서가 아니었다. 방어처럼 보였지만 **기질 운**이었다.

🟢 **v0.31.0에서 `dof-outperforms-target`으로 닫힘** — 휴리스틱이 아니라 정합성 법칙이다: 주장된 구조를 부수는 것이 효과를 *늘릴* 수는 없으므로, 대조가 처치를 이기면 라벨이 뒤바뀌었거나 그건 대조가 아니다. FM×CDE 홀드아웃 **22/22**로 봉인(`582f4130`·결과 am `45d5f3d2`)했고 기질-2의 거짓음성도 함께 닫힌다. 단, **진짜 처치가 자기 대조를 실제로 이길 때만** 잡는다 — 둘이 구분 안 되면 뒤바꿈도 안 보이고, 그때는 숨겨질 효과도 없다. 전문: [eval/subspace_substrate2/RESULTS.md](eval/subspace_substrate2/RESULTS.md).

#### ㉘ B층 — 실행기 (`measure_mirror.subspace`, numpy 필요)

```bash
pip install "measure-mirror[subspace]"
```

A층은 제출된 표를 감사합니다. **B층은 배열에서 그 표를 만들어** 곧바로 A층에 돌려줍니다 —
내 실행도 남의 주장과 똑같은 감사기 앞에 세우는 것입니다. B층이 A층을 대체하지 않고,
A층이 볼 수 있는 범위를 넓히지도 않습니다.

|  | A층 — `subspace_claim_check` | B층 — `measure_mirror.subspace` |
|---|---|---|
| 보는 것 | 제출된 표뿐 | 배열 |
| 의존성 | stdlib | numpy |
| 감사 대상 | 누구의 주장이든 | 내가 직접 돌린 것만 |
| 못 잡는 것 | 정합적 위조표 | 자기가 돌리지 않은 모든 것 |

B층만 할 수 있는 두 가지 — 표에는 담길 수 없는 것들입니다.

- **내용주소 표본 id.** `basis_fit_ids`·`effect_eval_ids`는 각 행의 float64 바이트 sha256이지
  위치 라벨이 아닙니다. 그래서 `estimation-eval-overlap`이 **실제 재사용**을 검사하고,
  분할 이름만 바꿔서는 빠져나갈 수 없습니다.
- **`overfit_smallsample`.** A층은 선언된 `n_basis_fit`으로 `underdetermined-basis`를 **린트**할
  뿐입니다. 그 정도 표본으로 뽑은 기저가 *실제로* 잡음 방향에 정렬됐는지는 추정 실행의 속성이라
  표가 담을 수 없습니다. B층은 그것을 직접 돌립니다: 합성 등방 가우시안·신호 0·
  `n_basis ∈ {20, 50, 200}`에서 target 팔이 널 사다리를 넘으면 안 됩니다.
  **양성대조를 모든 `n`에서 돌립니다** — 안 그러면 "n=20에서 안 이겼다"와
  "계기가 n=20에서 눈이 멀었다"가 구분되지 않습니다. 양성대조가 안 터진 `n`은 통과로 세지 않고
  **보류(withheld)**로 보고합니다.

이 둘은 `verify()` probe가 아니라 실행기이므로 위 probe 개수에 **의도적으로 포함하지 않습니다**.



### `judge` — LLM 판정자 신뢰성

| Probe | # | 잡아내는 것 |
|---|---|---|
| `judge_consistency_check` | ⑭ | LLM 판정자 뒤집기율 초과 — 신뢰 불가 판정자 감지 |
| `judge_bias_check` | ⑮ | 판정자가 A 또는 B 위치를 체계적으로 선호 — 위치 편향 감지 |
| `inter_rater_agreement` | ⑯ | 서로 *다른* 두 판정자 간 Cohen's κ 미달 (단독 전용) |
| `judge_score_sanity` | ⑰ | 판정자가 동일/근사 점수만 부여 — 퇴화 분포 감지 |
| `judge_swap_check` | ⑱ | AB→BA 교환 후에도 같은 슬롯 선택 — 내용 아닌 위치를 읽는 판정자 |

### `ranking` — 순위(리더보드) 무결성

| Probe | # | 잡아내는 것 |
|---|---|---|
| `judge_transitivity_check` | ⑲ | A>B>C>A 순환 선호 — 일관된 품질 척도가 없는 판정자 |
| `ranking_stability_check` | ⑳ | "A가 B를 이김"이 부트스트랩 리샘플링에서 뒤집힘 — 순위 신기루 |

| 유틸리티 | 역할 |
|---|---|
| `anchor` | 변조 방지 원장 스냅샷(해시+헤드 봉인) stdout 출력 → 외부 보관 |
| `calibrate` | 자가 테스트: 5종 합성 케이스로 도구 정상 작동 확인 |
| `witness` | 커맨드 실행·출력 캡처·변조 방지 실행 봉인 원장에 기록 |
| `retract` | 체인 연결 철회 엔트리 추가 → 의존 주장 cascade_check에서 STALE |
| `certificate` | 봉인된 검증 인증서 발행: CERTIFIED / WITH-WARNINGS / UNVERIFIED / REJECTED |
| `badge` | 인증서를 임베드 가능한 markdown / SVG 배지로 렌더링 (verdict 색상) |

### 체인 해시 원장 (① 확장)

모든 `preregister()` 호출이 이전 엔트리의 seal을 포함하고 SHA-256을 계산합니다.
원장 파일 전체가 위변조 방지 체인이 됩니다:

```python
# 언제든지 원장 체인 전체 검증
findings = mm.verify_chain("mm_ledger.jsonl")
mm.report("원장 무결성", findings)
```

적발 범위: 엔트리 삭제, 삽입, 내용 수정.  
**명시된 한계**: 파일 통째 삭제 + 새 등록은 못 잡음 — git 커밋으로 보완.

### 검정력 probe ⑧

```python
# n이 진짜 효과를 잡기에 충분한지 사전 경고
f = mm.power_check(n=50, baseline=0.5, min_detectable_effect=0.05)
# ⚠️  n=50은 Δ=+0.05 탐지에 부족 (필요 n≥388, 80% 검정력)

# full_audit에서 활성화
findings = mm.full_audit(LEDGER, "my_model", ..., min_detectable_effect=0.05)
```

### 다중비교 probe ⑨

```python
# 같은 레저에 k>1 실험이 있으면 Bonferroni 교정 경보
f = mm.multiple_comparisons_check("mm_ledger.jsonl")
# ⚠️  k=3 실험 → Bonferroni α=0.0167 (0.05가 아님)

# full_audit에서 활성화
findings = mm.full_audit(LEDGER, "my_model", ..., check_multiplicity=True)
```

### 반증가능성 ⑪ — 포퍼 게이트

```python
# 실험 전 — 주장을 죽이는 조건까지 봉인
mm.preregister("mm_ledger.jsonl", "my_model",
               metric="acc", min_n=200, baseline=0.5, pass_threshold=0.60,
               kill_condition="held-out 테스트에서 정확도 0.55 미만",
               kill_threshold={"metric": "acc", "threshold": 0.55, "direction": "below"})

# 실험 후 — audit()이 ⑪을 자동 실행
findings = mm.audit("mm_ledger.jsonl", "my_model",
                    reported_metric="acc", reported_acc=0.50, n=500)
# 🔴 [⑪ falsifiability] Kill condition triggered: acc=0.5 < 0.55.
#    Claim 'my_model' is falsified by its own pre-registered criterion.
```

```bash
mm register my_model --metric acc --min-n 200 --baseline 0.5 --pass 0.60 \
  --kill "0.55 미만이면 사망" --kill-threshold 0.55 --kill-direction below
```

kill-condition 없이 등록된 주장은 audit 시점에 `WARN: Unfalsifiable`을 받습니다.
OSF 사전등록도 가설만 받지 죽음조건은 받지 않습니다 — 이 도구가 최초입니다.

### 철회 cascade ⑫

```python
# 의존성이 있는 주장 등록
mm.preregister("mm_ledger.jsonl", "model_v2",
               metric="acc", min_n=200, baseline=0.5, pass_threshold=0.60,
               depends_on=["dataset_v1", "baseline_eval"])

# 나중에 dataset_v1에서 오염 발견 → 철회
mm.retract("mm_ledger.jsonl", "dataset_v1", "훈련/테스트 중복 발견")

# cascade_check가 model_v2를 자동으로 STALE 표시
f = mm.cascade_check("mm_ledger.jsonl", "model_v2")
# ⚠️  [⑫ retraction-cascade] Claim 'model_v2' is STALE: depends (transitively) on
#     retracted claim(s): 'dataset_v1'

# audit()에서 cascade_check 자동 실행 (WARN/FAIL만 추가)
findings = mm.audit("mm_ledger.jsonl", "model_v2",
                    reported_metric="acc", reported_acc=0.72, n=500)
```

```bash
mm register model_v2 --metric acc --min-n 200 --baseline 0.5 --pass 0.60 \
  --depends-on dataset_v1 baseline_eval

mm retract dataset_v1 --reason "훈련/테스트 중복 발견"
```

철회 엔트리는 **체인 연결**되어 있어 삭제하면 `verify_chain()`에서 즉시 탐지됩니다.
발표 순서와 관계없이 철회가 전파됩니다: 철회된 기반 위에 세운 주장은 자동으로 오래된 것이 됩니다.

### 음성 주장 감사 ⑬ — 성급종결 게이트

단일 음성 결과는 frame 결함일 수 있습니다. `negative_audit`는 "Resolved-Negative"
결론에 대한 게이트입니다: 종결 전 최소 `min_angles`개의 독립 사전등록 실험이 수렴해야 합니다.

```python
# 각 독립 각도를 실험 전 등록
for angle_id in ["oee_test_wave", "oee_test_bilinear", "oee_test_alife"]:
    mm.preregister("mm_ledger.jsonl", angle_id,
                   metric="oee_score", min_n=100, baseline=0.5, pass_threshold=0.0)

# 모든 각도가 음성으로 수렴한 후 — 결론 게이트
f = mm.negative_audit("mm_ledger.jsonl",
                      angles=["oee_test_wave", "oee_test_bilinear", "oee_test_alife"])
# ✅ [⑬ negative-audit] 3/3 독립 사전등록 각도 검증 — 음성 결론 지지

# 선택사항: 결론 범위가 검증 범위보다 넓으면 FAIL
f = mm.negative_audit("mm_ledger.jsonl",
                      angles=["oee_test_wave", "oee_test_bilinear", "oee_test_alife"],
                      conclusion_scope=["all_substrates"],
                      tested_scope=["in_silico"])
# 🔴 [⑬ negative-audit] 검증되지 않은 범위 포함: ['all_substrates']
```

```bash
mm negative --angles oee_test_wave oee_test_bilinear oee_test_alife --min-angles 3
```

### LLM-as-a-Judge 프로브 ⑭⑮⑯⑰

LLM 판정자(judge)는 숫자 지표로는 잡을 수 없는 고유한 실패 패턴을 가집니다.
4개 프로브는 평가받는 모델이 아니라 **판정자 자체**를 감사합니다.

```bash
pip install "measure-mirror[judge]"   # openai · anthropic 의존성 추가
```

```python
from measure_mirror.judge import anthropic_judge, openai_judge, judge_run

# 판정자 callable 생성 (pairwise A-vs-B 모드)
judge_fn = anthropic_judge(model="claude-opus-4-8")
# 또는: judge_fn = openai_judge(model="gpt-4o")

# 각 아이템: {"prompt": str, "a": str, "b": str}  (pairwise)
#            {"prompt": str, "response": str}       (rating, pairwise=False)
pairs = [
    {"prompt": "양자 얽힘을 요약하세요",
     "a": "후보 A 출력", "b": "후보 B 출력"},
    ...
]

# judge_run: judge_fn을 runs×len(items)회 호출하고,
# ⑭⑮⑯⑰(⑱)를 자동 발화한 뒤 체인 연결 원장 엔트리를 봉인합니다.
result = judge_run("mm_ledger.jsonl", "my_llm_eval",
                   judge_fn=judge_fn,
                   items=pairs,
                   runs=2,               # 동일 아이템 2회 실행 → ⑭ 일관성
                   pairwise=True,        # A-vs-B → ⑮ 편향 검사
                   swap_positions=True)  # AB→BA 추가 패스 → ⑱ 스왑 검사

for f in result["findings"]:
    print(f"  {f.level}  [{f.probe}]  {f.msg}")
```

**`judge_run`이 자동으로 실행하는 검사:**

| 프로브 | 잡아내는 것 |
|---|---|
| `judge_consistency_check` ⑭ | 재실행 시 다른 판정 (확률적 / 신뢰 불가) |
| `judge_bias_check` ⑮ | 내용에 관계없이 A 또는 B 위치를 체계적으로 선호 |
| `judge_score_sanity` ⑰ | 모든 것에 동일하거나 거의 동일한 점수 부여 |
| `judge_swap_check` ⑱ | AB→BA 교환 후에도 같은 슬롯 선택 (내용을 안 읽는 판정자) |

⑯ `inter_rater_agreement`은 **단독 전용**입니다: 서로 다른 두 판정자를 비교하는
용도이며, 같은 판정자의 재실행은 ⑭가 이미 커버합니다.

파싱 불가 응답은 -1로 기록되고 **모든 프로브에서 제외**됩니다. 실패율 10% 초과 시
`judge-parse` WARN, 전부 실패 시 FAIL이 발화됩니다.

**⑱이 중요한 이유** — 응답을 전혀 안 읽는 결정론적 판정자는 ⑭(완벽한 일관성),
⑮(균형 잡힌 승률), ⑯(κ=1.0), ⑰(다양한 점수)를 전부 통과합니다.
A와 B를 교환하는 것만이 정체를 드러냅니다: 내용을 읽는 판정자는 판정을 뒤집어야 하고,
내용을 안 읽는 판정자는 같은 슬롯을 계속 고릅니다. 데모로 확인하세요:

```bash
python examples/demo_judge.py   # API 키 불필요 — mock 판정자
```

**단독 사용 (점수 리스트를 직접 전달):**

```python
from measure_mirror import mm

# ⑭ 일관성 — 판정자가 뒤집었나?
score_pairs = [(1, 1), (0, 0), (1, 0), (0, 0), (1, 1)]  # (런1, 런2) per item
f = mm.judge_consistency_check(score_pairs, flip_threshold=0.20)
# ✅  뒤집기율 20.0% ≤ 20.0% (1/5 flips). 일관성 있음.

# ⑮ 위치 편향 — A가 항상 이기나?
results = [0, 0, 0, 0, 0, 0, 0, 1, 0, 0]  # 0=A승, 1=B승
f = mm.judge_bias_check(results, bias_threshold=0.60)
# 🔴  Position A win rate 90.0% > 60.0%. 강한 위치 편향 감지.

# ⑯ 평가자 간 일치도 — Cohen's κ
matrix = [(1, 1), (0, 0), (1, 1), (0, 1), (1, 0), (0, 0)]
f = mm.inter_rater_agreement(matrix, min_kappa=0.40)
# ⚠️  Cohen's κ=0.333 < 0.40 — fair agreement only.

# ⑰ 점수 건전성 — 퇴화 분포?
scores = [8, 8, 8, 8, 8, 8, 8, 7, 8, 8]  # 90%가 8
f = mm.judge_score_sanity(scores)
# ⚠️  90% of scores are '8' — near-degenerate distribution.

# ⑱ 위치 스왑 — 판정이 내용을 따르나, 슬롯을 따르나?
forward = [0, 1, 0, 1, 0]   # (A, B) 순서 승자
swapped = [0, 1, 0, 1, 0]   # AB→BA 교환 후 승자 — 동일 = 위치 고착!
f = mm.judge_swap_check(forward, swapped)
# 🔴  Position-lock rate 100.0% > 65.0%. 판정자가 내용이 아닌 위치를 읽고 있음.

# ⑲ 이행성 — 판정자에게 일관된 품질 척도가 있나?
matches = [("gpt", "claude", 0), ("claude", "llama", 0), ("llama", "gpt", 0)]
f = mm.judge_transitivity_check(matches)
# 🔴  순환 선호 적발: gpt > claude > llama > gpt.
#     이 판정으로 만든 리더보드는 대진 순서의 산물.

# ⑳ 순위 안정성 — "A가 B를 이김"이 리샘플링을 버티나?
f = mm.ranking_stability_check(scores_model_a, scores_model_b)
# 🔴  순위 'A > B'가 1000회 부트스트랩 중 64.2%만 유지 (n=7).
#     순위는 노이즈 — 동점과 구별 불가.
```

```bash
# CLI: 수집된 판정 점수를 JSON 파일로 감사
mm judge --file judge_scores.json
# 키: score_pairs / pairwise_results / ratings_matrix / scores /
#     forward_results + swapped_results / matches / scores_a + scores_b
```

### 인증서(Certificate) 📜 — 주장당 하나의 봉인된 판정

`certificate()`는 주장의 전체 무결성 상태를 논문·README·릴리스 노트에 삽입 가능한
하나의 검증 가능 산출물로 압축합니다:

```python
# 구조 인증서 (사전등록 봉인 + 체인 + 철회 상태)
cert = mm.certificate("mm_ledger.jsonl", "my_model")

# 완전 인증서 — 감사 결과까지 포함
findings = mm.audit("mm_ledger.jsonl", "my_model",
                    reported_metric="acc", reported_acc=0.72, n=500)
cert = mm.certificate("mm_ledger.jsonl", "my_model", findings=findings)
# {"verdict": "CERTIFIED", "prereg_seal": "6c802655ab095e8b",
#  "anchor_hash": "sha256...", "findings": {"ok": 4, "warn": 0, "fail": 0},
#  "seal": "9d1e83a4b72f0c5e", ...}
```

```bash
# CLI
mm certify my_model --pretty                  # 구조만
mm certify my_model --acc 0.72 --n 500        # + 감사 결과 포함
mm certify my_model | gh gist create -        # 외부 공개
```

| 판정 | 의미 |
|---|---|
| `CERTIFIED` | 사전등록·체인 무결·미철회·FAIL/WARN 없음 |
| `CERTIFIED-WITH-WARNINGS` | 유효하나 오래된 의존성 또는 WARN 존재 |
| `UNVERIFIED` | 사전등록 없음 — 인증할 기준이 없음 |
| `REJECTED` | 체인 파손·봉인 변조·철회됨·FAIL 존재 |

인증서는 원장의 `anchor_hash`를 포함하므로 **특정 원장 상태 하나**를 보증합니다.
인증서 자체도 봉인되어 있어 필드 수정은 즉시 탐지됩니다.

**배지 🏷 — verdict를 README에 임베드:**

```bash
mm certify my_model --badge markdown >> README.md   # shields.io 배지
mm certify my_model --badge svg > badge.svg          # 오프라인 자체완결 SVG
```

```python
cert = mm.certificate("mm_ledger.jsonl", "my_model")
print(mm.badge(cert))                 # markdown (기본)
print(mm.badge(cert, fmt="svg"))      # 인증서 seal이 툴팁에 포함된 SVG
# ![🪞 my_model: CERTIFIED](https://img.shields.io/badge/🪞_my__model-CERTIFIED-brightgreen)
```

배지 색상은 verdict를 따릅니다: CERTIFIED = 초록 · WITH-WARNINGS = 노랑 ·
UNVERIFIED = 회색 · REJECTED = 빨강. SVG 버전은 인증서 seal과 anchor-hash
접두사를 툴팁에 내장해, 배지가 어떤 봉인된 인증서를 렌더링한 것인지 추적 가능합니다.

### 앵커(Anchor) ⎈

```bash
# 변조 방지 원장 스냅샷을 stdout으로 출력 — 신뢰하는 곳에 파이프
mm anchor                              # 컴팩트 JSON (기본)
mm anchor --pretty                     # 사람이 읽기 쉬운 형태

# 외부 보관 예시 (추가 의존성 없음)
mm anchor >> ~/Dropbox/mm_anchors.jsonl        # 로컬 백업
mm anchor | gh gist create -                   # GitHub Gist
```

```python
a = mm.anchor("mm_ledger.jsonl")
# {"_type": "anchor", "ts": "...", "entry_count": 3,
#  "head_seal": "a3b9f2c1", "anchor_hash": "sha256hex...", "chain_ok": true}
```

`anchor_hash`(원장 파일 전체 SHA-256)는 **파일 통째 교체**까지 감지합니다 — 체인 해시만으로는 잡을 수 없는 유일한 공격. 결과 공개 전 외부에 저장하세요.

### 보정(Calibrate) + 증인실행(Witness run)

```bash
# 거울 자체가 정상 작동하는지 확인
mm calibrate
# ✅ [⚙ calibrate] 5/5 케이스 정상 — 거울이 보정되었습니다.

# 증인 실행: 먼저 보정하고, 커맨드 실행 후 봉인 기록
mm run my_model -- python evaluate.py --model my_model
```

```python
# Python API
findings = mm.calibrate()
mm.report("거울 보정", findings)

entry = mm.witness("mm_ledger.jsonl", "my_model",
                   ["python", "evaluate.py", "--model", "my_model"])
# entry["output_hash"]은 스크립트 출력이 바뀌면 달라짐
```

### GRIM probe ⑩

```python
# 산술적으로 불가능한 정확도 수치 적발
f = mm.grim_check(reported_acc=0.33, n=10)
# 🔴  acc=0.33은 n=10에서 산술적으로 불가능합니다.
#     round(k/10, 2) = 0.33을 만족하는 정수 k가 없습니다.
#     (후보: k=3 → 0.3, k=4 → 0.4). 수치 조작 또는 n 오기재.

# audit() 내부에서 자동 실행 — FAIL일 때만 findings에 추가됨
findings = mm.audit(LEDGER, "my_model", reported_metric="acc", reported_acc=0.33, n=10)
```

---

## MCP 서버 — AI 에이전트 연동

MCP 호환 AI(Claude Code, Cursor, Windsurf 등)가 대화 중에 Measurement Mirror를 직접 호출할 수 있습니다.

### 설정

```bash
pip install "measure-mirror[mcp]"
```

**Claude Code** — 프로젝트 루트의 `.mcp.json`에 추가:

```json
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

**기타 MCP 클라이언트** — stdio 서버 명령으로 `mm-mcp`를 실행하세요.

28종 probe + 6 유틸리티 + `mm_verify` 우산까지 전부 MCP 도구로 노출됩니다(총 38개):  
`mm_verify` (풀 / 그룹 필터) ·  
`mm_register` · `mm_verify_chain` · `mm_audit` · `mm_continuous_audit` · `mm_full_audit` ·  
`mm_baseline_fairness` · `mm_gaming_check` · `mm_leakage_check` · `mm_multiseed_check` · `mm_scope_check` ·  
`mm_anchor_basis_check` · `mm_threshold_provenance_check` · `mm_content_delta_check` ·  
`mm_anchor_line_source_check` · `mm_anchor_cell_check` ·  
`mm_too_good_check` · `mm_power_check` · `mm_multiple_comparisons_check` · `mm_grim_check` ·  
`mm_falsifiability_check` · `mm_prereg_lint` · `mm_cascade_check` · `mm_negative_audit` ·  
`mm_subspace_claim_check` ·  
`mm_judge_consistency_check` · `mm_judge_bias_check` · `mm_inter_rater_agreement` ·  
`mm_judge_score_sanity` · `mm_judge_swap_check` · `mm_judge_transitivity_check` ·  
`mm_ranking_stability_check` ·  
`mm_anchor` · `mm_calibrate` · `mm_witness` · `mm_retract` · `mm_certificate` · `mm_badge`

---

## 실제 적발 사례 — 도그푸딩

자체 AI 연구에 Measurement Mirror를 실행해서 잡아낸 것들:

```
🪞 Audit: ZERO "55.6% Best" 주장
   🔴 FAIL
   🔴 [④a small-sample CI] n=9, acc=0.556 → 95%CI [0.267, 0.811] ⊃ baseline(0.5)
       통계적으로 우연과 구별 불가.
   🔴 [① pre-registration(min_n)] 보고 n=9 < 등록 min_n=200. 표본 미달.
   🔴 [① pre-registration(metric-swap)] 보고 'best_of_9' ≠ 등록 'acc_full_balanced'
       사후 지표 교체 적발. (seal=6c802655ab095e8b)

🪞 Audit: Field 후보5 (제어 시뮬레이션)
   🔴 FAIL
   🔴 [② fair-baseline] Field 0.996 ≈ GRU-ODE 0.998 (Δ+0.002 < 0.01). 동점 — 진짜 우위 없음.
```

데모 직접 실행:

```bash
python examples/quickstart.py    # 정직한 연구자 정상 경로
python examples/demo_zero.py     # ZERO 55.6% 신기루 (우리 프로젝트 자가 폐기)
python examples/demo_field.py    # Field 후보 거짓양성
```

---

## 프로젝트 구조

```
measure-mirror/
├── measure_mirror/
│   ├── mm.py              # verify() + probe ①~㉘ + CLI + DB 조회 (stdlib만)
│   ├── mcp_server.py      # MCP 서버 — 37개 도구 (pip install .[mcp])
│   ├── judge.py           # LLM-as-a-Judge 러너 (pip install .[judge])
│   ├── subspace.py        # ㉘ B층 실행기 — numpy (pip install .[subspace])
│   └── pytest_plugin.py   # assert_clean() — CI 게이트
├── docs/
│   ├── GUIDE.md           # 프로브 완전 가이드 (영문)
│   └── GUIDE_KO.md        # 프로브 완전 가이드 (한국어)
├── examples/
│   ├── quickstart.py      # 정상 경로 데모
│   ├── demo_zero.py       # ZERO 거짓양성 (도그푸딩)
│   ├── demo_field.py      # Field 거짓양성 (도그푸딩)
│   ├── demo_judge.py      # LLM 판정자 실패 유형 (API 키 불필요)
│   └── mcp_example.py     # MCP 도구 사용 참고
├── db/                    # 로컬 기억, 생산 주체별로 분리
│   ├── README.md              measured/ vs curated/ 구분 설명
│   ├── measured/             ← 측정거울 자체 출력 (정량)
│   │   ├── baselines.json         작업별 공정 기준선
│   │   └── reproductions.jsonl    재현 이력 (verdict 자동판정)
│   └── curated/              ← 사람 큐레이션 (정성)
│       ├── self_catches.jsonl          자체 적발 거짓양성
│       ├── false_negative_guards.jsonl 재검증한 거짓음성
│       ├── gaming_patterns.json        게이밍 시그니처
│       ├── contamination.jsonl         데이터 누설
│       └── research_closures.jsonl     정성 음성 결론
└── tests/
    ├── test_mm.py         # 145개 코어 프로브 테스트, CI 강제
    ├── test_judge.py      # 17개 judge.py 모듈 테스트
    └── test_sync.py       # sync gate: probe ↔ MCP ↔ 테스트 ↔ README ↔ 노출 ↔ 버전
```

---

## 헬퍼 함수

프로브와 함께 export되는 공개 API입니다. `__all__`이 이들을 약속하고 있으므로,
소스를 읽어야 알 수 있게 두지 않고 여기 문서화합니다.

| 함수 | 시그니처 | 반환 |
|---|---|---|
| `wilson_ci` | `wilson_ci(k, n, z=1.96)` | `n`회 중 `k`회 성공에 대한 Wilson 점수 구간 `(lo, hi)`. `audit()`이 보고된 정확도가 기준선을 실제로 넘는지 판정할 때 씁니다. `n <= 0`이면 0으로 나누지 않고 `(0.0, 1.0)`을 반환합니다. |
| `lookup_baseline` | `lookup_baseline(task, db_dir=None)` | `db/`에 기록된 해당 과제의 기준선. 모르는 과제면 `None`. 기준선을 넘기지 않았을 때 `audit()`이 채워 넣습니다. |
| `lookup_reproduction` | `lookup_reproduction(task, db_dir=None)` | `db/`에 기록된 이 과제의 **실패한** 재현 이력. 남들이 이미 재현에 실패한 결과를 새 증거로 읽으면 안 됩니다. |

```python
from measure_mirror import wilson_ci, lookup_baseline, lookup_reproduction

lo, hi = wilson_ci(780, 1000)          # (0.7533, 0.8046)
base = lookup_baseline("my_task")      # 기록 없으면 None
prior = lookup_reproduction("my_task") # 실패 이력 없으면 []
```

## 로컬 기억 (`db/`)

`db/`는 **내 과거 감사의 로컬 기억**입니다 — 공유/크라우드 DB가 아닙니다.
"CVE / 공유 시그니처" 프레이밍을 시도했지만 **우리에겐 값을 못 했습니다**(보편
법칙이 아니라 우리 맥락의 관찰): 기여하려면 *내 연구가 틀렸던 것*(`self_catches`)
이나 *동료의 재현 실패*(`reproductions`)를 공개해야 하는데, 이건 신뢰 ⊥ 평판
딜레마에 부딪힙니다. 인센티브가 맞는 팀은 공유 DB를 유지할 수도 있지만 — 우리는
아니었고, 아래 가치는 어차피 공유가 필요 없습니다.

*실제로* 성립하는 가치는 공유가 전혀 필요 없습니다: **과거의 내가 이미 데였던
패턴을 미래의 나에게 경고.** 데이터가 아무리 민감해도 작동합니다 — 내 머신을 절대
안 떠나니까요.

`db/`는 **레코드를 누가 생산했나**로 분리됩니다. 두 종류가 절대 헷갈리지 않도록
물리적으로 나눴습니다 (전체 구조는 [`db/README.md`](db/README.md)):

### `db/measured/` — 측정거울이 쌓는 것 (정량)

verdict를 측정거울이 직접 계산; 같은 수치로 재실행하면 같은 verdict가 정확히
나옵니다. audit 루프에 연결돼 있고, `record_reproduction()`으로만 자랍니다.

| 파일 | 사용 방식 |
|---|---|
| `measured/baselines.json` | `audit(task="musr")`가 공정 기준선 자동 조회 |
| `measured/reproductions.jsonl` | `audit(task=...)`가 과거 재현실패 경고; `record_reproduction(...)`이 추가(Wilson CI로 verdict 자동판정) |

```python
# 기억이 자란다: 주장을 재현하고 결과를 기록
mm.record_reproduction("musr", claim="ZERO 55.6%", acc_claimed=0.556,
                       n_claimed=9, acc=0.385, n=1050, note="대표본서 붕괴")
# → verdict 자동판정 FAIL, db/measured/reproductions.jsonl에 추가

# 나중에: 같은 과제의 어떤 audit이든 자동으로 경고를 띄움
mm.audit("ledger.jsonl", "new_claim", reported_metric="acc",
         reported_acc=0.62, n=120, task="musr")
# ⚠️ [⚙ prior-reproduction] task 'musr' has a prior reproduction failure:
#    'ZERO 55.6%' claimed 0.556 (n=9) → reproduced 0.385 (n=1050). 대표본서 붕괴
```

### `db/curated/` — 우리가 손으로 만든 것 (정성)

**적발 이력(catch log)** 과 연구 결론 — 사람 큐레이션이지 측정거울 자동 출력이
*아닙니다*. `catch_history()`로 조회하되, `audit()`에 자동 연결은 **안 됩니다**
(매칭이 깔끔한 `task` 키가 아닌 모호한 텍스트라 자동경고하면 거짓양성).

| 파일 | `kind` | 무엇의 적발 이력 |
|---|---|---|
| `curated/self_catches.jsonl` | `self_catch` | 내 작업에 대한 거짓*양성* 적발 |
| `curated/false_negative_guards.jsonl` | `false_negative` | 재검증한 거짓*음성* |
| `curated/gaming_patterns.json` | `gaming` | 목격한 게이밍/신기루 시그니처 |
| `curated/contamination.jsonl` | `contamination` | 발견한 데이터 누설 |
| `curated/research_closures.jsonl` | `closure` | 정성 음성 결론 (`acc`/`n` 없음 — 측정거울 verdict **아님**) |

```python
mm.catch_history(db_dir="db")                  # 전체 큐레이션 레코드
mm.catch_history(kind="gaming", db_dir="db")   # 게이밍 수법 카탈로그만
mm.catch_history(source="fm_cde_pixel_feasibility")  # 특정 아크 관련
```

**분리가 정직한 이유**: `db/` 전체를 "측정거울 이력"이라 부르면 과대주장입니다 —
`measured/`만 그렇습니다. `measured/`의 모든 레코드는 교차검증됐습니다: `(acc, n)`을
측정거울 자체 Wilson-CI 로직에 다시 넣으면 기록된 verdict가 **0건 불일치**로 재현됩니다.

---

## 설계 원칙

- **코어는 stdlib만** — 범위를 붙여서 말합니다. 선택 모듈 `judge`는 openai/anthropic,
  선택 모듈 `subspace`(㉘ **B층**)는 numpy를 씁니다. **stdlib 전용인 것은 코어와 A층
  감사기들이지 패키지 전체가 아닙니다** — 그 단서를 떼고 "의존성 0"이라고만 말하는 것이
  도감 항목 [zero-dep-scope-overgeneralize](catalog/self-catch/zero-dep-scope-overgeneralize.md)가
  기록한 과대일반화이고, 바로 이 문서에서 한 번 적발됐습니다.
- **양방향 감지** — 거짓 *양성* **과** 거짓 *음성* 모두 잡음. 성급한 음성 종결도 착시임.
- **위변조 감지 사전등록** — 첫 쓰기에 SHA-256 봉인. 재등록은 무시됨. 원장 조작은 매 감사마다 감지됨.
- **독립적 probe** — 각 검사는 독립 함수. 기존 코드 건드리지 않고 새 검사 추가 가능.
- **기본이 의심** — "너무 좋은 결과"는 믿기 전에 먼저 플래그됨.

---

## 기여

새 probe, 거짓양성/음성 사례, 기준선 기여를 환영합니다.

1. Fork → 브랜치 → PR
2. **`db/baselines.json`**: 공유 가능한 과제 기준선 (내 비공개 실패가 아니라)
3. **새 probe**: `mm.py`에 함수 추가 + `tests/test_mm.py`에 테스트 추가
4. CI 녹색 유지: `pytest tests/`

---

## 라이선스

[Apache 2.0](LICENSE)

---

[English README](README.md)
