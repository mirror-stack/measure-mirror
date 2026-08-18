# grim-ratio-assumption — GRIM k≤n 비율가정 버그 자가적발

> The tool's own GRIM check falsely failed a valid mean because it assumed proportions (k≤n).

- **오류유형**: `instrument-misfire` — 독립 이중코딩 합치(2026-08-18)
- **증상(시그니처)**: GRIM 검사가 가능한 평균을 FAIL로 오판. 원인은 k≤n 상한이 비율(0~1)을 암묵 가정한 것.
- **기전**: GRIM은 mean·n으로 정수 합 k=round(mean·n)의 정합성을 본다. k≤n 상한은 비율 데이터에만 맞고, 리커트 평균(k=mean·n이 n 초과 가능)엔 틀리다. 도구의 숨은 가정이 정상 데이터를 거짓 FAIL시킴 — 검증기 자신의 거짓양성.
- **실사례**: 외부 GRIM 원논문(Brown&Heathers 2017) mean=5.18, n=28 사례를 측정거울이 FAIL로 오판 → k≤n을 k≥0으로 수정, GRIM 평균 5건+비율 회귀 통과. 출처: db/curated/self_catches.jsonl — external_grim_dogfood_20260612
- **탐지법**: 외부 정답 코퍼스(원논문 사례)로 도구를 도그푸딩 → GRIM/exact-binomial 검사기의 가정 결함 노출. self-catch를 도구 자체에 적용.
- **오적용 주의**: 진짜 비율 데이터(0~1)에서는 k≤n 상한이 옳다. 이 버그 교훈은 "가정을 데이터 유형에 맞춰라"이지 "GRIM 상한을 항상 풀어라"가 아니다. 비율 회귀 테스트로 양방향 유지.
