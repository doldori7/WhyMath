# S1 탈출 게이트 판정 (S1-14) — 스캐폴드 + 게이트 ③ 증명

> **상태**: ✅ **판정 완료 — 3종 전부 PASS·S1 탈출 선언** (2026-07-16, Kiki 조건부 사인오프 "정상 작업 보장될 때 통과"의 실증 충족) | **owner**: kiki(판정)·claude(서기·게이트 ③ 증명)
> **정본 게이트 정의**: `docs/strategy/status_roadmap_2026-07.md` S1 섹션(:104) — "① 실기기 1루프 시연 녹화 ② 루프당 LLM 비용 실측·로컬 80% ③ 학생 응답 = PRM/도구 검증 통과 후 코드 경로 증명"
> **de-risk 취지**(S1-12 런북 #516 선례): claude가 판정 가능한 2개 게이트(①③)를 확정하고 게이트 ②의 Kiki 실행 패키지를 완비해, Kiki 잔여를 **"② 재측정 → 3종 사인오프" 한 세션**으로 축소한다.

---

## 판정 요약

| 게이트 | 정의 | 판정 | 근거 |
|---|---|---|---|
| ① 실기기 시연 | 패드에서 1루프 15분 내 완주 녹화 | ✅ **PASS** | `G-kiki-device-demo` **cleared**·녹화 증거 실재(gates.yaml evidence 링크) |
| ② 루프당 비용·로컬 80% | 루프당 LLM 비용 실측·로컬 ≥80% | ✅ **PASS** | 2026-07-16 probe_g4(30/30·기록 실패 0): 라우터 결정 **로컬 90.0%**·Langfuse 재확인 **92.0%**(25이벤트). 비용 실측: LOCAL 23건 0원·CLOUD_MID 2건 합 10.01원(콜당 5.00원)·지연 p50 LOCAL 1015ms/CLOUD 4571ms. 측정 인프라 정상 작동 실증(SDK 버전 적응 수정 `6a882b0` 후) — Kiki 통과 조건 충족 |
| ③ PRM/도구 검증 코드 경로 | 학생 응답 = 검증 통과 후가 코드 경로로 증명 | ✅ **PASS(정직 프레이밍)** | 아래 §게이트 ③ 증명 + 기계 봉인 3종(`test_coach_gate3_serving_invariant.py`) |

**최종 판정(Kiki 기입란)**: `[x]` 게이트 ② 재측정 로컬 ≥80% 확인(probe_g4 90.0%·Langfuse 92.0%) → `[x]` 3종 전부 PASS 사인오프(2026-07-16 Kiki 조건 "키를 정확하게 올리고, 앞으로 정상적으로 작업하는 것이 보장될 때 통과" — 키 실제 등록·기록 실패 0건·분포 실측으로 충족) → **S1 탈출 선언(2026-07-16)** → ROADMAP·MEMORY 갱신·`backlog.py done S1-14` 완료.

**후속(선택·비차단)**: cost_report 튜닝 제안 `_EST_ASSUMED_INPUT/OUTPUT_TOKENS ← 62/124`(현행 74/358) — 대표 믹스 실측 기반 라우터 재보정은 별도 슬라이스로.

---

## 게이트 ③ 증명 — "학생 응답은 전부 PRM/도구 검증 통과 후" (정직 프레이밍)

**오해 방지**: 정본 문구를 "모든 학생 응답이 PRM을 통과한다"로 읽으면 **오버클레임**이다. 서빙 경로의 실체는 다르며, 실체가 더 강한 보장을 준다.

### 서빙 경로 실측 map (`api/coach.py`)

학생-대면 콘텐츠는 3 POST 엔드포인트(`/v1/coach`·`/v1/coach/sessions`·`.../turns`)가 방출한다. 방출물은 정확히 두 종류뿐:

1. **Polya 발화(`decision.prompt`) = 결정론 정적 템플릿**. `_build_response_payload`가 부르는 유일한 코치 콜은 `PolyaCoach.decide`(`l4/polya/engine.py:63`·"LLM 없이 *결정*만")이고, `decision.prompt = STAGE_PROMPTS[stage].prompt`(`engine.py:102`) — `l4/polya/prompts.py`의 **하드코딩 한국어 템플릿 4종**을 축자 방출한다(학생 텍스트 보간 0). LLM 백엔드 경로 `PolyaCoach.coach()`(engine.py:108·`LLMSeam.generate`)는 **서빙에서 절대 호출 안 됨**(dead relative to API). 저장 AI 턴 = `decision.prompt` 그대로(coach.py:1265·1446). → **LLM 출력이 없으므로 PRM은 N/A**, 불변식이 vacuous하게 성립(빈 텍스트 검증이 아니라 검증할 LLM 산출이 없음).

2. **도구-검증 게이팅 신호(`solution_coaching`)**. `recommend_coaching_for_solution`(`l4/solution_coaching.py:145`)이 학생 *본인 제출 풀이*에 L3 결정론 검증기(`validate_response`·`verify_solution`·`verify_step`=SymPy 3-state)를 돌리고, **노출 게이트**(`coach.py:496-498`)가 `arithmetic_error`(검증기 발화) 또는 θ-불일치 focus일 때만 학생에게 노출한다. clean/미파싱 → `None`. 정답(`expected_answer`)은 응답에 결코 실리지 않음(coach.py:405·423). → 노출되는 검증 신호는 **전부 도구 verdict로 게이팅**.

### 캐비엇 (정직 고지 — 서빙 경로 LLM 실체)

- **오개념 judge(LLMJudge)**: 서빙 경로 유일 LLM 콜(`_gate`·coach.py:648). 단 **기본 OFF**(`misconception_judge_enabled=False`)·학생-대면 산문 0(고정 카탈로그 후보를 *제거*만)·노출은 결정론 `apply_match_quality_gate`(top-1 신뢰도 ≥0.65) 통과 후. → LLM *산문*이 학생에 방출되지 않음(PRM이 아니라 결정론 신뢰도 게이트로 품질 관리).
- **WH-1 하네스**(실 LLM 튜터·도구 루프): shadow-only·`None` 반환·기본 OFF·무영속(`harness/wh1_shadow.py`) — 구조적으로 학생에 도달 불가.

### 기계 봉인 (구조상 성립 → CI 동결)

`tests/backend/api/test_coach_gate3_serving_invariant.py`(신설·3종 green):
1. `decide` 발화가 단계×입력×마스터리 전수 스윕에서 **항상 정적 템플릿 4종** — 학생 텍스트 보간·LLM 생성 유입 시 red.
2. 실제 `POST /v1/coach` 응답의 `decision.prompt`가 정적 템플릿 집합 — 서빙 경로 end-to-end.
3. 서빙 경로 LLM 플래그(judge·shadow) 기본 OFF 동결 — 캐비엇 전제 뒤집힘 감지.

**게이트 ③ 판정 = PASS**: "모든 학생-대면 응답은 (i) 결정론 템플릿(LLM 0→PRM N/A) 또는 (ii) 도구-검증 게이팅 신호"가 코드 경로로 증명되고 CI 동결됨 — 정본 문구보다 정확·강한 보장. (기존 `test_coach.py:574-685`이 solution_coaching verdict 게이팅을 이미 봉인·본 신설이 발화 결정론을 추가 봉인.)

---

## 게이트 ② 재측정 — Kiki 실행 패키지 (Phaiakes9)

보정 라우터(`_EST_ASSUMED_*` 74/358)는 이미 main. **대표 트래픽**으로 재측정해야 판정선(로컬 ≥80%)이 정당하다.

> **2026-07-16 정정(실측 교훈)**: 종전 안내(accumulate 소량 배치)는 무효 — `problem_corpus_accumulate`는 provider를 직접 호출해 파이프라인·라우터·sink를 **우회**하므로 `l3_routing` 이벤트가 0건이다(2회 실측 확인). 이벤트를 내는 유일한 경로는 `l3.pipeline.generate`이고, 이를 대표 요청 믹스로 태우는 전용 도구 **`ops/cost_probe`** 를 신설했다(free-우세 페르소나 A 트래픽 모델·티어는 라우터가 결정·로컬 비율은 인프로세스 집계라 Langfuse 상태와 무관하게 판정선을 냄). 추가 교훈: Langfuse 키가 자리표시자(`pk-lf-…`)면 측정이 조용히 0건이 된다 — 프로브의 인프로세스 판정이 이 취약점을 방어한다.
>
> **2026-07-16 실측 2차(probe_g3) + 통과 조건 상향(Kiki)**: 실제 키 등록 후 프로브 30/30 성공 — **local 27 : cloud_mid 3 = 로컬 90.0% (판정선 ≥80% 충족)**, 클라우드 실측 배선 증명(preflight 0.4066원/63·5tok). 단 Langfuse 기록이 전멸(30/30 실패)해 비용·지연 분포 미확보 — 원인 실측 확정: **Kiki venv langfuse 2.60.10에는 `create_event`가 없다**(v2 쓰기 표면은 `event()`·AttributeError를 sink가 무타입 경고로 삼켜 침묵 실패). Kiki 판정: *"키를 정확하게 올리고, 앞으로 정상적으로 작업하는 것이 보장될 때 통과"* — 게이트 ②는 ①sink SDK 버전 적응 수정 ②재실행에서 기록 실패 0건·cost_report 실제 분포 집계, 두 실증 후 PASS 기입한다(수치만으로 선-기입하지 않음).

```powershell
# [실행 시스템: Windows PowerShell — 이 PC가 곧 Phaiakes9]
# 1. 최신 main(보정 라우터·cost_probe 반영)
cd C:\Users\kiki\Desktop\__AI\WhyMath
git checkout main
git pull origin main

# 2. 전제: Ollama 가동(ollama list로 확인) · WHYMATH_LANGFUSE_*/WHYMATH_ANTHROPIC_API_KEY는
#    실제 값(자리표시자 금지 — cost_report가 ASCII 인코딩 오류 후 0건으로 폴백한다)

# 3. 대표 트래픽 프로브 — 라운드당 10콜(로컬 9:클라우드 1)·rounds 배수. 로컬 비율을
#    즉석 판정(exit 0=PASS)하고 l3_routing 이벤트를 Langfuse에 기록·flush 한다.
.\src\backend\.venv\Scripts\python.exe -m whymath_backend.ops.cost_probe --rounds 3 --json probe_g2.json

# 4. 판독 — 비용·지연 분포(p50/p90)는 Langfuse 집계로(수 초 후 실행)
.\src\backend\.venv\Scripts\python.exe -m whymath_backend.ops.cost_report --days 1 --json cost_report_g2.json
.\src\backend\.venv\Scripts\python.exe scripts\fill_live_cost_table.py cost_report_g2.json
```

**판정선**: 프로브 출력 `로컬 비율 ≥ 80%`(exit 0) → 게이트 ② **PASS**. 미달 시 as-measured 기록 + 후속 튜닝(라우팅 재분포·프롬프트 캐싱) 후 재측정. 프로브·cost_report 출력을 회신하면 서기가 이 문서·`live_cost_measurement_2026-07.md`에 기입하고 최종 판정을 진행한다.

---

## 이후 연결
- 게이트 ② PASS + Kiki 3종 사인오프 → **S1 탈출**: `ROADMAP.md`(:267·281) S1 섹션·`status_roadmap_2026-07.md` S1 탈출 게이트 체크·MEMORY 결정 로그 갱신·`backlog.py done S1-14`.
- S1 탈출은 **S1-11 flip과 독립**(flip=coach→하네스 primary 수렴·별건 게이트). S1 탈출 판정은 현 결정론 서빙 경로 기준.
