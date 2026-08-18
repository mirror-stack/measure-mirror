# never-works-negative-overclaim — "never works" 음성 과대선언 자가적발

> A negative conclusion phrased as "never" when only our own cases/theory were tested.

- **오류유형**: `fn-guard` — 독립 이중코딩 합치(2026-08-18)
- **증상(시그니처)**: 음성 결론을 "shared db never works"처럼 절대화. 검증한 각도가 미등록이고 결론범위(never)가 검증범위를 초과.
- **기전**: 음성을 "언제나/절대"로 확장하면, 실제로 본 몇몇 사례·이론·코드보다 훨씬 넓게 주장하게 된다. 반증 시도한 각도를 명시하지 않으면 범위 초과를 스스로 못 본다.
- **실사례**: 측정거울 자기측정 ⑬ — mm_negative_audit이 FAIL(각도 미등록 + 결론범위 never가 검증범위 우리 사례·이론·코드 초과) → README를 "우리 맥락 인센티브 불일치"로 약화. 출처: db/curated/self_catches.jsonl — measure_mirror_self_audit_20260612
- **탐지법**: ⑥ mm_negative_audit — 음성결론의 검사 각도 등록·결론범위≤검증범위 강제. gaming/overclaim(음성판)과 짝. 범위 한정 문구로 재작성.
- **오적용 주의**: 여러 독립 각도가 수렴한 음성은 정당하게 강한 결론이 될 수 있다(perseverance vs 성급종결). "never" 라벨은 검증 각도가 좁은데 절대화할 때만 — 맥락 한정 결론은 과소가 아니다.
