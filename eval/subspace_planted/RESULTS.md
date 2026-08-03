# 심은 대조 세트 — ㉘ `subspace_claim_check`

> 양방향 채점용. **심은 음성을 통과시키면 거짓음성(FN)**, **심은 양성을 FAIL 내면 거짓양성(FP)**.
> 생성: `python eval/subspace_planted/gen_cases.py` · 검증: `--check`

## 🚨 가장 먼저 읽을 것 — 이 세트는 균질하지 않다

"심은 표본 12종 통과"라는 딱지는 **부당한 신뢰를 만든다.** 표본마다 실재성이 다르기 때문에
모든 케이스에 `layer`와 `provenance`를 **필수 필드로** 박아뒀다.

| layer | 뜻 | 개수 |
|---|---|---|
| 🟢 `real` | 라벨 이동·삭제·복제만 했다. **숫자를 하나도 지어내지 않았다** | 7 |
| 🟡 `half` | 실제 런에 없는 필드 하나를 합성/브로드캐스트하고 나머지는 실재 | 2 |
| 🔴 `synthetic` | 숫자가 날조다. 코퍼스에 그 현상의 실례가 **없기 때문** | 2 |
| 🔵 `B` | A층으로 **원리적으로 판정 불가** → B층(실행기) 몫 | 1 |

## 🚨 Finding 5 `vacuous` 는 양방향 모두 합성이다

**전 코퍼스에 실제 VACUOUS 라벨이 0건이다.** 실측 근거:

```
result_104_matched_subspace.json   vacuous_arms: []      surviving_arms: []
                                   manipulation 3홈×6팔 전수 valid: true
result_102_anchor_spectrum.json    any_vacuous_null: false
```

104_가 가진 것은 **규칙**이지 실례가 아니다. 따라서:

- FP 쪽(`clean_104`)의 올바른 라벨은 *"VACUOUS 실례가 들어 있다"* 가 **아니라**
  **"VACUOUS 0건 clean + 적용 가능한 증서 통과"** 다.
- FN 쪽(`vacuous_as_collapse`)은 증서 실패를 **손으로 써 넣어야** 만들어졌다.

⇒ **`vacuous`가 이 세트를 통과해도 그것은 실제 데이터에서의 검증이 아니다.** 공개 게이트 문서에
이 문장을 그대로 유지한다. 숨기면 우리가 우리 도감의 `crippled_baseline` 옆에 표본을 하나 더 얹게 된다.

⚠️ 증서의 하위 검사에는 **적용 불가(`null`)** 가 섞여 있다(예: `S5_amp_matched_random`의 `sv_bar`,
`S3a_spec_persample`의 `amp_bar`/`amp_ok`). **`null`을 "통과"로 읽으면 안 된다** — 어댑터는 `null`을
`True`로 강제하지 않고 그대로 옮긴다.

## ★ `relabeled_dof` — 이 케이스의 합격 기준은 "잡아라"가 아니다

105_에서 `LOCAL` ↔ `LOCAL_SHUF` 의 **role만 맞바꾼다.** 에너지는 여전히 맞고, dof 팔도 있고,
앵커도 멀쩡하다. **표만으로는 어느 쪽이 진짜 처치인지 미결정이다.**

그러므로 요구는 `__must_not__: {null-ladder: [OK]}` — **"확인"을 뱉지 않는 것**이 통과다.
여기서 OK를 내면 그게 진짜 거짓음성이다.

## 어댑터 3종 — 스키마가 전부 다르다

| 어댑터 | 실재 구조 | 이 세트에서의 역할 |
|---|---|---|
| `adapt_105` | `cells[팔][시드][에너지목표] = {gap, ratio, k_per_bin[4], energy_per_bin[4]}` · 4팔×10시드×4목표×3홈 = **480셀** | 주 clean 케이스. **`k_per_bin`은 벡터로 유지** — 평균 내면 105_ 자신이 `honest_limits`에 경고한 빈별 초과분을 지운다 |
| `adapt_103` | 주 격자에 `k_used`는 시드별이나 `energy_achieved`는 **평균 1개** · dof 팔 없음 | **정직한 부분 리포트.** 평균 에너지를 시드별 k에 붙이면 런이 만든 적 없는 셀 값을 날조하게 되므로, 셀을 팔×격자점 단위로 둔다. 정답 = `dof-uncontrolled` **WARN** |
| `adapt_104` | 격자 자체가 **없음** · `arms[팔].per_seed_T`(10) · `manipulation[팔]`=증서 | `energy-not-matched` = **N/A**. 이걸 FAIL로 읽으면 clean 리포트가 FAIL나고 **FP KILL이 오발**한다 |

## 앵커 `code_path` — 105_는 `mixed`다

105_ `honest_limits[0]`: *무사영 지점은 **동결된** `g91.rollout`을 직접 호출하고, 사영 지점은 같은
rollout의 **로컬 사본**을 쓴다.* 3값 어휘로는 정직하게 못 적어서 `mixed` + `mixed_detail` 필수로 뒀다.
`n_seeds`(NCORE=10)와 `guard_seeds`(NREPRO_guard_seeds=5)도 **분리 필드**다 — 합치면 앵커가 10시드
전부에서 검증된 것처럼 읽힌다.

## ⚠️ "실재"의 범위

기저 `B`와 섭동 표본 `dX`는 **어떤 파일로도 저장되지 않았다**(`*.pt|npy|npz` 0건).
재실행 비용 = 103_ 2647s · 104_ 508s · 105_ 928s.
∴ 여기서 `real`은 **기록된 표가 실재**라는 뜻이지, 우리가 그걸 재생성할 수 있다는 뜻이 아니다.

## 판정 상태

⬜ **미판정.** G2(양방향 판정)는 `cases.jsonl`을 `mm_preregister`로 **봉인한 뒤에만** 돌린다.
봉인 전에 결과를 보고 프로브를 고치면 그건 회귀 테스트지 반증이 아니다.
FP·FN 각 0이 아니면 **KILL**(명세 §반증조건).
