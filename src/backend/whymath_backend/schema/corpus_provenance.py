"""코퍼스 사이드카(`_provenance.json`) 계약 — ARCH-20
(`docs/architecture/operations_module_gap_review.md` §3 D1).

배경
----
`data/corpus/*/_provenance.json`은 2026-05부터 24개 코퍼스가 각자 자유형으로 써 온
서지·저작권 메타데이터다(`docs/legal/copyright_gradient.md` §3.1 "구조 메타데이터만"의
실무 구현). 실측(2026-07-29) 결과 코퍼스마다 키 집합이 크게 다르다 — 그래프 계열은
`source_citation`만, 오개념 크로스링크는 `license_notice`만, 문제은행 계열은 둘 다.
`corpus_name`조차 3/19 코퍼스에만 있다. 이 이질성은 *결함*이 아니다 — 각 코퍼스의 생성
파이프라인·검수 이력이 다르고, 이미 검수 완결된 서술(예: `misconception_crosslinks_v1`의
`signatures[].reviewer/reviewed_on`)을 단일 스키마에 맞추려 재작성하면 감사 이력이
훼손된다. 그래서 이 계약은 **기존 자유형을 갈아엎지 않고 최소 공통분모만 강제**한다
(extra="allow" — `ContentProvenance`의 `extra="forbid"`와 의도적으로 다른 정책).

강제하는 것 (딱 이 둘)
---------------------
1. `pool` — `copyright_gradient.md` §4.2가 명령한 콘텐츠 풀 분리 필드. 이전엔 전무했다
   (전수 grep 무일치, ARCH-20 실측). 값은 `ContentPool`(3종 폐쇄) 중 하나.
2. **서지 정보 최소 1건** — `source_citation` 또는 `license_notice` 중 하나 이상 non-empty.
   "이 콘텐츠가 어디서 왔는지 한 마디도 안 쓴 사이드카"만 걸러낸다. 19개 실 사이드카 중
   18개는 이미 최소 하나를 갖고 있었다(legacy_snapshot 격하 코퍼스 1건만 예외 —
   ARCH-20에서 1줄 추가).

강제하지 않는 것
---------------
`corpus_name`·`record_count`·`generated`·`copyright_rail`·`contract`·`authoring_fields`
등 — 코퍼스별 자유 서술. `extra="allow"`이므로 무엇을 더 써도 거부되지 않는다.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from whymath_backend.schema.enums import ContentPool

__all__ = ["CorpusProvenanceSidecar"]


class CorpusProvenanceSidecar(BaseModel):
    """`_provenance.json` 최소 계약 — `pool` + 서지 정보 ≥1건.

    `model_validate_json`으로 사이드카 원문을 그대로 검증한다(`ops.provenance_audit`가
    유일한 소비처). 나머지 자유 필드는 그대로 통과(`extra="allow"`) — round-trip 손실 없음.
    """

    model_config = ConfigDict(extra="allow", str_strip_whitespace=True)

    pool: ContentPool = Field(
        description="콘텐츠 풀 분리 태그(copyright_gradient.md §4.2) — 폐쇄 3종."
    )
    source_citation: str | None = Field(default=None, description="출처 서술(자유형).")
    license_notice: str | None = Field(default=None, description="라이선스 고지(자유형).")

    @model_validator(mode="after")
    def _require_at_least_one_bibliographic_field(self) -> "CorpusProvenanceSidecar":
        has_citation = bool(self.source_citation and self.source_citation.strip())
        has_notice = bool(self.license_notice and self.license_notice.strip())
        if not (has_citation or has_notice):
            raise ValueError(
                "source_citation·license_notice 둘 다 비어 있다 — 서지 정보 최소 1건 필수"
                "(이 콘텐츠가 어디서 왔는지 한 마디도 없는 사이드카는 감사 불가)."
            )
        return self
