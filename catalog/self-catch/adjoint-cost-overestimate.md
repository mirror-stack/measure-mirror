# adjoint-cost-overestimate — Adjoint 비용 과대평가 자가적발

> A false negative caused by overestimating a method's own cost, self-corrected to a pass.

- **오류유형**: `fn-guard` — 독립 이중코딩 합치(2026-08-18)
- **증상(시그니처)**: 픽셀 F1이 거짓음성으로 나옴. 원인이 데이터가 아니라 자기 구현이 Adjoint 비용을 과대평가한 결함이었음.
- **기전**: 방법 자체의 비용/복잡도를 잘못 크게 잡으면 실현 가능한 것을 불가능(음성)으로 오판한다. 음성이 대상의 한계가 아니라 구현 결함에서 온 것 — 거짓음성의 전형.
- **실사례**: FM×CDE 픽셀 F1 거짓음성 → "Adjoint 비용을 과대평가한 자기 결함" 적발 → O(1) Adjoint불요로 자가정정, F1 PASS. 출처: db/curated/self_catches.jsonl — fm_cde_pixel_feasibility
- **탐지법**: ⑤ 양방향(거짓음성도 검사) — 음성이 나오면 "진짜 대상/최적 구현을 썼나"를 먼저 확인. fn-guard/implementation-flaw-as-negative와 짝. 구현 대안(O(1) Adjoint)으로 재시험.
- **오적용 주의**: 모든 음성을 "내 구현 탓"으로 돌리면 진짜 벽을 못 본다. 구현 결함 의심은 비용 산정에 실제 오류가 있고 대안 구현이 결과를 뒤집을 때만. 여러 정당 구현에서도 음성이면 그것은 진짜 음성.
