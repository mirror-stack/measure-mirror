# alias-folding-indicts-a-lookalike-column — 접힌 별칭이 닮은꼴 열을 고발한다

> A registry alias, folded by normalization (bare substring, hyphen-folding, over-short
> aliases), latches onto a lookalike column of a *different quantity* — and downstream
> integrity checks then confidently indict honest numbers.

- **증상(시그니처)**: 매칭 파이프라인의 유일한(또는 소수의) 히트가 하필 이름만 닮은 딴
  수량이다(사람 평가 점수 열 ↔ 코드 벤치마크). 그 히트에 정합성 검사(GRIM 등)가 **전건
  FAIL**을 낸다. "전부 부정직해 보인다"는 "전부 딴 대상이다"의 신호이기도 하다.
- **기전**: 별칭·정규화는 재현율을 위해 이름공간을 접는다 — 과단축 별칭(`"he"`), 단어경계
  없는 부분문자열 매칭, 하이픈→공백 접기. 접힌 공간에서는 서로 다른 수량이 같은 키로
  충돌하고, 매처는 가장 닮은 셀에 확신을 갖고 붙는다. 하류 검사는 *매칭이 옳았다는 전제*
  위에서 산수만 검사하므로, 잘못된 귀속을 "부정직한 숫자"로 번역한다 — 확신에 찬 잘못된
  고발. 계기는 퇴화값 없이 말끔하게 돌았다는 점에서 instrument-bug-as-verdict 와 다르다:
  고장난 건 계기가 아니라 **가리킨 대상**이다.
- **실사례**: `bench_registry.py` HumanEval 별칭, 같은 아크에서 이틀 간격 2연속.
  ① 2026-08-13 설계 리뷰 **B1**: 별칭 `"he"` + 단어경계 없는 부분문자열 → 현실적 표 헤더
  20개 중 **13개**가 HumanEval(n=164)로 오매칭(Other·Overhead·Chess·Weather·Shell·Cache·
  Schema·The Model…). 봉인 前 설계게이트가 차단. 출처:
  `lanes/mirror/reviews/20260813_arxiv-study-design-review.md` §B1.
  ② 2026-08-14 재파일럿: `_norm` 이 하이픈을 공백으로 접어 별칭 `human-eval`→`human eval`,
  논문 2411.17261 의 **사람 평가 열**("Human Eval ↑"·심사자 점수 1.9~4.0)을 HumanEval
  n=164 의 비율로 읽어 **GRIM 7/7 거짓 FAIL** — 그 팔(ARM_FLAG)의 유일한 "매칭"이 전부
  위양성. 수리+회귀 테스트 19/19. 출처: `82_BHYI4/harvest/REVISION_STUDY_DESIGN.md` §9.2 ·
  am seal `c52798269b082493c514c0e1f28f6c264cfb58a81d641e09feedb100090c4fff`.
- **탐지법**: ① 별칭은 고유명 전문만 — 과단축·일반어 별칭 금지("he"는 영어 대명사다).
  ② 매칭은 단어경계/정확일치로, 정규화는 최소로 — 구분자 접기(하이픈→공백)를 넣을 때마다
  그 접기로 충돌하게 되는 이름 후보를 열거해 볼 것. ③ 정합성 검사가 **전건** FAIL이면
  산수 이전에 귀속을 의심(⑦ self-catch — "전부 부정직"보다 "전부 딴 대상"이 훨씬 흔하다).
  ④ 수리에는 반드시 그 오매칭 사례 자체를 회귀 테스트로 박는다.
- **오적용 주의**: 정규화 자체가 악이 아니다 — 표기 변형(HumanEval/Human-Eval/humaneval)을
  같은 키로 모으는 것은 정규화의 정당한 일이고, 이 라벨은 접기가 **다른 수량**과 충돌할
  때만 붙는다. 또 정합성 검사의 전건 FAIL 이 언제나 오귀속 신호인 것도 아니다 — 귀속을
  눈으로 확인한 뒤에도 FAIL 이면 그때는 진짜 고발감이다.
