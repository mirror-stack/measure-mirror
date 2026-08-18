# 측정착시 도감 — Catalog of Measurement Illusions

> A field guide to the ways AI evaluation deceives its own authors — every
> entry backed by a real, recorded case from our own research (no invented
> examples). Like CWE for software weaknesses, but for measurement.

측정이 측정한 사람을 속인 **실제 사례**의 카탈로그다. 항목은 전부 우리 연구
아크에서 실제로 발생하고 적발된 것들이며(출처=`db/curated/` + 원장 seal),
창작 사례는 넣지 않는다. 안티바이러스 시그니처처럼 쓴다: 새 결과가 어떤
항목의 증상과 일치하면, 먼저 그 착시를 배제하고 나서 결과를 믿는다.

## 분류 (v2.6: 73항목)

| 디렉토리 | 뜻 | 항목 수 |
|---|---|---|
| [gaming/](gaming/) | 게이밍/신기루 수법 — 지표가 실력 없이 오르는 길 | 19 |
| [self-catch/](self-catch/) | 자가적발 — "너무 좋다"를 스스로 의심해 잡은 거짓양성 | 29 |
| [fn-guard/](fn-guard/) | 거짓음성 가드 — 음성을 믿기 전 확인해야 했던 것 | 20 |
| [contamination/](contamination/) | 데이터/인코딩 오염 — 측정 이전에 무너진 입력 | 5 |

## 🔴 축이 둘이다 — 디렉토리 하나로는 안 갈린다 (2026-08-18 실측)

**디렉토리 이름은 두 축이 섞여 있다.** `self-catch` 는 *누가 잡았나*(발견경로)이고,
나머지 셋은 *무엇이 틀렸나*(오류유형)다. 형제처럼 나열돼 있지만 직교한다.

측정으로 드러났다. 이 도감을 안 본 독립 판정자에게 **원본 기록만** 주고 4개 중 하나를
고르게 했더니(n=52 · 봉인 `539d7a76…`):

| | |
|---|---|
| 정확도 | **29/52 = 0.558** (문턱 0.652 · 🔴KILL) |
| 가장 큰 혼동 | **self-catch 24건 중 10건이 fn-guard 로** |

판정자가 둔해서가 아니라 **갈 곳이 없어서**다. *"우리 검사 도구가 정상인 것을 FAIL 냈다"* 는
기록은 네 칸 어디에도 안 맞고, `fn-guard` 가 가장 가까운 오답이 된다.

⇒ **오류유형 축에 최소 세 칸이 비어 있었다**: `instrument-misfire`(계기가 정상을 FAIL) ·
`attribution`(요인 분리 없는 귀속) · `prereg-defect`(봉인문 자체의 결함).

### 그래서 무엇을 했나
`self-catch/` 의 29개 표본 각각에 **`오류유형` 한 줄을 추가**했다. 디렉토리는 안 옮겼다 —
경로가 밖에서 참조되고 있어서다. 라벨은 **두 코더가 독립으로** 붙였고(한 명은 도감을 만든
쪽, 한 명은 문맥 없는 독립 판정자), **일치 23 / 이견 6 · 일치율 79.3%** 였다.
**이견 6건은 어느 쪽으로도 확정하지 않고 두 판독을 나란히 적었다.**

### 아직 안 닫힌 것 (이견이 가리킨 구멍)
- **계기 결함에 방향이 없다.** `instrument-misfire` 는 *거짓 FAIL* 만 담는다. 코드 버그로
  지표가 **좋게** 나온 경우(`sign-bug-generativity`)는 갈 곳이 없어 `gaming` 으로 샌다.
- **`범위 과대주장` 칸이 없다.** `zero-dep-scope-overgeneralize` 가 그 자리이고, 두 코더가
  서로 다른 칸에 밀어 넣었다. n=1 이라 새 칸을 만들지 않고 열어 둔다.
- ⚠️ 위 79.3% 는 **코더 간 일치율이지 정확도가 아니다.** 정답이 따로 없는 라벨링이라,
  새 축이 실제로 전달되는지는 **같은 시험을 새 라벨로 다시 걸어야** 답이 나온다(미실시).

## 항목 스키마 (1항목 = 1파일)

```markdown
# <id> — <이름>

> One-line English summary.          ← AI 스키머용 첫 줄

- **증상(시그니처)**: 무엇이 보이면 이 착시를 의심하나
- **기전**: 왜 이 착시가 생기나
- **실사례**: 실제 발생 기록 (출처: db/curated 라인 · 아크명 · 원장 seal)
- **탐지법**: 어느 프로브/규율 체크가 잡나
- **오적용 주의**: 이 라벨을 붙이면 안 되는 경우 (양방향 방어 — 과잉적발도 착시다)
```

## 규칙

1. **창작 금지** — 실사례 없는 항목은 도감에 못 들어온다. 출처는
   `db/curated/`의 해당 라인(이 레포 git 이력이 증인)과, 있으면 원장
   claim_id/seal.
2. **양방향** — 모든 항목에 "오적용 주의"가 있다. 착시 사냥 자체가
   과잉적발이라는 새 착시를 만들지 않도록.
3. **성장** — 아크 종료 / KILL / 자가적발이 나올 때마다 표본 1장 추가
   후보. 종결 세션 체크리스트에 포함. 봉인된 철회에서 초안을 자동 생성:
   `python catalog/draft_specimen.py --ledger <L>.jsonl --latest` — 실사례(원장
   claim_id·seal)만 전사하고 증상/기전/탐지법/오적용은 TODO로 남긴다(창작 금지
   규칙 유지). 사람이 TODO를 채우고 `.DRAFT.md → .md`로 승격해야 도감에 든다.

## Provenance

Seed data: `db/curated/{gaming_patterns.json, self_catches.jsonl,
false_negative_guards.jsonl, contamination.jsonl}` — sealed research history
(chrysalis journey, ZERO/場 closures, measure-mirror self-audits). The
ledger discipline that recorded these cases is specified in
[docs/SPEC.md](../docs/SPEC.md).
