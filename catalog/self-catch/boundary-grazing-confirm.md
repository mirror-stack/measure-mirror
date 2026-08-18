# boundary-grazing-confirm — 경계 통과 확진

> A CONFIRM whose every pre-registered criterion passes with exactly zero margin — the
> signature of a noise-level effect grazing the thresholds, not a real one clearing them.

- **오류유형**: `gaming` — 독립 이중코딩 합치(2026-08-18)
- **증상(시그니처)**: 사전등록된 판정 기준 2개 이상이 전부 **여유 0으로 정확히 문턱값에서** 통과
  (차이=마진 그대로, 허용 역전=상한 그대로, 앵커=하한 그대로). 점추정만 보면 "전 기준 통과"로 읽힘.
- **기전**: 정수/거친 지표 + 소표본에서는 노이즈 수준 효과도 문턱을 스칠 확률이 상당하다.
  기준이 여러 개면 "전부 아슬아슬 통과"는 오히려 효과가 마진 크기 근처(=구분 불가)라는 증거인데,
  이진 판정(통과/미달)이 이 정보를 버려 확진처럼 보인다. small_n(gaming/)의 다기준 변종.
- **실사례**: SELFQ 1봉인(2026-07-13, prereg `b719a25f0a025a0c`→verdict `5fae99474e367152`):
  self−rand 차 1.0=마진 정확히·역전시드 1=상한 정확히·앵커 4.0=하한 정확히 — 3기준 전부 여유 0.
  후속 기제 절제런(신선시드 730~733, prereg `dc12de4be3b48243`)에서 self 3.0 vs rand 3.5로
  **방향 역전·재현 실패** → 철회 `f353316b79b7fa47`. 앵커 수준은 양 시드셋에서 4.0 재현
  (측정기계는 유효·효과만 허상). 자가적발: 외부 감사 아닌 자체 후속 절제런이 잡음.
- **실사례②**: SELFQ×외부연료 폐루프 표적클레임(2026-07-16, prereg `d41a820845ae3cd4`): 신선시드 판정서 median(active−random)=1.0=RATE_LIFT 정확히 그레이징(단 sign 6/12은 이미 명백 fail). 내가 봉인한 median 데드존이 과폭이라 기계판정 PENDING 반환 → holdout 772-777 재현서 active16.3<random18.7·median **−3.0**(방향 역전·재현 실패=+1.0은 노이즈) → 철회 `c08c4491c69eecd2`. 앵커 imposed−closed≈17 양세트 재현(기계 유효·효과만 허상). 교훈=데드존은 sign이 아닌 절대노이즈였는데 median밴드에 잘못 걸침(과폭 데드존 자체가 함정). 자가적발=봉인된 holdout이 잡음.
- **탐지법**: 판정기 출력에 기준별 **여유(margin) 명시** 의무화. 기준 ≥2개가 여유 0~ε로 통과하면
  CONFIRM에 자동 플래그(예: `boundary_grazing: true` — 실제로 이 사례의 verdict seal 본문에 있었으나
  발화 강등으로만 쓰고 재현 게이트로는 안 씀 = 절반 적발). 플래그 시 승격 전 신선시드 재현 의무.
- **오적용 주의**: 여유 0 통과가 자동 무효는 아니다 — 효과가 진짜여도 우연히 문턱에 앉을 수 있다.
  판정 기준은 "여유 0 통과 → 재현 요구"지 "여유 0 통과 → 기각"이 아니다. 또한 마진을 사후에
  올리는 건 골대이동(post_hoc 계열)이므로, 재현 요구만이 정직한 대응이다.
