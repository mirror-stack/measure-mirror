# baseline-only-direction-missed — baseline만 보고 방향 누락 자가적발

> Judging a result "OK" from baseline-exclusion alone while missing that it was below chance.

- **오류유형**: ⚠️**미정(이견)** — 코더A `fn-guard` / 코더B `gaming`. 두 독립 코더가 갈렸다. 어느 쪽으로도 확정하지 않는다.
- **증상(시그니처)**: baseline 배제만으로 결과를 'OK' 판정. 방향(부호) 검사를 빠뜨려 below-chance를 놓칠 뻔함.
- **기전**: baseline보다 나은지만 보고 chance 대비 방향을 안 보면, 대표본에서 chance 미만인 anti-signal을 성공으로 오판한다. 판정 로직 자체에 방향 게이트가 없으면 발생.
- **실사례**: 측정거울 MVP가 0.385를 'OK'로 판정 → "baseline 배제만 보고 방향 누락" 자가적발 → 방향 패치로 anti-signal 정정. 출처: db/curated/self_catches.jsonl — measurement_mirror_product_pivot
- **탐지법**: ④a direction 검사를 판정 파이프라인에 필수화 — chance/기준선 대비 부호 확인. gaming/anti_signal과 짝. 도구 자체를 도그푸딩해 판정 누락을 잡음.
- **오적용 주의**: 방향 게이트가 이진·chance 정의가 있는 태스크에만 유효하다. 회귀/순위 등에서는 chance 기준을 재정의해야 하며, 방향 누락 라벨을 기계적으로 적용하지 말 것.
