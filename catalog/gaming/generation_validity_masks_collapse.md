# generation_validity_masks_collapse — 생성 유효율이 다양성 붕괴를 가림

> A high self-generation "validity rate" that hides mode collapse — the generator emits valid-but-nearly-identical items.

- **증상(시그니처)**: 자기출제/self-play에서 "출제 유효율"이 0.99+로 건강해 보이는데, 학습이 안 늘거나 죽음대조(seed만 반복)와 동일한 성능. 유효율만 대시보드에 있고 **고유 산출 수/다양성**은 안 봄.
- **기전**: 생성기가 형식적으로 유효한(파서·실행기 통과) 소수 패턴으로 mode collapse하면, 유효율은 1.0에 수렴하지만 실질 정보는 시드 분포로 붕괴한다. "유효"는 문법 게이트일 뿐 신규성 게이트가 아니다 — 위조 불가능한 심판(실행기)조차 라벨 위조는 막지만 다양성 붕괴는 못 막는다.
- **실사례**: self-examiner(자기 문제 출제기, 07-22~23) CLOSED 팔이 propose_validity 0.997인데 3510출제 중 **고유 46~65개** = mode collapse. 비ERR정확도 0.028~0.064로 죽음대조 SEEDONLY(0.044~0.072)와 동일 → H1 🔴KILL(delta −0.0013). 유효율만 봤으면 "건강한 자기출제"로 오독할 뻔. 출처: 원장 self_examiner.jsonl retract seal=3a92f71bc8c5ad34 · runs/main_0722_0803.
- **탐지법**: 유효율 옆에 **고유율(unique/emitted)·엔트로피·중복률**을 항상 병기. 죽음대조(생성 없이 시드만 반복)를 넣어 "생성이 시드를 넘어서는가"를 격차로 확인. self-catch ⑦: 유효율 높은데 성능이 죽음대조와 같으면 다양성부터 의심. 선행: self-play 붕괴(arXiv 2603.02218) — proposer가 사소/반복 문제로 표류.
- **오적용 주의**: 낮은 고유율이 항상 붕괴는 아니다 — 과제 공간이 작으면 정당한 재방문이다. **죽음대조 대비 초과분이 있으면**(생성이 실제로 신선 진리를 공급하면) 이 라벨 금지. 유효율이 아니라 "죽음대조 대비 격차"가 기준.
