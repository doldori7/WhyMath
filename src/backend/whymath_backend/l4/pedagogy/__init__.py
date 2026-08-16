"""L4 교수법 팩(pedagogy pack) 런타임 — 4계층 발문 조립·금지모드 가드·인메모리 팩 레지스트리.

PED-01 슬라이스 ③. 이 패키지는 `data/corpus/pedagogy_packs_v1/*.yaml`(7 지식유형 팩)을
*런타임 조회 자산*으로 올려, 지식 유형별 소크라테스 발문 계층(`prompt_assembler`)을 stateless
코치(`PolyaCoach.decide`) 경로에 옵트인·플래그 게이트로 얹는 재사용 기계다. 금지 교수 모드의
집행은 두 좌석으로 갈린다 — *사전* 가드(`runtime_selector`의 교수학 게이트·supply 경로 배선)와
*사후* 문면 가드(`mode_guard.check_forbidden_modes`)다. 사후 가드는 **PED-23(회수)가 런타임
배선을 복원했다** — WH-1 primary 학생-대면 발화 경로(`harness/wh1_primary.py`)의 톤필터 직전,
`mode_guard_runtime_enabled`(기본 False·옵트인 캔어리) ∧ 팩 주입 시에만 fail-closed로 돈다
(coach가 `decide(pack=)`에 넣은 같은 팩 객체를 러너로 thread). 경위: PED-16(2026-08-10)은
"WH-1 루프가 PedagogyPack을 참조하지 않는다"를 근거로 by-design 미배선을 확정했으나, 격리
브랜치의 원 구현(원 PED-07)이 coach→러너 팩 thread로 그 선결 조건을 이미 충족해 뒀고 PED-23이
현행 main 위에 재적용했다. 오프라인 결함주입 측정(`harness/pedagogy_pack_fidelity_eval`·CI 상시)은
불변(근거 전문은 `mode_guard.py` 모듈 docstring, dsl_integration_gap_review §2-⑤).

경계(계층 위생): `pack_registry`는 `schema`(팩 계약)·`yaml`(로더)만 import한다(DB 무접근·순수 파일
로드). `prompt_assembler`는 거기에 더해 l4 형제 타입(`MisconceptionHypothesis`·`MasteryLevel`)을
참조한다(l4→l4 동일 계층·import-linter 무관). 어느 모듈도 l1(적재 seam)에는 의존하지 않는다 — L1
시더(`l1/pedagogy/pack_loader.py`)는 *영속 적재*를, 이 패키지는 *런타임 조회/조립*을 맡는 별개
좌석이다(같은 YAML을 각자 소비·역방향 의존 0).
"""
