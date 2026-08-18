# integrity_false_fail_format_drift — 무결성 검증기의 형식 불일치 오경보

> A ledger integrity checker crying "tampered!" when the real cause is a seal-format drift, not content alteration.

- **오류유형**: `instrument-misfire` — 독립 이중코딩 합치(2026-08-18)
- **증상(시그니처)**: 체인 무결성 프로브가 특정 엔트리에서 "seal mismatch / tampered"를 FAIL로 낸다. 그런데 그 엔트리는 다른 세션·다른 봉인 도구로 append됐고, prev_seal 링킹과 내용은 멀쩡하다.
- **기전**: 검증기는 표준 규칙(예: 16자리 truncated seal)으로 seal을 재계산해 대조한다. 엔트리가 비표준 도구(예: 64자리 full-sha + 추가 필드)로 봉인됐으면 재계산이 안 맞아 "tampered"로 뜬다. 이는 **내용 조작이 아니라 봉인 형식 drift** — 검증기의 거짓양성이다. "tamper 경보가 떴다"는 사실이 "조작됐다"를 뜻하지 않는다.
- **실사례**: self-examiner 원장(self_examiner.jsonl) mm_verify가 엔트리 2·3(amend2·amend3)에서 seal mismatch FAIL. 규명 결과 = **형식 drift**: (1) prev_seal 링킹 4엔트리 전부 무결(genesis→…→head, append-only 순서 보존), (2) kill_condition이 4엔트리 동일(threshold 0.02·below — 골포스트 이동 없음), (3) 엔트리 2·3만 64자리 seal + `pre_seal_checks` 필드 = 07-22 세션의 비표준 봉인 도구. 내용은 명세.md Amendment 2·3과 일치. → false-fail 배제 후 KILL 판정 유효. 출처: 원장 self_examiner.jsonl · retract seal=3a92f71bc8c5ad34.
- **탐지법**: FAIL 시 세 가지 독립 확인 — ①prev_seal 링킹(순서/연결), ②핵심 조건 필드(kill_condition 등)의 엔트리 간 동일성, ③내용 vs 외부 사본(명세 SHA) 대조. 셋 다 무결이면 형식 drift로 분류하고 봉인 도구 통일. self-catch: "tamper" 경보를 판정 근거로 쓰기 전에 조작 가설을 능동 반증.
- **오적용 주의**: **진짜 조작을 형식 탓으로 덮지 말 것.** prev_seal 링킹이 깨졌거나, 조건 필드가 조용히 바뀌었거나, 내용이 외부 사본과 다르면 그건 형식 drift가 아니라 실제 tamper다. 세 확인 중 하나라도 실패하면 이 라벨 금지 — 무결성 FAIL을 정당한 경보로 취급.
