# WhyMath 튜터링 하네스(WH-1) 설계안 v0.3

> 하네스-1(UIUC·UC버클리·Chroma, arXiv 2606.02373)의 “상태 기반 인지 오프로딩” 구조를
> WhyMath 소크라테스 튜터링 엔진에 이식하는 설계안.
> **v0.2 변경**: 리스크 검토 반영 — 리스크 레지스터(§9) 신설, 0단계(평가 하네스) 추가,
> verify 탈출구·가설 탐색 규칙·fast path·개인정보 스키마 보강,
> §6 비용 절감과 §7 자체 학습을 “확정 효과”에서 “검증 필요 가설”로 강등.
> **v0.3 변경**: 전략 계층(§11) 신설 — 하네스를 “오류 교정기”에서
> “문제해결능력 성장 엔진”으로 확장. 전략 레퍼토리 상태, 힌트 경제(스캐폴딩 페이딩),
> 확신도 보정 루프, 전이 측정 설계. 도구 3종(#9~#11) 추가,
> 0단계 대리 지표 4종→7종 확장, 리스크 R14~R16 추가.
> 작성일: 2026-06-13 | 버전: 0.3

> **편집자 주 (저장소 정합, 2026-06-12)**: 원안 prose를 보존하되, 잠금된 기술 결정과의 정합을 위해
> 다음 표기를 교정했다 — ① **ChromaDB → pgvector**(4건; 2026-06-10 슬98: PostgreSQL 16 확장으로 벡터
> store 통합·별도 ChromaDB 폐기. 본문의 "신규 인프라 0" 주장은 store 1개 감소로 오히려 강화됨)
> ② **Mathpix OCR → PaddleOCR + Qwen3-VL**(§3.3 1건; 2026-05-28: 로컬 처리·미성년자 프라이버시. 본 문서
> §2.3/§11의 프라이버시 원칙과 정합). 현 구현 좌석과의 매핑은 문서 끝 "현 구현 매핑(편집자 부기)" 절 참조.

-----

## 0. 한 줄 요약

**LLM이 프롬프트 안에서 기억·진단·검증을 모두 하던 방식을 버리고,
외부 하네스가 “학생 상태·오개념 가설·증거”를 관리하며
LLM은 매 턴 “다음 교수학적 행동 판단”만 하는 도구 루프(agent loop)로 전환한다.**

단, 검색과 튜터링은 도메인 성격이 다르므로(§9 R1) 검증 가능한 단원부터
하이브리드로 도입하고, 효과는 0단계에서 정의한 대리 지표로 측정한다.

하네스-1의 검색 도메인 개념을 튜터링 도메인으로 번역하면:

|하네스-1 (검색)              |WH-1 (튜터링)                                          |
|------------------------|----------------------------------------------------|
|후보 문서 저장소               |세션 작업 메모리 (풀이 이력·행동 신호)                             |
|큐레이션 세트 (핵심 문서)         |**활성 오개념 가설 세트** (3~5개 후보 + 신뢰도 + 감쇠)               |
|증거 그래프 (인명·날짜 연결)       |**학습 증거 그래프** (오답 이벤트 → 오개념 → 커리큘럼 노드)              |
|verify (사실 검증)          |verify_step (SymPy 동치 검증 + PRM 점수 + unverifiable 상태)|
|웜 스타트 (1차 검색 결과 시드)     |CAT 진단 + 직전 세션 가설 + 단원 고빈도 오개념 프리로드                 |
|8개 전용 도구                |8개 튜터링 전용 도구 (§3) + 전략 도구 3종 (§11.3)                |
|end_search              |end_turn (질문/힌트/출제 중 택1로 턴 종료)                      |
|(하네스-1에 없음 — WH-1 고유 확장)|**전략 계층**: 전략 레퍼토리·힌트 경제·보정·전이 측정 (§11)             |

-----

## 1. 7계층 아키텍처 내 위치

하네스는 **새 계층이 아니다.** L3(콘텐츠 생성·검증)와 L4(교수학 엔진) 사이의
LLM 호출 방식을 바꾸는 **횡단 인프라**다. 계층 경계 원칙(상위→하위 호출만 허용)은 그대로 유지된다.

```
[현재]  L5 오케스트레이터가 L1·L2·L4 컨텍스트 수집
        → 거대 프롬프트 1개 조립 (프롬프트 스터핑)
        → LLM 1회 생성 → 응답

[WH-1]  L5 오케스트레이터가 하네스 세션 개시 (웜 스타트)
        → [fast path 판정: 풀이 제출 없는 단순 턴이면 루프 생략] (§5.3)
        → LLM이 도구 루프 진입:
           read_student_state → match_misconception → curate_hypothesis
           → verify_step → select_probe → ... → end_turn
        → 하네스가 상태 무결성 보장 + BKT 업데이트 큐에 커밋
```

핵심 차이: **상태(state)가 프롬프트 텍스트가 아니라 DB 레코드**가 된다.
LLM 컨텍스트에는 매 턴 “압축된 현재 상태 뷰”만 주입된다.

-----

## 2. 상태 저장소 설계 (Harness State)

기존 기술 스택(PostgreSQL 16 + TimescaleDB, pgvector, Redis 7)을 그대로 사용한다.
**신규 인프라 도입 없음.**

### 2.1 세션 작업 메모리 — Redis

- 키: `harness:session:{session_id}`
- 내용: 현재 문제 ID, 학생 풀이 단계 스택(최근 N개), Polya 단계, 힌트 레벨(0~3),
  verify 결과 캐시, 행동 신호(힌트 요청까지 시간, 지우개 횟수)
- TTL: 세션 종료 + 24h. **단, 웜 스타트에 필요한 미해결 가설은 TTL 만료 전
  PostgreSQL 스냅샷으로 영속화** (R7 대응 — Redis 휘발로 인한 연속성 단절 방지)

### 2.2 활성 오개념 가설 세트 — Redis + PostgreSQL 스냅샷

하네스-1의 “큐레이션 세트”에 해당. LLM이 임의로 늘리지 못하도록 **최대 5개 강제**.

```json
{
  "hypotheses": [
    {
      "misconception_id": "M-217",
      "label": "이차함수 a<0이면 그래프가 아래로 볼록이라고 착각",
      "confidence": 0.72,
      "last_supported_turn": 14,
      "evidence_refs": ["ev-1031", "ev-1045"],
      "status": "active"
    }
  ]
}
```

**확증편향 방지 규칙 (v0.2 신설, R4 대응):**

1. **시간 감쇠**: 가설 confidence는 새 지지 증거 없이 3턴 경과 시마다 ×0.85 감쇠.
   웜 스타트로 프리로드된 가설도 예외 없음 — 초기 가설이 영구 고착되는 것을 방지.
1. **ε-탐색 강제**: 5턴마다 1회, select_probe는 활성 가설 세트 *밖*의
   오개념(해당 노드에 태깅된 차순위 후보)을 겨냥한 문항을 의무 선택.
   하네스가 카운터를 관리하고 위반 시 probe 요청을 거부한다.
1. **반박 증거 우선 기록**: verify_step이 가설 예측과 모순되는 결과를 내면
   하네스가 자동으로 polarity=-1 증거를 기록 (LLM의 선택적 무시 차단).

### 2.3 학습 증거 그래프 — PostgreSQL

기존 `learning_events` 이벤트 소싱 테이블과 545노드 커리큘럼 그래프 **위에 엣지만 추가**한다.

```sql
-- 증거: 개별 학습 이벤트가 어떤 가설을 지지/반박하는지
CREATE TABLE evidence_links (
  link_id          BIGSERIAL PRIMARY KEY,
  session_id       UUID NOT NULL,
  student_id       UUID NOT NULL,            -- v0.2: 삭제권 연쇄 처리용 명시
  event_id         BIGINT REFERENCES learning_events(event_id) ON DELETE CASCADE,
  misconception_id TEXT REFERENCES misconceptions(id),   -- 400개 오개념 DB
  node_id          INT REFERENCES curriculum_nodes(id),  -- 545노드
  polarity         SMALLINT,      -- +1 지지, -1 반박
  weight           REAL,          -- verify/PRM 기반 가중치
  retention_until  DATE,          -- v0.2: 보존 기한 (기본 졸업+1년, 정책 설정)
  created_at       TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_evidence_student ON evidence_links(student_id);  -- 삭제권 행사 대비
```

이 테이블 하나로 “이 학생이 이차함수를 못 푸는 진짜 원인은 인수분해 노드”라는 진단이
LLM 추론이 아닌 **SQL 조회**로 나온다. 학부모 리포트의 신뢰 근거도 이것이다.

**개인정보 설계 원칙 (v0.2 신설, R11 대응):**

- 증거 그래프는 미성년자의 인지·행동 정밀 프로파일에 해당 →
  만 14세 미만은 법정대리인 동의를 가입 플로우에 통합 (개인정보보호법 §22의2)
- 삭제권 행사 시: student_id 기준 evidence_links → learning_events 연쇄 삭제
  (ON DELETE CASCADE + 배치 검증), BKT 상태 초기화, pgvector 임베딩 삭제까지 한 트랜잭션 단위로
- retention_until 경과 레코드는 야간 배치로 자동 파기
- 이 설계는 나중에 붙이기 어려우므로 **스키마 1차 마이그레이션에 포함** (선택이 아님)

### 2.4 장기 상태 — 기존 L2 그대로

BKT 숙달도 벡터는 변경 없음. 하네스가 `end_turn` 시 업데이트 큐에 푸시하고
비동기 워커가 갱신하는 기존 패턴 유지.

-----

## 3. 전용 도구 8종 명세

|#|도구                   |입력                                |출력                                               |담당 계층|
|-|---------------------|----------------------------------|-------------------------------------------------|-----|
|1|`read_student_state` |node_ids[]                        |BKT 숙달 확률, 오개념 이력, 정서 프록시                        |L2   |
|2|`verify_step`        |expr_before, expr_after, step_type|`correct` / `incorrect` / `unverifiable` + PRM 점수|L3   |
|3|`match_misconception`|학생 풀이 단계 텍스트                      |pgvector 검색 → 오개념 후보 top-5 + 유사도 + **품질 플래그**    |L2/L3|
|4|`curate_hypothesis`  |add/remove, m_id, evidence_refs[] |갱신된 가설 세트 (최대 5개·감쇠·ε-규칙 적용)                     |하네스  |
|5|`query_curriculum`   |node_id, relation(선수/후속/형제)       |관련 노드 + 숙달 확률 조인                                 |L1+L2|
|6|`select_probe`       |hypothesis_id 1~2개                |진단 문항 1개 (§3.2 근사 방식)                            |L4   |
|7|`log_evidence`       |event_id, m_id, polarity          |evidence_links 기록                                |하네스  |
|8|`end_turn`           |action(질문/힌트/출제/격려), payload      |학생에게 전달 + BKT 커밋                                 |L4→L5|

### 3.1 verify_step 3상태 설계 (v0.2 수정, R5 대응)

v0.1의 “verify 없이 end_turn 거부” 규칙은 검증 불가 단원에서 교착을 일으킨다. 수정:

- **3상태 반환**: `correct` / `incorrect` / `unverifiable`
- 식 변형(대수 연산): SymPy 동치 검증 → correct/incorrect
- 서술형 논증·증명·보조선 기하·경우 나누기: `unverifiable` 반환 + step_type 기록
- **강제 규칙 수정**: 풀이 단계 포함 턴은 verify_step *호출*은 의무이되,
  unverifiable이면 통과. 단, 그 턴의 evidence weight를 0.5로 할인하고
  세션 메타에 `unverified_ratio`를 누적 기록한다.
- **솔직한 한계 인정**: unverifiable 비율이 높은 단원(중학 기하 등)에서는
  환각 차단 보장이 부분적이다. 0단계에서 단원별 verify 커버리지를 측정해
  커버리지 70% 이상 단원부터 하네스를 켠다 (§8.4).
- PRM800K는 영어 GSM8K/MATH 분포 → 한국 교육과정 샘플 200문항으로
  오탐/미탐률 사전 측정 후 가중치 결정 (0단계 과제).

### 3.2 select_probe 현실화 (v0.2 수정, R6 대응)

“가설 A·B를 판별하는 전용 문항이 항상 존재”한다는 가정은 조합 폭발로 비현실적.
수정: 문제은행 문항에 오개념 태그(다중)를 부여하고, **정보 이득 근사** —
“가설 A 태그는 있고 B 태그는 없는 문항” 중 학생 숙달도 대비 적정 난이도 문항을
IRT 정보함수로 선택한다. 완전 판별이 아닌 근사임을 진단 신뢰도 표시에 반영
(가설 confidence 상한 0.9 — 시스템이 “확신”을 출력하지 않게).

### 3.3 match_misconception 품질 게이트 (v0.2 신설, R6 대응)

- 입력이 PaddleOCR+Qwen3-VL 산출물이면 OCR confidence < 0.8 시 `low_quality` 플래그 →
  LLM이 학생에게 재확인 질문을 하도록 유도 (오염된 매칭으로 가설 세우는 것 방지)
- 유사도 top-1 < 0.65면 “후보 없음” 반환 — 억지 매칭 금지
- **선결 조건**: 400개 오개념 항목당 예시 오답 최소 5개의 임베딩 적재.
  현재 DB의 예시 충족률을 0단계에서 감사(audit)하고 미달 항목은 합성 예시로 보충.

### 3.4 설계 원칙 (유지)

1. verify_step 호출 의무 (3상태로 완화, §3.1)
1. select_probe는 정보 이득 근사 (§3.2)
1. **end_turn만이 학생에게 말할 수 있다.** 중간 도구 호출은 전부 내부 동작.

> **v0.3**: 전략 계층 도구 3종(#9 log_strategy_event, #10 elicit_prediction,
> #11 assign_transfer_probe)이 추가됨 — 명세는 §11.3 참조.

-----

## 4. 웜 스타트 (Warm Start)

세션 시작 시 하네스가 LLM 개입 없이 자동 구성:

1. **CAT/진단고사 결과** → 해당 단원 노드들의 BKT 사전확률 시드
1. **직전 세션의 미해결 가설** (PostgreSQL 스냅샷에서 복원, §2.1)
1. **해당 단원의 모집단 고빈도 오개념 top-3** — 단, §2.2 감쇠 규칙 적용 대상.
   프리로드 가설은 confidence 0.4로 시작(겸손한 사전확률)하여 고착 방지.

→ LLM은 첫 턴부터 “백지 진단”이 아니라 **“초안 검증·보완”**으로 시작한다.
체감 효과는 “선생님이 지난 시간 내용을 기억하고 있다”는 연속성 경험이다.

-----

## 5. 루프 제어·압축 (하네스 자동 담당)

### 5.1 압축 — 무손실 원칙 (v0.2 수정, R8 대응)

v0.1의 “요약 압축”은 오개념을 드러내는 학생의 정확한 표현
(“음수를 빼면 더 작아지잖아요”)을 유실할 위험. 수정:

- **원문은 절대 삭제하지 않는다.** 10턴 초과 시 원문을 컨텍스트에서만 제외하고
  PostgreSQL에 보존, `recall_dialogue(turn_range)` 보조 도구로 LLM이 재조회 가능
- 컨텍스트에는 하네스가 만든 구조화 인덱스(턴 번호, 이벤트 유형, 가설 변화)만 유지
- 반박된 가설(confidence < 0.2): archived 전환, 증거 그래프엔 보존

### 5.2 루프 가드 (v0.2 신설, R2 대응)

- 턴당 도구 호출 상한 8회 — 초과 시 하네스가 강제 end_turn(안전 응답: 단계 확인 질문)
- 동일 도구 동일 인자 2회 반복 → 거부 + 경고 주입 (thrashing 차단)
- 도구 호출 JSON 스키마 검증 실패 2회 연속 → 해당 턴을 클라우드 모델로 폴백

### 5.3 Fast Path (v0.2 신설, R9 대응)

풀이 제출이 없는 턴(인사, “네”, 격려 요청, 단순 진행 확인)은 하네스가 사전 분류해
도구 루프 없이 경량 생성으로 즉답. 풀이 포함 턴만 풀 루프를 돈다.
→ 평균 체감 레이턴시를 낮추고, “생각 중…” 스트리밍 UI는 풀 루프 턴에만 표시.

-----

## 6. 모델 라우팅 — 【검증 필요 가설】 (v0.2 강등, R2 대응)

v0.1은 “Qwen3 로컬 판단 루프”를 기대 효과로 적었으나, 하네스-1의 성능은
**하네스 환경에서 학습된 모델**의 결과다. 학습 없는 기성 모델의 도구 호출
신뢰성은 미검증이므로 다음 3단계로 강등한다:

|단계    |판단 루프                          |조건                                |
|------|-------------------------------|----------------------------------|
|A (출시)|Claude Haiku                   |즉시 가능, 비용 중간                      |
|B (검증)|Qwen3-Math 로컬 (Phaiakes9) 섀도 모드|Haiku와 병렬 실행, 도구 호출 일치율 ≥ 90% 달성 시|
|C (전환)|Qwen3 주력 + Claude 에스컬레이션       |B 통과 + §7 SFT 완료 후                |

최종 소크라테스 질문 문장 생성은 전 단계에서 Claude API(짧은 호출) 유지.
**비용 절감은 C단계 도달 시에만 실현되는 가설이며, A단계만으로도
긴 세션 품질·설명 가능 진단이라는 효과는 독립적으로 성립한다** — 이것이
하네스 도입의 1차 정당화이고, 비용 절감은 2차다.

-----

## 7. 자체 모델 학습 경로 — 【검증 필요 가설】 (v0.2 강등, R1·R10 대응)

하네스-1 레시피의 직접 이식에는 두 가지 장벽이 있다:

1. **보상 신호 부재 (근본 장벽)**: 검색은 리콜이라는 객관 보상이 있지만,
   “좋은 소크라테스 질문”은 자동 채점 불가. RL 이전에 보상 모델 설계가 별도 과제.
   현실적 대안: (a) 대리 보상 — verify 통과율·가설-실제 일치율·세션 완주율 합성,
   (b) RLHF-lite — 주간 100개 turn 샘플에 본인이 직접 rubric 채점한 선호 데이터.
   둘 다 “노이즈 있는 보상”이므로 RL은 SFT 효과 확인 후로 보류.
1. **약관**: 상용 모델(Claude) 출력으로 자체 모델을 학습시키는 것은
   Anthropic 이용약관의 학습 제한 조항 검토 선행 필수. 위반 소지가 있으면
   교사 모델을 오픈 가중치 대형 모델(예: 하네스-1 자체, Qwen 대형)로 대체.

조건이 충족되면: 교사 모델 trajectory ~1,000개 → Qwen3-Math SFT.
하네스-1이 899개로 충분했다는 점은 여전히 유효한 희망적 근거이나,
**검증 가능 도메인의 결과를 교수학 품질로 외삽한 것**임을 명시해 둔다.

-----

## 8. 현재 WhyMath 시스템과의 차이 분석

### 8.1 무엇이 바뀌는가

|측면      |현재 (프롬프트 스터핑)          |WH-1 적용 후                        |
|--------|-----------------------|---------------------------------|
|학생 상태   |프롬프트 안 텍스트, 턴마다 재조립, 휘발|외부 DB 레코드, 명시적·감사 가능             |
|오개념 진단  |LLM의 턴별 즉흥 추론 (재현 불가)  |가설 세트 + 증거 링크 (설명 가능, SQL 조회)    |
|긴 세션 품질 |컨텍스트 비대 → 일관성 붕괴       |하네스 압축 → 30턴에도 일정 품질             |
|풀이 검증   |LLM 자가 판단 의존 (환각 위험)   |verify_step 의무 호출 (커버리지 한계는 §3.1)|
|모델 의존성  |대형 모델 필수               |단계적 경량화 (§6, 가설)                 |
|단원 확장   |단원별 프롬프트 튜닝 필요         |도구 사용법은 단원 불변 → 일반화 기대           |
|API 비용  |턴당 거대 컨텍스트 호출          |A단계: 소폭 개선 / C단계: 구조적 절감 (가설)    |
|학부모 리포트 |LLM 생성 요약              |증거 그래프 직접 시각화 (근거 제시)            |
|물리/화학 확장|튜터 프롬프트 재설계            |하네스 재사용 + 도메인 도구만 교체             |

### 8.2 무엇이 바뀌지 않는가 (기존 자산 보존)

- **7계층 경계 원칙**: 그대로. 하네스는 L3/L4 구현 방식 변경이지 계층 재편이 아님
- **545노드 그래프, 400개 오개념 DB, CSAT 55+108 패턴**: 하네스 상태 저장소의 재료
- **learning_events 이벤트 소싱**: evidence_links가 위에 조인되는 구조라 무변경
- **기술 스택**: PostgreSQL/pgvector/Redis/Ollama 전부 기존 그대로

### 8.3 새로 감수하는 비용

1. **레이턴시**: 풀 루프 턴 2~5초+ (낙관 추정). 완화: fast path(§5.3), 도구 병렬화, 웜 스타트
1. **엔지니어링 복잡도**: 사실상 분산 시스템. Langfuse 추적을 0단계에 선행 구축 (§8.4)
1. **로컬 모델 신뢰성**: §6의 3단계 게이트로 관리

### 8.4 수정된 도입 로드맵 (v0.2 — 0단계 신설)

|단계          |작업                                                                                                                                                                                                   |산출물 / 게이트                          |
|------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-----------------------------------|
|**0단계** (신설)|① 평가 하네스: 대리 지표 **7종** 정의·계측 (verify 통과율, 진단-실제 오개념 일치율, 세션 완주율, 턴당 토큰 + **도움 감소 곡선 기울기, 보정 점수, 전이 점수** — §11.6) ② 단원별 verify 커버리지 측정 ③ 오개념 DB 예시 충족률 감사 ④ Langfuse 추적 구축 ⑤ PRM800K 한국 문항 200개 오탐률 측정|커버리지 맵 + 베이스라인 수치 (이것 없이는 효과 주장 불가)|
|1단계         |verify_step + match_misconception 2개 도구를 기존 파이프라인에 삽입                                                                                                                                                |verify 커버리지 ≥ 70% 단원에서만 활성         |
|2단계         |활성 가설 세트(감쇠·ε-규칙) + evidence_links (개인정보 스키마 포함)                                                                                                                                                     |진단-실제 일치율이 베이스라인 대비 유의 개선          |
|3단계         |전체 도구 루프 + 웜 스타트 + fast path. 판단 루프는 Claude Haiku (§6 A단계)                                                                                                                                           |세션 완주율·30턴 품질 A/B                  |
|4단계         |(가설) Qwen3 섀도 → 전환 (§6 B·C단계), trajectory 수집 → SFT (§7)                                                                                                                                              |도구 호출 일치율 ≥ 90%, 약관 검토 통과          |

**적용 범위 원칙**: verify 가능한 대수 연산 중심 단원부터 켜고,
기하·서술형은 기존 방식과 병행하는 하이브리드 운영. 전 단원 일괄 전환은 하지 않는다.

-----

## 9. 리스크 레지스터 (v0.2 신설)

|ID |리스크                                                           |심각도|가능성  |대응 (설계 반영 위치)                                          |
|---|--------------------------------------------------------------|---|-----|-------------------------------------------------------|
|R1 |검색≠튜터링: RL 보상 신호 부재, +17%p 일반화 외삽 불가                          |높음 |높음   |§7 강등, 대리 보상 설계, RL 보류                                 |
|R2 |기성 로컬 모델의 도구 호출 신뢰성 미검증 (하네스-1은 학습된 모델)                       |높음 |높음   |§6 3단계 게이트, §5.2 루프 가드·폴백                              |
|R3 |논문이 동료심사 전 프리프린트, 자체 평가                                       |중간 |—    |아키텍처 베팅 최소화: 점진 이식 + 0단계 자체 측정                         |
|R4 |가설 세트 확증편향 고착 (웜 스타트 프리로드의 자기실현)                              |높음 |중간   |§2.2 감쇠·ε-탐색·반박 증거 자동 기록                               |
|R5 |verify_step 교착 (서술형·증명·기하 검증 불가) + PRM 분포 차이                  |높음 |확실   |§3.1 3상태, 커버리지 게이트, 0단계 오탐률 측정                         |
|R6 |match_misconception 오염 (OCR 노이즈, 표면 유사≠인지 원인) / probe 문항 조합 폭발|중간 |중간   |§3.3 품질 게이트, §3.2 정보 이득 근사 + confidence 상한             |
|R7 |상태 무결성: Redis 휘발, 비동기 경쟁 조건, 세션 복구                            |중간 |중간   |§2.1 PostgreSQL 스냅샷, end_turn 단일 커밋 지점                 |
|R8 |압축 손실 — 진단 단서가 되는 학생 원문 표현 유실                                 |중간 |중간   |§5.1 무손실 원칙 + recall_dialogue 도구                       |
|R9 |레이턴시 — 단순 턴까지 풀 루프, 학생 이탈                                     |중간 |높음   |§5.3 fast path, 병렬 호출, 스트리밍 UI                         |
|R10|효과 측정 불가 — 학습 성과 A/B는 수개월, 인프라만 짓고 효과 모름                      |높음 |높음   |§8.4 0단계 대리 지표 선행 (게이트 조건화)                            |
|R11|미성년자 행동 프로파일링 — 동의·보존·삭제권 미비 시 법적 리스크                         |높음 |낮음~중간|§2.3 스키마 단계 내장 (동의 플로우·retention·연쇄 삭제)                |
|R12|1인 운영 복잡도 — 도구 루프 디버깅 불가                                      |중간 |높음   |0단계 Langfuse 선행, 루프 가드 로그 표준화                          |
|R13|Claude 출력 기반 학습의 약관 저촉                                        |중간 |중간   |§7 약관 검토 선행, 오픈 가중치 교사 모델 대안                           |
|R14|전략 태깅의 비검증성 — LLM 추론 의존이라 오개념(verify 가능)보다 노이즈 큼              |중간 |높음   |§11.1 증거 가중치 하향·관찰 횟수 기반 갱신, strategy confidence 상한 0.7|
|R15|지표 왜곡 행동 — 힌트 회피를 위한 방치·찍기 등 측정 게이밍                           |중간 |중간   |§11.2 도움 감소를 정답률 유지와 결합 판정, 이탈·무작위 응답 신호 교차 검증         |
|R16|예측 요구의 UX 마찰 — 확신도 질문 피로로 이탈                                  |낮음 |중간   |§11.3 elicit_prediction 세션당 2회 상한, 원탭 이모지 UI           |

-----

## 10. 종합 판단 (v0.2)

- 하네스의 **1차 가치는 비용 절감이 아니라**: ① 설명 가능한 진단(증거 그래프),
  ② 긴 세션 품질(상태 외부화+압축), ③ 구조적 검증(verify 의무화). 이 셋은
  Claude Haiku 판단 루프(A단계)만으로 성립한다.
- 비용 절감(§6 C단계)과 자체 모델(§7)은 **검증 필요 가설**로 관리하고,
  게이트(도구 호출 일치율 90%, 약관 검토)를 통과해야만 진행한다.
- 모든 단계 진입은 0단계에서 정의한 대리 지표의 베이스라인 대비 개선을 조건으로 한다.
  “측정 없는 도입 없음”이 v0.2의 제1원칙이다.
- **v0.3**: 전략 계층(§11)은 하네스를 “오류 교정기”에서 “문제해결능력 성장 엔진”으로
  확장한다. 성장 판정은 **도움 감소 곡선(행동 증거)과 전이 점수(성과 증거) 두 축**으로 하며,
  둘 다 종단 지표이므로 단기 A/B로는 검증 불가함을 명시한다.

-----

## 11. 전략 계층 (Strategy Layer) — v0.3 신설

> **목적**: 오개념 교정(§2~§3)은 도메인 내 숙달을 견인하지만, 문제해결능력
> (낯선 문제에서의 표상 선택·전략 수립·우회)의 지속 상승까지 보장하지 않는다.
> ITS 연구의 일관된 한계가 근전이는 강하고 원전이는 약하다는 것(VanLehn 2011 등).
> 전략 계층은 이 격차를 겨냥한 WH-1 고유 확장으로, 하네스의 상태 관리 능력이
> 있어야만 가능한 설계다 (프롬프트 스터핑 방식에서는 종단 추적 자체가 불가).

### 11.1 전략 레퍼토리 상태 (Strategy Repertoire State)

오개념 가설 세트(§2.2)와 나란히, “이 학생이 보유한 문제해결 휴리스틱”을 추적한다.

**휴리스틱 노드 사전 (~20종, Polya·Schoenfeld 분류 기반):**
거꾸로 풀기(working backwards), 특수화/일반화, 그림·표 그리기(표상 전환),
보조선 도입, 경우 나누기, 패턴 찾기, 변수 도입, 대칭 활용, 극단값 검사,
단순한 문제로 환원, 반례 탐색, 식↔그래프 전환, 검산 습관, 조건 재진술 등.

```sql
-- 전략 노드 사전 (545 커리큘럼 노드와 별도 차원)
CREATE TABLE strategy_nodes (
  strategy_id   TEXT PRIMARY KEY,      -- 'S-03' 등
  name_ko       TEXT NOT NULL,         -- '거꾸로 풀기'
  polya_stage   SMALLINT,              -- 주 발현 단계 (1~4)
  description   TEXT
);

-- 전략 증거 (evidence_links와 동형, 단 가중치 체계가 다름)
CREATE TABLE strategy_evidence (
  link_id      BIGSERIAL PRIMARY KEY,
  student_id   UUID NOT NULL,
  event_id     BIGINT REFERENCES learning_events(event_id) ON DELETE CASCADE,
  strategy_id  TEXT REFERENCES strategy_nodes(strategy_id),
  source       TEXT,    -- 'llm_tag' | 'polya_transition' | 'tool_interaction' | 'self_correction'
  weight       REAL,    -- llm_tag는 상한 0.5 (R14: 추론 의존이라 노이즈 큼)
  created_at   TIMESTAMPTZ DEFAULT now()
);
```

**학생별 strategy_mastery**: BKT 유사 보유 확률. 단 오개념과의 결정적 차이 —
전략 사용은 verify로 직접 검증 불가하므로 **confidence 상한 0.7**, 갱신은
관찰 횟수 기반(단일 강한 증거보다 반복 관찰 우선).

**증거 소스 4종:**

1. Polya 단계 전환 로그 (계획 단계에서 머문 시간, 단계 회귀 패턴)
1. 풀이 텍스트의 전략 태그 — LLM 추론 (`source='llm_tag'`, 노이즈 명시)
1. 그래핑 계산기 등 탐구 도구 조작 (식↔그래프 전환 신호 — 기존 설계의 조작 로그 환류와 결합)
1. 자기 교정 이벤트 (지우개 후 다른 접근으로 전환 = 전략 전환 능력의 직접 증거)

### 11.2 힌트 경제 — 스캐폴딩 페이딩 (Scaffolding Fading)

생산적 어려움(productive struggle)을 보호하고, 도움 의존도를 의도적으로 줄인다.

**상태**: 학생×노드별 `hint_economy = {time_to_first_hint, hints_per_problem, unaided_success_rate}`

**정책 (하네스가 구조적으로 강제):**

1. **개입 금지 타이머**: 학생 수준별 최소 자력 시간(예: 중3 기본 90초, 심화 180초)
   경과 전에는 LLM이 힌트성 end_turn 불가 — 격려·관찰 질문만 허용.
   하네스가 타이머를 관리하므로 LLM의 “친절 본능”이 구조적으로 차단된다.
   단, 정서 가드레일(연속 오답 + 이탈 신호 감지) 발동 시 타이머 해제.
1. **페이딩 스케줄**: 동일 노드 재방문 시 힌트 레벨 상한을 세션마다 한 단계씩
   하향 (3→2→1→0). 학생이 상한 0에서 unaided_success를 기록하면 해당 노드 졸업.
1. **핵심 지표 — 도움 감소 곡선**: 시간축에서 (힌트/문제) 감소 & 정답률 유지가
   동시에 성립할 때만 개선으로 판정 (R15: 힌트 회피만으로는 인정 안 함.
   방치·무작위 응답 신호와 교차 검증).

### 11.3 추가 도구 3종 (#9~#11)

|# |도구                     |입력                                       |출력/효과                                        |사용 규칙                        |
|--|-----------------------|-----------------------------------------|---------------------------------------------|-----------------------------|
|9 |`log_strategy_event`   |event_id, strategy_id, source, confidence|strategy_evidence 기록                         |llm_tag는 weight 상한 0.5       |
|10|`elicit_prediction`    |problem_id 또는 step_id                    |학생 UI에 “맞을 것 같아? (1~5)” 원탭 질문 트리거 → 보정 데이터 수집|**세션당 최대 2회** (R16 UX 마찰 관리) |
|11|`assign_transfer_probe`|pattern_id, surface_constraints          |CSAT 패턴 동일·표면 상이 문항 출제                       |주간 1회 자동 스케줄 + 노드 숙달 2주 후 트리거|

### 11.4 확신도 보정 루프 (Calibration Loop)

메타인지 향상의 검증된 개입 — WhyMath의 “왜” 철학과 직결.

1. verify_step 실행 *전*에 elicit_prediction으로 학생 예측(확신 1~5) 수집
1. 예측 vs verify 결과 → Brier score 류 **보정 점수** 산출, 종단 추적
1. **과신 구간**(틀렸는데 확신 5): 소크라테스 질문 강도 상향 — “왜 그렇게 확신해?”
1. **과소신 구간**(맞았는데 확신 1): 성취 명시 피드백 — 효능감 회복
1. 학부모 리포트에 “자기 평가 정확도” 항목 신설 — 점수 외 성장 지표 제공

### 11.5 전이 측정 — CSAT 패턴 자산 활용

문제해결능력 상승의 **직접 성과 측정치**. 기존 자산(시그니처 패턴 55종 + 하위 108종)이
정확히 이 용도에 들어맞는다.

- **정의**: 학습한 패턴과 심층 구조는 동일하되 표면(소재·숫자·맥락)이 다른
  초견 문항의 정답률 = **전이 점수(transfer score)**
- **출제 주기**: 노드 숙달(BKT ≥ 0.95) 도달 2주 후 자동 출제 — 간격 반복 효과 겸용
- **판정 프레임**: 도움 감소 곡선(행동 증거) × 전이 점수(성과 증거) 두 축.
  둘 다 상승 → 문제해결능력 성장 / 절차 점수만 상승·전이 정체 → “교정기 함정”
  경보로 전략 계층 개입 비중 상향

### 11.6 0단계 대리 지표 확장 (4종 → 7종)

기존 4종(verify 통과율, 진단 일치율, 세션 완주율, 턴당 토큰)에 추가:
**⑤ 도움 감소 곡선 기울기 ⑥ 보정 점수 ⑦ 전이 점수**.
⑤~⑦은 종단 지표이므로 베이스라인 수집 기간을 최소 4주로 설정한다.

### 11.7 전략 계층의 한계 (정직한 명시)

1. 전략 태깅은 LLM 추론 의존 → 오개념(verify 가능)보다 본질적으로 노이즈가 크다.
   confidence 상한 0.7과 관찰 횟수 기반 갱신은 완화책이지 해결책이 아니다.
1. 효과 검증은 전이 점수의 종단 개선으로만 가능 — 단기 A/B로는 증명 불가.
   따라서 전략 계층의 ROI 판정은 도입 후 최소 1분기를 요한다.
1. 끈기·효능감 같은 정의적 측면은 행동 프록시의 한계 내에서만 포착된다.
   설문 기반 정의적 진단(AskMath류)과의 결합은 별도 검토 과제.

-----

## 참고

- 하네스-1 논문: arXiv 2606.02373 (Stateful Search Harness)
- 코드/가중치: github.com/pat-jj/harness-1, huggingface.co/pat-jj/harness-1 (Apache 2.0)
- 기사: AI타임스 2026-06-09, “20B로 GPT-5.4 검색 성능 능가”
- 변경 이력: v0.1 (2026-06-13 초안) → v0.2 (리스크 검토 반영) → v0.3 (전략 계층 신설)
-----

## 현 구현 매핑 (편집자 부기, 2026-06-12)

> 본 설계안은 *목표 상태*다. 아래 표는 현재 백엔드 구현 좌석과의 연결·델타를 정리한다(추적용).

|설계안 좌석                         |현 구현 (가동 중)                                                                 |델타·비고                                            |
|-------------------------------|---------------------------------------------------------------------------|-------------------------------------------------|
|`read_student_state`(BKT·오개념·정서)|L2 `concept_mastery_history`(BKT)·`get_current_mastery`·`compute_concept_diagnoses`|정서 프록시 미구현                                       |
|`match_misconception`(pgvector top-5)|L4 오개념 의미 매처(slice104+·pgvector `misconception` 임베딩)                          |카탈로그 **30종**(설계안 "400"=목표·§3.3 audit으로 보강)         |
|`query_curriculum`(선수/후속)       |`concept_edge` PREREQUISITE + `fetch_prerequisites`(재귀 CTE·다단계)              |후속/형제 EdgeType은 후속 확장(현 데이터 전량 prerequisite)       |
|`curate_hypothesis`/`select_probe`|L2 `recommend_weak_concepts`·`recommend_prerequisite_gaps`                  |가설 세트(감쇠·ε)·`evidence_links`는 향후 스키마             |
|`end_turn` 코칭 결정               |L4 `recommend_coaching`·`recommend_prerequisite_coaching`·`GET /v1/me/.../coaching`·`/v1/coach/sessions`|§11.2 힌트 경제(개입 금지 타이머)는 이 코칭 결정의 *집행 런타임*       |
|상태 저장소                        |PostgreSQL 16·Redis 7 (가동)·**벡터=pgvector**                                  |`evidence_links`·`strategy_*`는 향후 alembic 마이그레이션 |
|커리큘럼 노드                       |개념그래프 **403개념**(`concept` code=UC)·NCIC 성취기준                                |설계안 "545노드"와 용어·수치 정합 필요                         |

미구현 테이블(`evidence_links`·`strategy_nodes`·`strategy_evidence`)은 *향후 스키마*다 — 구현 시 alembic 마이그레이션과 §2.3 개인정보 설계(14세 미만 동의·retention·삭제권 연쇄)를 1차에 포함한다. 본 하네스 도입은 ROADMAP상 **0단계(평가 하네스)·verify_step·match_misconception은 Phase 1~2, 전체 도구 루프·전략 계층·자체 모델 학습은 Phase 2~3**으로 단계화한다(1인 capacity 가드·"측정 없는 도입 없음").

### `evidence_links` 스키마 — 실제 테이블 매핑 (편집자 부기)

§2.3의 `evidence_links` DDL은 *설계 시점 추상 스키마*다. 구현 시 실제 backend 테이블에 맞춘다(`learning_events`·`curriculum_nodes` 신설 불요):

|설계 DDL 참조                                       |실제 테이블 (현 backend)                                                       |정합 메모                                                          |
|------------------------------------------------|-----------------------------------------------------------------------|---------------------------------------------------------------|
|`event_id BIGINT REFERENCES learning_events(event_id)`|**`attempt_event`**(BIGSERIAL `event_id` + `event_at` **복합 PK**·TimescaleDB hypertable)|`learning_events` 테이블 *미존재* → `attempt_event`로. 복합 PK라 FK는 (event_id, event_at) 또는 대리키 필요(hypertable 제약)|
|`misconception_id TEXT REFERENCES misconceptions(id)`|오개념 카탈로그 TEXT id(kebab-case)·`misconception_embedding(misconception_id TEXT PK)`|TEXT 일치 ✓·카탈로그 현 **30종**(설계 "400"=목표)                          |
|`node_id INT REFERENCES curriculum_nodes(id)`     |**`concept(concept_id UUID PK·code=UC TEXT)`**                         |`curriculum_nodes(INT)` *미존재* → `concept.concept_id`(UUID) 또는 `concept.code`(UC). **INT→UUID/TEXT 형 변경**|
|`student_id UUID`                                |`user_profile.user_id`(UUID)                                           |명칭만 다름(student_id≈user_id) ✓                                  |

`evidence_links`는 *신규 테이블*이되 FK 타깃을 위 실제 테이블로 정정해 마이그레이션한다.

### 용어·수치 정합: "545 노드" → 구현 403 개념

본문의 "545노드 커리큘럼 그래프"는 *설계 시점 추정치*이며 현 저장소에 해당 실체가 없다(레포 grep 결과 "545"는 본 문서 외 0). 구현된 커리큘럼/개념 계층은 **개념그래프 v1 — 403 개념(`concept`·code=UC) + 541 선수엣지(`concept_edge` PREREQUISITE)** + NCIC 성취기준이다. 성취기준 노드를 별도 차원으로 둘 경우 수치를 실측으로 확정한다("545"는 미반영 추정치).

### 도구 11종 → 실제 좌석 1:1 매핑 (편집자 부기)

§3(8종)·§11.3(전략 3종)의 도구를 *현 backend 좌석*에 매핑한다. 상태: 🟢 가동 · 🟡 부분 · 🔴 미구현.

|# |도구                   |계층    |실 구현 좌석 (현 backend)                                                                                       |상태                                             |
|--|---------------------|------|--------------------------------------------------------------------------------------------------------|-----------------------------------------------|
|1 |`read_student_state` |L2    |`get_current_mastery`(BKT)·`compute_concept_diagnoses`(BKT+IRT)·`get_current_theta`/`compute_concept_abilities`(θ)·`concept_mastery_history`|🟡 정서 프록시 미구현                                  |
|2 |`verify_step`        |L3    |L4 `recommend_coaching_for_solution`(verify_steps 신호)·L3 SymPy 검증·PRM(PRM800K)                            |🟡 3-state(unverifiable)·한국 PRM 보정은 0단계         |
|3 |`match_misconception`|L2/L3 |L4 `misconception/diagnose`(substring+정규식+의미)·pgvector `misconception_embedding`(slice104+)              |🟢 카탈로그 30종·top-1<0.65 게이트                     |
|4 |`curate_hypothesis`  |하네스   |(근접) L2 `recommend_weak_concepts`                                                                         |🔴 가설 세트·감쇠 ×0.85·ε-탐색·최대 5 미구현             |
|5 |`query_curriculum`   |L1+L2 |`concept_edge` PREREQUISITE·`fetch_prerequisites`(재귀 CTE 다단계)·`recommend_prerequisite_gaps`             |🟢 선수(후속/형제 EdgeType은 후속)                      |
|6 |`select_probe`       |L4    |`GET /v1/me/next-problem`·`select_weighted_item`(IRT 정보량 CAT·slice L2-12/16)                              |🟡 정보량 출제 가동·가설 판별 태깅/ε 미구현                  |
|7 |`log_evidence`       |하네스   |(근접) `record_attempt_mastery`·`attempt_event`(이벤트 소싱·TimescaleDB)                                       |🔴 `evidence_links`(polarity·weight) 미구현        |
|8 |`end_turn`           |L4→L5 |`recommend_coaching`·`recommend_prerequisite_coaching`·`GET /v1/me/.../coaching`·`/v1/coach(/sessions)`·BKT 커밋 `record_problem_attempt_mastery`|🟢 코칭 결정+커밋(도구 루프 오케스트레이션은 미구현)             |
|9 |`log_strategy_event` |전략    |—                                                                                                       |🔴 `strategy_nodes`·`strategy_evidence` 미구현     |
|10|`elicit_prediction`  |전략    |—                                                                                                       |🔴 보정 루프(Brier·과신/과소신) 미구현                   |
|11|`assign_transfer_probe`|전략  |(자산) 시그니처 패턴 55+108(ROADMAP Phase 1)                                                                    |🔴 전이 측정·간격 출제 미구현                            |

**판독**: 코어 진단·코칭·선수 좌석(#1·#3·#5·#8 일부)은 *이미 가동*하며 이번 세션 소비 아크로 강화됐다. 하네스가 추가하는 건 ① **상태 외부화**(가설 세트·evidence_links·#4·#7) ② **도구 루프 오케스트레이션**(end_turn 도구 루프·#8) ③ **전략 계층**(#9~#11). 즉 WH-1 도입은 *기존 좌석을 도구로 노출 + 상태/루프/전략 신설*이며, 진단·코칭 로직을 새로 짜는 게 아니다.

### 0단계 평가 하네스 — 구현 현황 (2026-06-13, 편집자 부기)

§8.4 0단계의 *대리 지표 베이스라인 좌석*이 **구현됨** — `whymath_backend/harness/wh1_evaluation.py`(`compute_wh1_surrogate_metrics`)·`GET /v1/me/harness-metrics`. **날조 0 원칙**: 계측 가능분만 실값, 미계측은 `value=None` + `MetricStatus`(NOT_INSTRUMENTED·REQUIRES_DATA·REQUIRES_TOOL) + note로 *커버리지 맵*을 낸다(가짜 0 금지). 현 커버리지: **🟢 ① verify 통과율**(검산결과 `attempt_event` 적재→집계·단 binary 검산[거짓 수치관계 *미적발*]·3-state 아님·unverifiable 미구분)·**🟢 ③ 세션 완주율**·**🟡 ④ 턴당 토큰**·**🟡 ⑤ 도움 감소 곡선**(힌트제공 `attempt_event` 적재→hint_level OLS 기울기·음수=도움 감소)·**🟢 ⑤+R15 결합 판정**(`help_reduction_validated` — ⑤ 도움 기울기 × 정답률[`ProblemAttempt.is_correct`] OLS 추세 × **문항 난이도[IRT b] OLS 추세** 3신호 교차: 도움↓·정답률 유지·난이도 유지/↑→`GENUINE_IMPROVEMENT`·도움↓·정답률↓→`GAMING_SUSPECT`[힌트 회피]·**도움↓·정답률 유지·난이도↓→`GAMING_SUSPECT`[쉬운 문제 회피]**·난이도 데이터 부족→2신호 판정+blind spot 캐비엇·표본 부족→`INSUFFICIENT_DATA`·마이그레이션 0)·**🟢 ⑥ 보정 점수(Brier)**(`ProblemAttempt.confidence_self_reported`[0~1 자기보고 확신도=예측·`POST /v1/me/attempts`로 이미 수집] vs `is_correct` → `mean((confidence−is_correct)²)`·낮을수록 잘 보정·유효 쌍<5 NO_DATA) = 계측. **§11.4 보정 루프 코칭 구현**: `l4/calibration_coaching.recommend_calibration_coaching(confidence, is_correct)`(순수 L4) → 틀림+확신≥0.7→`calibration_overconfident`(소크라테스 강화·ASSUMPTION·"어디서 확신했는지 같이 짚어볼까")·맞음+확신≤0.3→`calibration_underconfident`(효능감·META·"잘 풀었어·좀 더 믿어도 돼")·잘 보정→None·`POST /v1/me/attempts` 응답 `calibration_coaching` 필드로 노출(측정⑥→코칭 행동 연결·톤 가드).·**🟡 ② 진단-실제 오개념 일치율(오프라인 진단정확도)**(라벨 프로브 92건[recall 60·FP 32]을 패키지 데이터 `l4/misconception/probes_v1.jsonl`로 단일화→recall 프로브에 substring 매처[`diagnose`] **top-1 recall**[현 11/60=0.18·substring 보수적 기준선]·**LIVE 학생별 ground-truth 아님**[시스템 진단엔진 품질·전 user 동일·user/기간 무관]·precision/FP는 `semantic_eval` 별도) = 계측. **🔴 ⑦** = 미계측(REQUIRES_TOOL). 미계측 실계측은 후속(⑦ 패턴 태깅[전이])·② LIVE per-user(문항-오개념 태깅·attempt별 진단 기록)·② precision/FP 결합·의미 매처(임베딩) recall 격상·보정 종단 추적·학부모 리포트·R15 추가 정밀화·0단계 나머지(verify 커버리지·오개념 audit·Langfuse·PRM 오탐률)도 후속(MEMORY 2026-06-13 참조).
