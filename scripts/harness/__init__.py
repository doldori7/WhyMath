"""빌드 하네스(Build Harness) — WhyMath 프로젝트 작업일정 관리·순차 조율 레이어.

주의: src/backend/whymath_backend/harness(WH-1 튜터링)·whs(WH-S 솔버)는
제품 런타임 하네스로 이 패키지와 무관하다. 이 패키지는 저장소의 backlog/를
단일 진실 원천으로 삼아 "다음 할 일"을 계산하는 빌드 관리 도구다.

- models.py   : 태스크·게이트·트랙 데이터 모델 + 검증
- store.py    : backlog/ 로드·저장·이벤트 로그·무결성 검증
- selector.py : 순차 조율 알고리즘 (착수 가능 후보 계산·정렬·정지 사유 판별)
- report.py   : status/brief 렌더링 (SessionStart 훅용 압축 포맷 포함)
- backlog.py  : CLI 엔트리포인트 (python3 scripts/harness/backlog.py <cmd>)
"""
