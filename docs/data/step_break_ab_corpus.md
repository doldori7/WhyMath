# 데이터 카드 — step_break A/B 라벨 코퍼스 (precision eval)

> **용도**: `classify_step_break`(slice 65)이 산출하는 **A 후보**(순차유도 변환오류)의
> *정밀도(precision)*를 사람 A/B 라벨 대비 측정한다. 2026-06-06 정책 **해금 게이트 #2**
> ("shadow 데이터로 A에 대한 precision ≥ 사전 임계 입증")의 실측 입력.
>
> **비노출·오프라인**: 런타임/HTTP/학생 노출과 무관한 내부 평가용. **student-facing 아님**.

- **현재 파일**: `data/corpus/step_break_ab_seed_v1.jsonl` (v1 시드)
- **하니스**: `python -m whymath_backend.l4.step_shadow_eval <labels.jsonl> [--min-precision T]`
- **harvest**(slice 67): `python -m whymath_backend.l4.step_shadow_harvest <obs.jsonl>` → 라벨 미지정 draft
- **관련**: slice 62(`detect_step_breaks`) · slice 65(`classify_step_break`) · slice 66(코퍼스+하니스) · slice 67(harvest)

---

## 1. 요약

| 항목 | 값 |
|---|---|
| 포맷 | JSONL (한 줄당 `StepBreakLabel`) · 빈 줄·`#` 주석 무시 |
| v1 시드 행 수 | 16 (합성) |
| 라벨 | `A`=순차유도 변환오류 · `B`=변수재사용(독립 소문제) |
| v1 분포(시드) | TP 5 · FP 2 · FN 3 · TN 6 → A-precision ≈ 0.714 · recall = 0.625 |
| 출처 | **합성**(수기 구성 + `tests/backend/l3/test_pregenerate.py` 픽스처 유래) |
| 민감정보 | 없음 (학생 데이터·교과서/저작권 본문·PII **0**) |

> v1 시드의 정밀도 수치는 **하니스 검증용 예시**이지 실측 결론이 아니다. 실제 해금 판정은
> *실 shadow 로그를 사람이 라벨링한* 코퍼스를 같은 하니스에 넣어 산출한다(이 슬라이스는 *기구*를 만든다).

---

## 2. 레코드 스키마 (`StepBreakLabel`)

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `solset_before` | str | ✅ | 이전 단계 해집합 문자열, 예 `"{3}"` (`_format_solset` 형식) |
| `solset_after` | str | ✅ | 다음 단계 해집합 문자열, 예 `"{4}"` |
| `expected_answer` | str \| null | — | 문항 기대정답(자유텍스트). 없으면 `null` |
| `human_label` | `"A"` \| `"B"` | ✅ | 사람 판정: A=변환오류 / B=변수재사용 |
| `var` | str | — | 변수명(기본 `"x"`·StepBreak 재구성용·평가 무관) |
| `marker` | str | — | 순차유도 마커(추적용·평가 무관) |
| `solution_text` | str | — | 원 풀이(가독·출처) |
| `source` | str | — | 출처(`manual`·`shadow-log` 등) |
| `note` | str | — | 라벨 근거 메모 |

> 평가에 **실제로 쓰이는** 필드는 `solset_before`·`solset_after`·`expected_answer`·`human_label`뿐이다
> (나머지는 추적·가독용). 이 스키마는 shadow 로그(slice 65)가 남기는 필드와 같은 모양이라, 실제 로그를
> 사람이 A/B로 라벨링하면 그대로 한 레코드가 된다.

> **harvest 경로(slice 67)**: `step_shadow_harvest`가 구조화 관측(`StepBreakObservation`) JSONL을 읽어
> *라벨 미지정* draft 행으로 변환한다 — `human_label: null`(사람이 `"A"`/`"B"`로 채움) · `source:
> "shadow-log"` · **`solution_text: ""`**(실 harvest는 원문을 비움 — 아래 §4 프라이버시). candidate·
> observed_at은 `note`에 보존(eval이 candidate를 재계산하므로 draft 필드엔 없음).

---

## 3. 라벨 정의 (A vs B)

- **A — 순차유도 변환오류**: *한 문항의 연속 유도*에서 한 단계를 잘못 옮겨 해집합이 바뀐 경우
  (예: `2x = 6`(x=3)을 `2x = 8`로 잘못 적음). 메타인지 코칭 가치가 있는 *진짜 오류*.
- **B — 변수재사용(독립 소문제)**: 같은 변수명을 *서로 다른 소문제*에 재사용해 해집합이 바뀐 경우
  (예: `2x = 6`(x=3) … `3x = 12`(x=4)). 오류가 아니다.

> **분리 불가성(정책 2026-06-06)**: A와 B는 *구문상* 구별되지 않는다(마커+해집합 변화 표면이 동일).
> `classify_step_break`은 *기대정답 앵커*로 A의 양성 증거(정답서 이탈=`diverged_from_answer`)를 추정할
> 뿐이며, 본 코퍼스는 그 추정의 precision을 *측정*해 student-facing 해금 가부를 증거로 판정한다.

---

## 4. 라이선스·안전 (CLAUDE.md 우선순위 #2 준수)

- **출처/저작권**: 전부 **합성**(수기 구성한 일반 1차방정식 스니펫). 검정교과서·평가원·EBS 등
  *저작물 본문·문항 0*. 공개/사유 저작물 복제 없음 → 저장소 라이선스 하에 자유 사용.
- **개인정보**: 학생 풀이·식별정보 **없음**(미성년자 데이터 0). PII 0.
- **노출 경계**: **내부 eval 전용·비-student-facing**. 런타임/HTTP/응답 경로에 싣지 않는다.
- **실 데이터 확장 시**: shadow 로그→코퍼스 변환은 학생 풀이가 *민감정보*이므로 익명화·동의·암호화
  저장 절차(CLAUDE.md 데이터 원칙)를 따르고, `source`에 출처를 명시한다.
- **프라이버시 비대칭(slice 67)**: 합성 시드는 `solution_text`(원 풀이)를 채우지만 *실 harvest*의 draft는
  `solution_text=""`다 — 구조화 관측(`StepBreakObservation`)이 학생 풀이 원문을 **담지 않기** 때문(미성년자
  프라이버시·slice 64~65 로그의 의도적 누락 계승). 라벨러는 추상 `solset_*`·marker·verdict/candidate 단서로
  A/B를 판정한다. draft도 코퍼스와 같은 **내부 eval 전용·비-student-facing** 경계를 상속한다.

---

## 5. 버전

| 버전 | 파일 | 비고 |
|---|---|---|
| v1 | `step_break_ab_seed_v1.jsonl` | 합성 시드 16행 — 하니스 검증·4 verdict 분기·A/B 균형·한계(FP) 케이스 포함 |

향후: 실 shadow 라벨 코퍼스(v2+)·다중값/유리해 케이스·다양한 마커·검정자 간 일치도(IAA) 기록.

---

## 6. 실행

```bash
cd src/backend && . .venv/bin/activate
# 리포트만(게이트 없음)
python -m whymath_backend.l4.step_shadow_eval ../../data/corpus/step_break_ab_seed_v1.jsonl
# 게이트: A precision < 0.99면 종료코드 1 (미래 CI 해금 체크)
python -m whymath_backend.l4.step_shadow_eval ../../data/corpus/step_break_ab_seed_v1.jsonl --min-precision 0.99
```
