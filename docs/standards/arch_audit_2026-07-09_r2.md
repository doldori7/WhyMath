# 아키텍처 감사 2회차 (ARCH-02) — 1회차 지적 이행·신규 코드 3커밋 점검·E축 사전 점검

> **감사일**: 2026-07-09 (1회차 `arch_audit_2026-07-09.md` 이후 커밋 f0d3443·f0faa17·d0805cc·6f36ab0 반영분)
> **태스크**: `backlog/tasks/ARCH-02-playbook-audit.yaml` | **방법**: 게이트 재실행 + 신규 코드 실측
> **한 줄 결론**: 1회차 갭 A **상환 완료·게이트 가동 확인**. 신규 코드 3커밋(S2-06·S2-03) 전부 플레이북 불변식 준수. 신규 위반 0건 — 상환 태스크 추가 없음.

---

## 1. 1회차 지적 이행 판정

### [갭 A] 클라이언트 무-수학로직 CI 게이트 — ✅ 상환 완료·가동 확인
- **이행(ARCH-10, 커밋 f0d3443)**: 게이트 2종 신설 — Flutter 소스 전수 스캔(`no_math_logic_governance_test.dart`) + 웹 화이트리스트 동결(`no_math_judgement_governance.test.js`).
- **2회차 재검증 실측**: 웹 게이트 `3 passed` 재실행 green / Flutter 스캔 시뮬레이션 lib 43파일 위반 0건. 1회차 red 검증(위반 파일 유입 시 2 failed)은 이행 시 실측 완료.
- **파생**: QuizMode 기존 위반은 화이트리스트 2건으로 봉인, 존치/리팩터 결정은 `ARCH-12`(owner: kiki) 대기 — 정상 추적 중.

### [유예 B] Minimal Subgraph depth≤2 가드 — ⏸ 유예 유지 (트리거 미도래)
- `ARCH-11-subgraph-depth-guard`가 `S1-11-coach-harness-converge`(해제 트리거 = WH-1 traversal 소비처 착륙)에 의존성으로 걸려 백로그 추적 중. S1-11은 `G-phaiakes9-key`(Kiki, 4일 경과) 대기. **사람 기억 의존 제거 목적 달성 — 조치 불요.**

### [정비] 스냅샷 stale — ✅ 1회차에서 갱신 완료, 본 회차에서 갭 A 해소 반영 추가 갱신.

## 2. 신규 코드 3커밋 불변식 점검 (1회차 이후 착륙분)

| 커밋 | 내용 | 점검 결과 |
|---|---|---|
| f0faa17 (S2-06 1/2) | 시그니처 태거·귀납 수열 밴드 | ✅ 비날조 원칙 준수(기존 1,073문 태깅 0 유지·구조 필드 유도만), 결정론 봉인(2회 바이트 동일), 태거 단일 권위 |
| d0805cc (S2-06 2/2) | 수능 적응 추천 루프 | ✅ l6→l2 하향 import만(lint-imports KEPT 재확인), 순수·I/O 0 관례 유지, 부적격 제외 방식(오추천 구조 차단), **subject 하드코딩 분기 0건 실측** (E축 루프 과목중립) |
| 6f36ab0 (S2-03) | problem_concept 원자 재연결 | ✅ 스키마 0·신규 테이블 0(anti-explosion)·mastery rekey 0·legacy_snapshot 화이트리스트 **의식적 등재**(테스트 안내문 준수·빌드타임 다리 소비 사유 주석 — 재가) · 거버넌스 6종 신설로 감시망 확장 (18→상회) |

- 금지 관계 토큰(similar_to/related_to) 유입: 신규 5모듈 전수 0건.
- 거버넌스 재실행: legacy_snapshot·edge_relation·embedding_namespace·relink 4종 31 passed.

## 3. 입도 통합(437↔2,697)·Part 7 진척

- **입도 통합**: 진척 없음 — 정상 (전문가 검수 소관, `G-domain-partner` 게이트 4일 경과 대기). 감사 조치 불요, 게이트 리마인드가 추적.
- **Part 7 9블록 잔여**(학생모델 축·인터랙션 다양성·경우분할 트리·AssessmentBlock): 변경 없음 — part7 review 기존 상환 계획 유효.

## 4. E축 불변식 4종 사전 점검 (e_axis_v1 §5 — S5 게이트 대비)

| 불변식 | 현황 | 근거 |
|---|---|---|
| ① 루프 과목 중립 | 🟢 유지 | 신규 코드 subject 분기 0건 실측. 수능 모드는 L6 오버레이(모드≠과목) — `Subject` enum 무접촉 |
| ② 검증기 plugin | 🟢 준비 | 3-tier 스택 유지, E1 `dimensional_consistency`는 형제 primitive로 설계 확정(E1-01 태스크 대기) |
| ③ 지표 중립 | 🟡 관찰 | WH-1 평가 지표는 과목 중립 설계이나 실측은 라이브 후 — S5 판정 시 재검 |
| ④ 커리큘럼 오버레이 | 🟡 진행 | S2-03으로 문제 태깅이 원자 축 정착. curriculum_entry 원자 이관은 `S2-07` 등록됨 — 이관 완료가 이 불변식의 남은 조각 |

## 5. 다음 회차(ARCH-03) 초점

1. S2-07(curriculum_entry 원자 이관) 이행 확인 — E축 불변식 ④의 완결 조건
2. ARCH-12(QuizMode 결정) 처리 여부 — 화이트리스트 축소 방향 확인
3. Phaiakes9 라이브 개통 시: WH-1 라이브 경로에서 검증 게이트·비용 가드 실측 (S1 라이브 선행분 착륙 후)
4. 입도 통합 — 도메인 파트너 게이트 해소 여부와 연동
