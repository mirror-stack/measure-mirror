# prereg-clause-defect-family — prereg 문구 결함 계열 (3연속)

> A family of preregistration wording defects — unreachable clause, information-destroying tie-break, prediction mispositioned as anchor, ambiguous judgment unit — each detonating only at verdict time; three consecutive arcs paid with lost verdicts.

- **증상(시그니처)**: 봉인된 prereg의 특정 절이 판정 시점에야 문제로 드러남 — ①절이 논리적으로 도달 불능(기준이 이미 참/거짓 고정) ②동률·퇴화 케이스 규칙이 판정 정보를 폐기 ③"~하지 않을 것"이라는 **예측**이 앵커(무효 트리거) **조건**에 오배치 ④판정 단위(all/any/mean·창/에피)가 미고정이라 해석 변형끼리 결론 분열. 공통 결과: 실질과 무관하게 문자 격발로 RUN-INVALID/판정 소실.
- **기전**: prereg는 코드처럼 기계 실행되는데 리뷰는 산문처럼 한다. 결함 절은 특정 상태(동률·무발동·경계·0건)에서만 격발하므로 파일럿에서 안 드러나고, 결과를 본 뒤에는 완화가 금지(침묵수정 금지·도감 40호 boundary-grazing류 규율)라 결함 비용이 전액 **판정 소실**로 전가된다. 산문 리뷰는 "의도가 통하는가"를 보지 "모든 상태에서 절이 평가 가능한가"를 안 본다.
- **실사례(3연속·deep-lock 캠페인 07-18~19)**: (신경망 학습 잠금현상 캠페인) ①CP 아크 — 도달불능 지표 절(z2cov F→T 요구인데 기준이 이미 True) ②TRIM 아크 — 동률 tie-break 위치 규칙이 gain 정보 폐기(스펙 결함) ③TTL 아크 2건 — R-K3 "507 무발동" 절: 성공시드의 무발동 *예측*을 앵커 *조건*으로 오배치, 실질 무손상(d 0.8260 동일·발동 3회는 오염 후보의 정당 재기각)인데 문자 격발로 H-TTL 판정 미소비(**RUN-INVALID**); 귀속 g-서명 창-단위 판정 미고정(all/any/mean 3변형이 2:1 분열). 사후 처리: 정정 재판정에서 앵커=성과 유지+junk 오발동 0으로 재배치·g-서명은 사후 개봉이므로 **최엄격(all) 고정**(유리 변형 선택 금지)→B3 문구강등·"관찰-확정" 수위로만 발화. 출처: 원장 seara.jsonl — TTL prereg 7a9bbd6a31371d2b → RUN-INVALID **0ef8c233cbe5f241** → 정정 74b688c7d07f013c·DEEPLOCK_TTL_RESULTS.md §🪞·db/curated/self_catches.jsonl(prereg_clause_defects_20260719).
- **실사례(⑤앵커×withheld밴드 상호작용·2026-08-10)**: ㉘ vacuous 실런 봉인 v1(`17c36ad6`)이
  양성앵커를 "sloppy@8 **전부** unmatched"로 문자 고정 → 1런의 마진 −0.0524가 채점 제외용
  경계밴드(±0.005)에 들어 앵커 문자 격발, 행동은 정상(증서 FAIL·finding FAIL)인데 **INVALID** 소비
  (am `1481aa28`). 두 절(앵커·withheld)이 각자 옳아도 **상호작용 상태를 열거 안 하면** 같은 계열이다.
  정정=새 claim(`2a22a95a`)에서 앵커를 "의도 **반대** 클래스 0건"으로 재서술(withheld는 채점 밖이라
  무대를 반증하지 않음)+신선 시드블록, 판정기 SHA 비트동일 → PASS. 소급 완화 아님: v1은 INVALID로 남음.
- **탐지법**: 봉인 **전** 문구 기계 체크리스트(이 캠페인 이후 의무화) — ①전 절 도달가능성: 각 절이 True/False 양쪽으로 갈 수 있는 상태가 존재하는가 ②판정 단위 유일성: all/any/mean·집계 창 명시로 해석 변형 0개 ③예측/앵커 분리: 예측 실패가 무효 트리거에 묶여 있지 않은가 ④퇴화 케이스 표: 동률·무발동·0건·경계에서 각 절이 뭘 반환하는지 열거. mm_falsifiability_check·mm_preflight로 보조.
- **오적용 주의**: ①격발한 절이 설계 의도대로 작동한 진짜 kill이면 이 라벨 금지 — 결함 여부는 "절이 재는 것이 봉인 의도와 다른가"로 판정하지, 결과가 아팠는가로 판정하지 않는다. ②결함을 발견해도 소급 완화·재해석은 여전히 금지 — 정정은 새 봉인(amendment·재판정+문구강등)으로만 하며, 이번 사례도 RUN-INVALID를 문자대로 집행한 뒤 정정판을 별도 봉인했다. 이 표본의 교훈은 "봉인 전에 기계 체크하라"이지 "문자 격발을 무시해도 된다"가 아니다.
