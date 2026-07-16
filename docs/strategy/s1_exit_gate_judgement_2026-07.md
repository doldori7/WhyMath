# S1 탈출 게이트 판정 (S1-14) — 스캐폴드 + 게이트 ③ 증명

> **상태**: 🟡 **de-risk 완료·최종 판정 대기** (claude 스캐폴드·게이트 ③ 증명·봉인 완비 / 잔여 = Kiki 게이트 ② 재측정 + 3종 사인오프) | **owner**: kiki(판정)·claude(서기·게이트 ③ 증명)
> **정본 게이트 정의**: `docs/strategy/status_roadmap_2026-07.md` S1 섹션(:104) — "① 실기기 1루프 시연 녹화 ② 루프당 LLM 비용 실측·로컬 80% ③ 학생 응답 = PRM/도구 검증 통과 후 코드 경로 증명"
> **de-risk 취지**(S1-12 런북 #516 선례): claude가 판정 가능한 2개 게이트(①③)를 확정하고 게이트 ②의 Kiki 실행 패키지를 완비해, Kiki 잔여를 **"② 재측정 → 3종 사인오프" 한 세션**으로 축소한다.

---

## 판정 요약

| 게이트 | 정의 | 판정 | 근거 |
|---|---|---|---|
| ① 실기기 시연 | 패드에서 1루프 15분 내 완주 녹화 | ✅ **PASS** | `G-kiki-device-demo` **cleared**·녹화 증거 실재(gates.yaml evidence 링크) |
| ② 루프당 비용·로컬 80% | 루프당 LLM 비용 실측·로컬 ≥80% | ⏳ **PENDING(Kiki 재측정)** | S1-12 실측 72.7% as-measured(<80%)·측정 세션 믹스 비대표·**보정 라우터(74/358)로 대표 트래픽 재측정 필요**(아래 §게이트 ② 명령) |
| ③ PRM/도구 검증 코드 경로 | 학생 응답 = 검증 통과 후가 코드 경로로 증명 | ✅ **PASS(정직 프레이밍)** | 아래 §게이트 ③ 증명 + 기계 봉인 3종(`test_coach_gate3_serving_invariant.py`) |

**최종 판정(Kiki 기입란)**: `[ ]` 게이트 ② 재측정 로컬 ≥80% 확인 → `[ ]` 3종 전부 PASS 사인오프 → **S1 탈출 선언** → ROADMAP·MEMORY 갱신·`backlog.py done S1-14`. (② 미달 시: 라우팅 재분포·프롬프트 캐싱 등 후속 튜닝 후 재측정.)

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

보정 라우터(`_EST_ASSUMED_*` 74/358)는 이미 main. **대표 트래픽**(측정용 스모크가 아닌 실제 코치 루프 믹스)으로 재측정해야 판정선(로컬 ≥80%)이 정당하다.

```powershell
# 1. 최신 main(보정 라우터 반영) 반영 — Phaiakes9 WhyMath 루트에서
cd C:\Users\kiki\Desktop\__AI\WhyMath
git checkout main
git pull origin main
cd src\backend
# (venv 활성 상태 가정 — 아니면 .\.venv\Scripts\Activate.ps1)

# 2. 클라우드·관측성 키 확인(S1-12 세션과 동일 — 이미 설정돼 있으면 생략)
#    $env:WHYMATH_ANTHROPIC_API_KEY / WHYMATH_LANGFUSE_* 가 있어야 실측이 기록됨

# 3. 대표 트래픽 유발 — 실제 코치 루프 믹스(로컬 우선 라우팅이 실작동하는 문항 분포).
#    측정 세션 전용 클라우드 스모크는 로컬 비율을 왜곡하므로 지양.
#    (프로덕션 유사 믹스가 없으면 problem_corpus_accumulate 소량 배치로 대체하되 대표성 캐비엇 병기)

# 4. 판독 — 라이브 세션 직후엔 --days 1
python -m whymath_backend.ops.cost_report --days 1 --json cost_report.json
```

**판정선**: 출력 `local_ratio ≥ 0.80` → 게이트 ② **PASS**. 미달 시 as-measured 기록 + 후속 튜닝(라우팅 재분포·프롬프트 캐싱) 후 재측정. 결과(`cost_report.json`의 `local_ratio`·`tier_stats`)를 회신하면 서기가 이 문서·`live_cost_measurement_2026-07.md`에 기입하고 최종 판정을 진행한다.

---

## 이후 연결
- 게이트 ② PASS + Kiki 3종 사인오프 → **S1 탈출**: `ROADMAP.md`(:267·281) S1 섹션·`status_roadmap_2026-07.md` S1 탈출 게이트 체크·MEMORY 결정 로그 갱신·`backlog.py done S1-14`.
- S1 탈출은 **S1-11 flip과 독립**(flip=coach→하네스 primary 수렴·별건 게이트). S1 탈출 판정은 현 결정론 서빙 경로 기준.
