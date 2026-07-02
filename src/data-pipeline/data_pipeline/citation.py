"""NCIC 유래 출처 표기(citation) 단일 빌더 — 과목 확장 준비 S2.

정본: `docs/architecture/subject_expansion_readiness.md` §1(하드 지점 목록)·§4.2·§9(invariant).

배경·근거:
  - 2022 개정 각론은 **고시 번호(교육부 고시 제2022-33호)를 전 과목이 공유**하고 별책만
    다르다 — 별책 8 수학과·별책 9 과학과. 따라서 NCIC 유래 출처 표기의 과목 종속부는
    "[<과목> 교육과정]" 라벨 하나뿐이며, **과목 라벨 파라미터만으로 확장이 충분**하다.
  - 종전에는 이 라벨이 3모듈(`ncic/models.py`·`concept_graph/models.py`·`atom_graph/models.py`)
    의 `SOURCE_CITATION`에 하드코딩 산재 — 과학과(별책 9) 확장 시 산재 수정을 유발하므로
    본 빌더로 단일화한다. §9 invariant: 수학과 교육과정 대괄호 라벨 리터럴은 이 파일 밖
    재등장 금지(`standards_university/models.py`는 NCIC 비유래 자체 표기라 제외).
  - **기존 3모듈 `SOURCE_CITATION` 값은 바이트 단위 불변** — 직렬화 산출물·golden 테스트·
    코퍼스가 이 문자열을 담고 있어, 리팩토링은 합성 방식만 바꾸고 값은 바꾸지 않는다.
    동결 테스트: `tests/data_pipeline/test_citation.py`(리팩토링 전 리터럴과 직접 비교).
"""

from __future__ import annotations

from typing import Final

# 2022 개정 각론 공유 고시 번호 — 과목이 달라도 고시 번호는 동일(별책만 상이).
_GOSI_NOTICE: Final[str] = "교육부 고시 제2022-33호"

# NCIC 표기 — 공공누리 제1유형 출처 표시 의무의 기관·URL 부분.
_NCIC_REFERENCE: Final[str] = "국가교육과정정보센터(NCIC, https://www.ncic.go.kr)"


def build_ncic_citation_core(subject_label: str = "수학과") -> str:
    """NCIC 유래 출처 표기의 공통 코어를 합성한다.

    3모듈 `SOURCE_CITATION`의 **최대 공통부**가 이 함수의 반환값이다 — 각 모듈은 용도별
    접두("출처: "·"개념-성취기준 매핑 근거: "·"원자-성취기준 매핑 근거: ")와 접미
    (원자 백본의 자체작성 명시)만 자기 자리에서 래핑한다.

    Args:
        subject_label: 교육과정 과목 라벨. 기본 "수학과"(별책 8).
            과학과 확장 시 "과학과"(별책 9) — 고시 번호는 공유하므로 라벨만 교체하면 된다
            (readiness doc §4.2: 과학과 성취기준 수집 시 이 파라미터가 준비 지점).

    Returns:
        "교육부 고시 제2022-33호 [<과목 라벨> 교육과정], 국가교육과정정보센터(NCIC,
        https://www.ncic.go.kr)" 형식의 문자열.
    """
    return f"{_GOSI_NOTICE} [{subject_label} 교육과정], {_NCIC_REFERENCE}"
