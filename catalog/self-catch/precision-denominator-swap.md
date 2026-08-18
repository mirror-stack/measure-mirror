# precision-denominator-swap — 조건부 지표의 분모 혼동

> A conditional metric (precision) was reported with the full-population n instead of the conditioning denominator; GRIM caught the impossible ratio.

- **오류유형**: `instrument-misfire` — 독립 이중코딩 합치(2026-08-18)
- **증상(시그니처)**: precision/recall/조건부 정확도류 지표를 검증에 넘길 때 n이 "전체 사례 수"로 들어감. GRIM이 "산술적으로 불가능한 값" FAIL을 냄(어떤 정수 k도 round(k/n)이 보고값과 불일치).
- **기전**: 조건부 지표의 분모는 조건을 만족한 부분집합(발화 건수·검출 건수 등)인데, 보고자는 습관적으로 실험 전체 n을 붙인다. 값 자체는 정직해도 (지표, n) 쌍이 거짓이 되어 CI·GRIM·검정력 판단이 전부 틀어진다.
- **실사례**: (음성 발화 정밀도 측정 실험) 너울 실Vault 게이트 v2(2026-07-03) — spoken_precision 0.9846(분모=발화 3255)·0.9967(분모=발화 3973)을 n=전체쿼리 6600으로 mm_verify에 보고 → GRIM ⑩ FAIL("no integer k satisfies round(k/6600,4)=0.9846") → 발화건수로 교정 재검증. 출처: db/curated/self_catches.jsonl — neoul_vault_real_v2_20260703, seals be3891607ddfe64b·2d8a006028148771·70147dc579556cfa·7c43e0ad5d85f89b
- **실사례 2 (prereg 단위 스케일 변종)**: hier_loop_external_fuel_v1(2026-07-13) — 등록 metric은 frac(late_succ_demo_frac, 0..1)인데 kill_threshold는 정수 카운트(late_succ_demo≤4.5, 0..16)로 봉인 → mm_verify ⑪ falsifiability가 0.6875를 4.5와 비교해 "kill 발동" 거짓 FAIL. 값 자체는 정직(11/16=0.6875·양 단위 동일 결론 CONFIRMED)했지만 (지표, 스케일) 쌍 불일치가 프로브를 오발동시킴. 양 단위 값 동시 제출로 재검증 통과·amendment로 봉인(prereg 809cafc189c67923·amendment a3b23ad3569489b3).
- **탐지법**: GRIM ⑩(정수 정합성). 예방은 지표 정의 시점에 "n = 이 지표의 분모"를 명문화하고, 조건부 지표는 (분자, 분모)를 함께 기록. prereg에선 metric과 kill_threshold의 단위(스케일)를 한 가지로 통일하고 봉인 전에 대조.
- **오적용 주의**: GRIM FAIL이 항상 분모 혼동은 아니다 — 반올림 자릿수 부족, 리커트 평균([[grim-ratio-assumption]]의 도구측 가정 버그)도 같은 증상을 낸다. 교정 후 원 rows에서 분자·분모를 재계산해 일치를 확인하고 나서 라벨을 붙일 것.
