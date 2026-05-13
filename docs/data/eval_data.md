# 평가·기출 데이터 스키마

## 출처

| 출처 | 종류 | 활용 |
|---|---|---|
| 한국교육과정평가원 | 수능·6월모평·9월모평 | 본문·해설 인용 (교육적 인용) |
| EBS | 수능특강·수능완성 | 메타데이터만 (단원·차시) |
| 각 시도교육청 | 내신 기출 | 학교 단위, 동의 시 |

## 데이터 필드

```yaml
exam_type: "수능"  # | "6월모평" | "9월모평" | "EBS수능특강"
year: 2025
subject: "수학"  # | "수학 가형" | "수학 나형" | "미적분" 등
problem_number: 21
problem_text: "..."  # 본문 (교육적 인용 범위)
answer: "5"
solution_outline: "..."  # 자체 작성 풀이 outline
standard_codes:
  - "[12수03-XX]"
kice_topic_code: "..."
difficulty_label: "killer"
techniques:
  - "discriminant"
  - "graph_translation"
estimated_solving_time_minutes: 8
```

## 라이선스 주의

평가원 기출 본문:
- ✅ 교육 목적 인용 (저작권법 인용 조항)
- ✅ 학생에게 *원문 표시* + 해설 *자체 작성*
- ❌ 원문만 모아 *재배포*
- ❌ 본문을 *변형 없이* 상업 데이터셋으로

## 활용 패턴

```
학생: [수능 21번 풀이 도움]
→ L1: 문제 조회 + 성취기준 매핑
→ L4: Polya 코칭 시작
→ L3: *자체 작성* 단계별 안내
→ 학생에게: 원문 + 자체 풀이 outline 표시
```
