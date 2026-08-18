# swept-knob-compound-pathway — 스윕 통과가 경로 귀속으로 오독될 뻔

> The intervention knob WAS swept and the outcome metric passed — but the knob moves several pathways at once, and preregistered mechanism-arithmetic showed the gain did not flow through the hypothesized pathway.

- **오류유형**: `attribution` — 독립 이중코딩 합치(2026-08-18)
- **증상(시그니처)**: 단일노브 개입 실험이 주지표를 통과("X를 올리니 K1 통과") → "요인=X 경로" 귀속이 공짜로 따라오려 함. 그러나 그 노브가 물리적으로 복수 경로를 동시에 움직이는 종류(예: 에피소드 수↑ = 채굴 유량↑ *그리고* 승격 기회↑ *그리고* 탐색 시도↑)라서, 통과 자체는 어느 경로가 담지했는지 말해주지 않음.
- **기전**: [[unswept-knob-attribution]]의 역방향 보완. 스윕을 *했어도* 노브가 compound면 귀속은 별도 증명이 필요하다. 통과/기각의 이분법이 "통과=가설(경로 포함) 전부 확증"으로 뭉개지는 인지 지름길. 특히 개입 성공의 실제 담지자가 "원래 성공하던 표본"일 때(이번: 이득 대부분=CTRL 기존 성공 8시드), 한계 표본 2~3개의 작은 flip이 경로 서사를 업어 가려 한다.
- **실사례**: (자기생성 언어모델 재귀 발명 실험) 너울 자생 H1′ 재귀발명 2단 개입(2026-07-13, prereg 98eed3e7f7794f20 → verdict seal 20420808cbb3bfac, 원장 river_engine_ignition.jsonl/seara.jsonl): N_TRAIN2 160→320 단일노브로 INT@320이 원 K1 통과(median 0.5609·sign 10/12 p=0.019·kill 7종 무트립). 그러나 사전등록된 K-diag D2 기제산술(채굴cnt×승격통과확률 원장)이 벗김 — flip 503=z2-cover 채굴 0→0(유량 경로 아님)·flip 509=cnt2로 명명 문턱(3) 미달·무flip 513=채굴 132→199 풍부+문턱 통과인데 실패·도즈커브 비단조(0.582→0.565→0.561). 판정은 유지하되 문구강등: "용량 증가 이득(요인 미귀속)" — "요인=채굴 표면 유량" 발화 차단. 1단 진단(유량 기아 지배·비봉인 가설)은 개입 수준에서 기각 방향.
- **탐지법**: 개입 prereg에 **기제산술 게이트를 사전 내장**(경로 가설이 함의하는 회계 항목을 원장으로: 이번엔 채굴 cnt·문턱 통과·승격 확률) + 도즈 단조성 + "이득의 담지자 분해"(flip 표본 vs 기존 성공 표본). 문구강등 게이트로 설계하면 주판정과 독립적으로 과대귀속만 자른다.
- **오적용 주의**: ①기제산술이 *일치*했으면 이 라벨 금지 — compound 노브라도 회계가 맞으면 귀속은 정당. ②주판정(K1 통과) 자체를 침해하지 말 것 — 교정 대상은 귀속 gloss뿐(이번에도 "INT@320서 원 K1 통과"는 유효한 봉인 결과). ③단일 경로 노브(다른 경로를 안 움직이는 개입)에는 과잉 요구하지 말 것.
