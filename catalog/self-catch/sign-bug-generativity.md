# sign-bug-generativity — 생성성 부호버그 자가적발

> A sign error inflating a generativity metric, caught by the mirror before shipping.

- **오류유형**: ⚠️**미정(이견)** — 코더A `instrument-misfire` / 코더B `gaming`. 두 독립 코더가 갈렸다. 어느 쪽으로도 확정하지 않는다.
- **증상(시그니처)**: 생성성 지표가 예상외로 좋게 나옴. 측정거울 자가검사에서 부호(sign) 버그 발견.
- **기전**: 지표 계산의 부호가 뒤집히면 나쁜 결과가 좋게, 또는 그 반대로 보인다. 코드 버그가 지표를 해킹하는 형태로, "너무 좋음"을 sanity 게이트로 걸러내지 않으면 통과한다.
- **실사례**: latent_oee 51_ 생성성에서 부호버그를 측정거울 자가적발 + 정정. 사전등록 metric-sanity 게이트로 해킹 차단. 출처: db/curated/self_catches.jsonl — chrysalis_latent_oee_pivot
- **탐지법**: ① preregistration에 metric-sanity 게이트(부호·범위·단조성)를 못박아 계산 버그가 지표를 밀어올리는 경로 차단. ⑦ self-catch로 "너무 좋음"을 코드 리뷰 트리거로.
- **오적용 주의**: 좋은 결과가 전부 버그는 아니다. sanity 게이트(부호·범위)를 통과하고 재현되면 진짜 신호다. 부호버그 의심은 게이트 실패 또는 방향 이상이 있을 때로 한정.
