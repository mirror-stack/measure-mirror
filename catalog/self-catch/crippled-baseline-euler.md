# crippled-baseline-euler — Euler 형태일치 rigged baseline 자가적발

> A too-good positive was caught as a rigged crippled baseline before it was believed.

- **오류유형**: `gaming` — 독립 이중코딩 합치(2026-08-18)
- **증상(시그니처)**: 스모크 테스트에서 압도적 양성(0.295)이 나옴. "이렇게 압도적일 리 없다"는 자기의심이 먼저 발동.
- **기전**: 제안 모델과 baseline이 같은 형태(residual=Euler)로 일치하도록 짜였고 baseline이 약화(crippled GRU-ODE)돼 우위가 조작됨. 압도적 양성은 실력보다 비교 조작의 신호일 때가 많다.
- **실사례**: real_edge 후보5 스모크 0.295 압도양성 → "crippled GRU-ODE+場 residual=Euler 형태일치=rigged" 자가의심 → baseline 공정화 후 우위 소멸(거짓양성 적발). 출처: db/curated/self_catches.jsonl — field_real_edge_control_axis_closed
- **탐지법**: ⑦ self-catch("너무 좋음"이 첫 용의자) + ③ mm_baseline_fairness로 baseline 형태·예산 감사. gaming/crippled_baseline과 짝.
- **오적용 주의**: 모든 강한 양성을 조작으로 몰면 진짜 큰 효과를 죽인다. 자기의심은 baseline 공정화 *검증*으로 이어져야 하며, 공정화 후에도 우위가 남으면 그것은 진짜다.
