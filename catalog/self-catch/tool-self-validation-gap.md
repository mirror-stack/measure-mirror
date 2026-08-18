# tool-self-validation-gap — 무결성 도구가 자기 입력을 검증하지 않음

> The integrity tool sealed a malformed input silently, then crashed at evaluation — the auditor un-audited itself.

- **오류유형**: `instrument-misfire` — 독립 이중코딩 합치(2026-08-18)
- **증상(시그니처)**: 검증 도구가 잘못된 입력을 조용히 받아들이고(봉인까지 성공), 나중 평가 단계에서 예외로 터진다. 도구 자신이 "입력 검증"이라는 자기 규율을 안 지킴.
- **기전**: 무결성 도구는 남의 주장을 검사하지만, 자기 API 입력에는 같은 엄격함을 적용하지 않기 쉽다. 특히 "선택적 구조화 필드"를 검증 없이 저장하면, 형식 오류가 봉인 시점(고칠 수 있을 때)이 아니라 평가 시점(이미 봉인된 뒤)에 드러난다. append-only·first-write-wins면 사후 교정도 막힌다.
- **실사례**: measure-mirror 자신. 비표준 `kill_threshold`(예 `{"H1_reject_if": ...}`, `threshold` 키 없음)를 `preregister()`가 검증 없이 봉인 → `audit()`/`falsifiability_check()`에서 `KeyError: 'threshold'`. first-write-wins라 같은 claim_id 재등록으로 교정 불가(새 id로 re-key만이 우회). 도그푸딩 중 자가적발(issue #18, fix PR #19: seal 시점 검증 + 기존 원장 graceful WARN).
- **실사례(호출자 측 변종)**: semantic-fuel 아크(2026-07-20, 원장 semantic_fuel.jsonl). 호출자(나) 쪽 형식 오류로 `kill_condition`이 별도 필드가 아니라 `metric` 본문 안에 임베드된 봉인 3건(`350f36d7ee0ab5ab`·`d955eea72424a112`·`0cf5446e06213016`). 내용은 원장에 전문 보존되고 **런 전에 봉인된 것도 사실**이나, `mm_audit`가 그 필드를 못 읽어 ⑪ falsifiability는 "kill-condition 없음" WARN, ①은 metric-swap FAIL을 냈다 — **둘 다 형식 결함의 산물이지 실체 발견이 아니다**. 위험은 두 방향: 이 FAIL을 실체로 읽으면 멀쩡한 판정을 버리고, 무시하는 습관이 들면 진짜 FAIL도 지나친다. 처리: 재봉인으로 덮지 않고 am 원장(`de3ae42d336c3e9c`)에 결함 자체를 기재. 출처: db/curated/self_catches.jsonl — mm_call_format_defect_20260720

- **탐지법**: 도구의 입력 경계에 **fail-fast 검증**(잘못된 형식은 저장/봉인 전에 거부). ⑦ self-catch: "내 도구는 자기 입력에 자기 기준을 적용하나?" append-only 저장 전 스키마 체크는 필수(사후 불가역이므로).
- **오적용 주의**: 모든 필드를 과잉 검증하면 자유형식(free-text)의 유연성을 죽인다. 검증은 *자동 평가에 쓰이는* 구조화 필드에만 — 사람이 읽는 서술 필드까지 강제 스키마를 걸지 말 것.
