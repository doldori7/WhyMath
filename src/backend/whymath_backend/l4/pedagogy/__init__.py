"""L4 교수법 팩(pedagogy pack) 런타임 — 4계층 발문 조립·금지모드 가드·인메모리 팩 레지스트리.

PED-01 슬라이스 ③. 이 패키지는 `data/corpus/pedagogy_packs_v1/*.yaml`(7 지식유형 팩)을
*런타임 조회 자산*으로 올려, 지식 유형별 소크라테스 발문 계층(`prompt_assembler`)과 금지 교수
모드 가드(`mode_guard`)를 stateless 코치(`PolyaCoach.decide`) 경로에 옵트인·플래그 게이트로
얹는 재사용 기계다.

경계(계층 위생): `pack_registry`는 `schema`(팩 계약)·`yaml`(로더)만 import한다(DB 무접근·순수 파일
로드). `prompt_assembler`는 거기에 더해 l4 형제 타입(`MisconceptionHypothesis`·`MasteryLevel`)을
참조한다(l4→l4 동일 계층·import-linter 무관). 어느 모듈도 l1(적재 seam)에는 의존하지 않는다 — L1
시더(`l1/pedagogy/pack_loader.py`)는 *영속 적재*를, 이 패키지는 *런타임 조회/조립*을 맡는 별개
좌석이다(같은 YAML을 각자 소비·역방향 의존 0).

PED-05 추가: `strategy_registry`(교수전략 카탈로그 레지스트리 — `pedagogy_strategies_v1/*.yaml`
10종·enum 1:1·pack_registry 미러·DB-free). 소비 배선(select 후보 필터·전략 카드)은 PED-06 소관.
"""
