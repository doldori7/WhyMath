"""교수법 팩 런타임 레지스트리 — 코퍼스 YAML을 인메모리 조회 자산으로(DB-free·1회 로드).

`l4/misconception/catalog.py`의 모듈 수준 동결 `CATALOG`/`CATALOG_BY_ID`(오개념 인메모리
카탈로그)의 *교수법 팩* 짝이다. 차이는 원천이다: 오개념 카탈로그는 코드 리터럴이지만, 교수법 팩은
사람이 저작하는 *데이터*(YAML)라 이 레지스트리가 `data/corpus/pedagogy_packs_v1/*.yaml`(7 지식유형
팩)을 `yaml.safe_load` + `schema.PedagogyPack.model_validate`로 읽어 `k_type` 문자열로 키한다.

특징:
  - **인메모리·DB-free**: `@lru_cache(maxsize=1)`로 첫 호출에만 파일을 읽고 이후는 0ms(catalog.py의
    모듈 수준 동결과 동형 — 조회는 순수). L1 시더(`pack_loader.py`)의 DB 적재와 무관한 별개 좌석.
  - **계층 위생**: `schema`(팩 계약)·`yaml`(로더)만 import — l1(적재 seam)에 의존하지 않는다
    (import-linter의 l4→l1은 허용되나, 이 레지스트리는 영속 계층과 결합하지 않으려 의도적으로
    피한다).
  - **경로 고정**: 레포 루트 기준(`parents[5]`·`compile.py`와 동일 depth)으로 코퍼스 디렉터리를
    앵커해 cwd 무관하게 해석한다(src/backend·레포 루트 어디서 실행하든 동일).

`k_type`은 schema가 `use_enum_values=True`라 검증 후 문자열 값("CONCEPT")이므로 그대로 dict 키가
된다(enum 멤버가 아니라 문자열 — 호출자는 `KnowledgeType.CONCEPT.value` 또는 리터럴로 조회).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

from whymath_backend.schema.pedagogy_pack import PedagogyPack

# 코퍼스 팩 디렉터리 — 레포 루트 기준 고정(cwd 무관). 이 파일은
# src/backend/whymath_backend/l4/pedagogy/pack_registry.py라 parents[5]가 레포 루트다
# (compile.py가 l1/pedagogy/compile.py에서 parents[5]로 같은 루트를 잡는 것과 동일 depth).
_REPO_ROOT = Path(__file__).resolve().parents[5]
_PACKS_DIR = _REPO_ROOT / "data" / "corpus" / "pedagogy_packs_v1"


@lru_cache(maxsize=1)
def get_pedagogy_packs() -> dict[str, PedagogyPack]:
    """7 지식유형 팩 YAML을 검증·적재해 `k_type`(문자열) → `PedagogyPack`으로 반환(1회 로드·캐시).

    `_PACKS_DIR`의 `*.yaml`을 정렬 glob(결정적 순서)해 각각 `yaml.safe_load`(안전 로더·임의 객체
    역직렬화 금지) 후 `PedagogyPack.model_validate`로 검증한다 — 형식·교수학 불변식은 schema가
    게이트하므로 오염 팩은 여기서 `ValidationError`로 떨어진다(정직·조용한 실패 금지). `_provenance.
    json`은 `.yaml`이 아니라 glob에 안 잡힌다(표지 메타 제외). 키는 `use_enum_values=True`로
    문자열이 된 `pack.k_type`이다.

    Raises:
        FileNotFoundError: `_PACKS_DIR`가 없거나 파일 접근 실패(경로 앵커 회귀 — 조용히 삼키지
            않는다).
        pydantic.ValidationError: 어느 팩이 schema 형식·교수학 불변식을 위반(게이트는 schema 몫).
    """
    packs: dict[str, PedagogyPack] = {}
    for path in sorted(_PACKS_DIR.glob("*.yaml")):
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        pack = PedagogyPack.model_validate(raw)
        # k_type은 use_enum_values=True라 문자열 값("CONCEPT") — 그대로 dict 키.
        packs[str(pack.k_type)] = pack
    return packs


def get_pack(k_type: str) -> PedagogyPack | None:
    """`k_type` 문자열로 팩 1건 조회 — 미등록(오탈자·미완성 유형)이면 None(fail-soft 조회).

    조회 실패를 예외로 올리지 않는 이유: 호출자(코치 결정 경로)는 팩이 없으면 base_system 그대로
    쓰는 옵트인 계약이라, None을 "팩 미적용" 신호로 흡수한다(조립기의 `pack=None` 무변경 계약과
    정합).
    `k_type`은 `KnowledgeType` 값 문자열("CONCEPT" 등)을 기대한다.
    """
    return get_pedagogy_packs().get(k_type)


def reset_pack_cache() -> None:
    """레지스트리 캐시 무효화 — 테스트 격리용(코퍼스 교체·경로 변경 후 재로딩).

    `coach_prose_leak_eval`의 `get_settings.cache_clear()`와 동형 — 프로덕션 런타임은 팩이 프로세스
    수명 동안 고정이라 호출할 일이 없다(테스트 전용 seam).
    """
    get_pedagogy_packs.cache_clear()


__all__ = [
    "get_pack",
    "get_pedagogy_packs",
    "reset_pack_cache",
]
