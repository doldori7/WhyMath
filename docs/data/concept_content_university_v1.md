# 와이매스 대학 소단원 콘텐츠 v1 — 데이터 카드

> **요약**: 대학 수학 **소단원 409건**의 교수학 콘텐츠(은유·오개념·정식정의[내부]·허용표현·설명)
> 와 **암기카드 409건**을 자체작성 코퍼스로 캡처한 슬라이스(원자 백본 U4). 출처는 사용자 업로드
> 통합마스터 xlsx의 `개념`(대학)+`암기카드` 시트. **자체작성**(원자노드DB 종합·AI 추정·검수필요)·
> redaction 불요. 콘텐츠 4종의 **DB 투영(misconception_catalog·problem 등)은 Phase 3** — 이
> 코퍼스는 *휘발 xlsx 자산을 커밋 코퍼스로 보존*하는 캡처다.
>
> **현황(2026-06-22)**: 코퍼스 **생성·커밋 완료**(`data/corpus/concept_content_university_v1/`).

---

## 1. 출처·프로비넌스

| 항목 | 값 |
|---|---|
| 형태 | 업로드 통합마스터 xlsx의 `개념`(학교급=='대학교') + `암기카드(목록화)`(소단원 코드) 조인 |
| 원본 sha256 | `74000919f32c9d8d4b5c6026c36781a4856976112e23c798b99348f222c0a8b1` |
| 출처 | **와이매스 자체작성** — 원자노드DB 종합·AI 추정·검수필요 |
| 산출물 | `data/corpus/concept_content_university_v1/{content.json, _provenance.json}` (**커밋됨**, 2026-06-22) |

> 원본 xlsx는 **커밋하지 않는다**(K-12 NCIC 본문 포함). 대학 콘텐츠는 자체작성이라 코퍼스로 보존.

---

## 2. 스키마

`content[]` 각 항목(`UniversityConceptContent`): `code`(소단원 `CALC1-U1-S1`)·`name`·`subject`·`unit`·
`metaphor`(은유)·`misconception`(오개념)·`formal_definition_internal`(정식정의·**학생 비노출**)·
`accepted_expressions`(허용표현)·`explanation`(설명)·`flashcards[]`(앞/뒤/mnemonic/노출조건/등급/난이도).

---

## 3. 통계 (실 코퍼스)

| 항목 | 값 |
|---|---|
| 콘텐츠(소단원) | 409 (코드 유일·소단원↔콘텐츠 1:1) |
| 암기카드 | 409 (소단원당 1) |
| 과목 | 32 |
| 콘텐츠 4종 채움 | 은유·오개념·정식정의·허용표현 각 409/409 |

---

## 4. 라이선스·취급 (CLAUDE.md 우선순위 #2)

- **자체작성**: redaction 불요(NCIC 본문 아님). `licensing_safety.md` 대학 콘텐츠 v1 행.
- **`formal_definition_internal`(정식정의)은 학생 비노출** — 내부·교사/검수용. 노출 계층이 게이팅.
- **검수필요**: 전 콘텐츠 AI 추정 초안 → 수학 전문가 검수 후 학생 노출(특히 오개념·정식정의).

---

## 5. 소비·후속 (Phase 3)

- 콘텐츠 4종 DB 투영: 오개념→`misconception_catalog`·정식정의/은유/허용표현→콘텐츠 슬롯·암기카드→
  카드 테이블. K-12 콘텐츠(구 437개념)와 함께 Phase 3에서 *개념/소개념 레벨* 투영(437→원자 크로스워크).
- 소단원 코드(`CALC1-U1-S1`)로 원자노드DB·`standards_university_v1`와 조인.
