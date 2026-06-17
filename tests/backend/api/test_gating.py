"""L6 게이팅 API 라우터 단위테스트 — FakeSession 주입(라이브 PG 없음, hermetic).

problems 라우터 단위테스트(test_problems.py)와 동형: `app.dependency_overrides[get_session]`로
가짜 세션을 주입하고 `TestClient(create_app(...))`로 `/v1/gating/*` 3 엔드포인트를 호출해
게이팅 결과(선별·우선순위·limit·저작권/페르소나 차단)를 검증한다. 실 PG 불요·순수 단위.

가짜 세션의 `execute()`는 라우터가 `select(Problem)`으로 만든 stmt를 *무시*하고(사전 SQL
필터가 없으므로 stmt 내용이 결과를 바꾸지 않는다 — 게이팅이 진실 게이트) 미리 정한 ORM
`Problem` 목록을 돌려준다(test_problems.py의 `_FakeResult`/`_FakeScalars` 패턴). 라우터는 각
행을 `to_schema()`로 변환해 L6 게이팅에 넘기므로, 가짜 행은 `Problem.from_schema(...)`로 만든
*진짜 ORM 인스턴스*다(to_schema가 동작해야 함).

검증 초점:
  - retake: persona=B에 자체생성 RT 문항 노출 · 평가원(본문 미보유) 출처 차단 · limit 적용.
  - suneung: persona=A에 정시 신호(exam_type/시그니처) 문항 노출 · 평가원 본문 차단.
  - school-progress: `?unit_codes=X&unit_codes=Y` 단원 정합 노출 · curriculum_version 불일치
    차단 · target 미지정 시 persona_fit 폴백.
  - 잘못된 persona 값(enum 밖) → 422.

레이어(CLAUDE.md): 테스트는 L1(`db.models.problem`·`schema.*`)·L5(`app`·`api.gating` 경유)만
건드린다. L6 게이팅은 라우터를 통해 *간접* 호출한다(게이팅 로직 자체는 l6 단위테스트가 검증).
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Any

from fastapi.testclient import TestClient

from whymath_backend.app import create_app
from whymath_backend.db.models.problem import Problem
from whymath_backend.db.session import get_session
from whymath_backend.schema.enums import (
    BloomLevel,
    Curriculum,
    ExamType,
    Persona,
    QuestionFormat,
    SignaturePattern,
    SourceType,
    Subject,
)
from whymath_backend.schema.problem import Problem as ProblemSchema


# ──────────────────────────────────────────────────────────────────────
# 픽스처 빌더 — 자체생성 최소 Problem(ORM)에서 게이팅 신호만 오버라이드
# ──────────────────────────────────────────────────────────────────────
def _problem(**over: object) -> Problem:
    """게이팅 후보로 쓸 ORM `Problem` 빌더(합성 픽스처).

    기본은 `source_type=자체생성`(저작권 노출 게이트를 통과하는 출처)이라 게이팅 신호만
    오버라이드하면 적격/부적격을 자유로이 만든다. 본문 미보유 출처(평가원/EBS/교과서)는
    `source_type=...`로 바꿔 저작권 게이트를 시험한다. schema.Problem을 거쳐(불변식 검증)
    `from_schema`로 ORM을 만들므로, 라우터의 `to_schema()` 왕복이 그대로 동작한다.
    (l6 단위테스트 `_problem` 빌더와 동일한 필드 셋·type: ignore도 동일.)
    """
    kwargs: dict[str, object] = {
        "source_type": SourceType.자체생성,
        "curriculum_version": Curriculum.REVISION_2022,
        "valid_from_year": 2022,
        "subject": Subject.미적분,
        "unit_codes": ["CAL-INT-DEF"],
    }
    kwargs.update(over)
    return Problem.from_schema(ProblemSchema(**kwargs))  # type: ignore[arg-type]


# ──────────────────────────────────────────────────────────────────────
# 가짜 세션 — execute()가 stmt를 무시하고 정한 ORM 행을 돌려줌(test_problems.py 패턴)
# ──────────────────────────────────────────────────────────────────────
class _FakeScalars:
    def __init__(self, rows: list[Problem]) -> None:
        self._rows = rows

    def all(self) -> list[Problem]:
        return list(self._rows)


class _FakeResult:
    def __init__(self, rows: list[Problem]) -> None:
        self._rows = rows

    def scalars(self) -> _FakeScalars:
        return _FakeScalars(self._rows)


class FakeSession:
    """AsyncSession 표면 일부 모사 — 게이팅 라우터가 부르는 `execute`만(stmt 무시).

    라우터는 사전 SQL 필터 없이 `select(Problem)`만 만들고 게이팅이 모두 거르므로, 가짜
    세션은 stmt 내용과 무관하게 보유한 후보 행(`rows`)을 통째로 돌려준다 — 그러면 *저작권/
    페르소나/진도 차단이 SQL이 아니라 게이팅에서* 일어남이 테스트로 입증된다(차단된 문항을
    가짜 세션이 *그대로 흘려보내도* 응답엔 없어야 한다).
    """

    def __init__(self, rows: list[Problem] | None = None) -> None:
        self._rows = list(rows or [])

    async def execute(self, stmt: Any) -> _FakeResult:
        return _FakeResult(self._rows)


def _client(rows: list[Problem]) -> TestClient:
    """후보 행을 보유한 가짜 세션을 `get_session`에 주입한 TestClient."""
    app = create_app()

    async def _override() -> AsyncIterator[FakeSession]:
        yield FakeSession(rows)

    app.dependency_overrides[get_session] = _override
    return TestClient(app)


def _slugs(payload: list[dict[str, Any]]) -> list[str | None]:
    """응답 본문(list[ProblemSchema])에서 slug 순서를 뽑아 비교용 리스트로."""
    return [item["slug"] for item in payload]


def _source_types(payload: list[dict[str, Any]]) -> set[str]:
    """응답 본문에서 등장한 source_type 집합(본문 미보유 출처 부재 검증용)."""
    return {item["source_type"] for item in payload}


# ──────────────────────────────────────────────────────────────────────
# GET /v1/gating/retake
# ──────────────────────────────────────────────────────────────────────
class TestRetake:
    def test_persona_b_sees_self_generated_rt_items(self) -> None:
        """persona=B(자사고N수) → 자체생성 RT 문항이 노출된다."""
        rt = _problem(slug="rt-fit", question_format=QuestionFormat.재수전용형)
        client = _client([rt])
        resp = client.get("/v1/gating/retake", params={"persona": "B_자사고N수"})
        assert resp.status_code == 200, resp.text
        assert _slugs(resp.json()) == ["rt-fit"]

    def test_persona_required(self) -> None:
        """persona는 필수 쿼리 — 누락 시 422."""
        resp = _client([]).get("/v1/gating/retake")
        assert resp.status_code == 422

    def test_pyeonggawon_body_source_blocked(self) -> None:
        """저작권 게이트 — 평가원(본문 미보유) 출처는 RT 신호가 있어도 응답에서 차단.

        가짜 세션은 차단 대상(평가원)을 그대로 흘려보내지만, 게이팅이 거르므로 응답엔
        자체생성만 남는다 → SQL이 아니라 게이팅이 진실 게이트임이 입증된다.
        """
        ok = _problem(slug="ok", question_format=QuestionFormat.재수전용형)
        # 평가원 출처(본문 미보유) — RT 라벨이 있어도 노출 불가. 본문 필드는 비워 둬야
        # schema.Problem 검증을 통과하므로 빌더 기본(본문 None)을 그대로 쓴다.
        blocked = _problem(
            slug="pyeonggawon",
            source_type=SourceType.평가원,
            question_format=QuestionFormat.재수전용형,
        )
        client = _client([blocked, ok])
        resp = client.get("/v1/gating/retake", params={"persona": "B_자사고N수"})
        assert resp.status_code == 200
        payload = resp.json()
        assert _slugs(payload) == ["ok"]
        # 평가원이 응답 어디에도 없어야 한다(본문 미보유 출처 노출 금지).
        assert "평가원" not in _source_types(payload)

    def test_limit_truncates(self) -> None:
        """limit이 상위 N개로 자른다(게이팅 우선순위 상위부터)."""
        rows = [
            _problem(
                slug=f"item-{i}",
                question_format=QuestionFormat.재수전용형,
                difficulty_overall=float(i),
            )
            for i in (1, 2, 3, 4, 5)
        ]
        client = _client(rows)
        resp = client.get("/v1/gating/retake", params={"persona": "B_자사고N수", "limit": 2})
        assert resp.status_code == 200
        # 난이도 5,4가 상위 2개(재수전용형 1.5 + 난이도).
        assert _slugs(resp.json()) == ["item-5", "item-4"]

    def test_non_target_persona_returns_empty(self) -> None:
        """비대상 페르소나(A) → 적합 문항이 있어도 게이팅이 전부 거른다(빈 배열)."""
        rt = _problem(
            slug="rt",
            question_format=QuestionFormat.재수전용형,
            persona_fit={Persona.A_일반고고3: 0.9},
        )
        resp = _client([rt]).get("/v1/gating/retake", params={"persona": "A_일반고고3"})
        assert resp.status_code == 200
        assert resp.json() == []

    def test_invalid_persona_returns_422(self) -> None:
        """enum 밖 persona 값 → 422."""
        resp = _client([]).get("/v1/gating/retake", params={"persona": "Z_없는페르소나"})
        assert resp.status_code == 422

    def test_empty_candidates_returns_empty(self) -> None:
        """후보가 없으면 빈 배열(200)."""
        resp = _client([]).get("/v1/gating/retake", params={"persona": "B_자사고N수"})
        assert resp.status_code == 200
        assert resp.json() == []


# ──────────────────────────────────────────────────────────────────────
# GET /v1/gating/suneung
# ──────────────────────────────────────────────────────────────────────
class TestSuneung:
    def test_persona_a_sees_exam_signal_item(self) -> None:
        """persona=A(기본) → 정시 신호(exam_type=수능) 자체생성 문항이 노출된다."""
        item = _problem(slug="suneung-exam", exam_type=ExamType.수능)
        resp = _client([item]).get("/v1/gating/suneung")  # persona 기본 A
        assert resp.status_code == 200, resp.text
        assert _slugs(resp.json()) == ["suneung-exam"]

    def test_persona_a_sees_signature_pattern_item(self) -> None:
        """시그니처 패턴 보유 문항도 정시 적합 신호로 노출된다(persona=A 명시)."""
        item = _problem(
            slug="sig",
            signature_patterns=[SignaturePattern.COMPOUND_CHOICES],
        )
        resp = _client([item]).get("/v1/gating/suneung", params={"persona": "A_일반고고3"})
        assert resp.status_code == 200
        assert _slugs(resp.json()) == ["sig"]

    def test_pyeonggawon_body_source_blocked(self) -> None:
        """수능 모드 핵심 — 평가원 기출 *본문*은 응답에서 원천 차단(자체생성만 노출)."""
        ok = _problem(slug="own", exam_type=ExamType.수능)
        # 평가원 출처(본문 미보유) — exam_type=수능 신호가 있어도 노출 불가.
        blocked = _problem(
            slug="pyeonggawon",
            source_type=SourceType.평가원,
            exam_type=ExamType.수능,
        )
        resp = _client([blocked, ok]).get("/v1/gating/suneung")
        assert resp.status_code == 200
        payload = resp.json()
        assert _slugs(payload) == ["own"]
        assert "평가원" not in _source_types(payload)

    def test_priority_orders_by_authority(self) -> None:
        """출처 권위(exam_authority_weight)가 높은 문항이 앞에 온다(게이팅 우선순위)."""
        suneung = _problem(slug="suneung", exam_type=ExamType.수능, exam_authority_weight=1.0)
        hakpyeong = _problem(slug="hakpyeong", exam_type=ExamType.학평, exam_authority_weight=0.5)
        # 입력은 역순으로 줘서 정렬이 실제로 일어나는지 본다.
        resp = _client([hakpyeong, suneung]).get("/v1/gating/suneung")
        assert resp.status_code == 200
        assert _slugs(resp.json()) == ["suneung", "hakpyeong"]

    def test_non_target_persona_d_returns_empty(self) -> None:
        """D(학종·수시)는 정시 모드 비대상 → 게이팅이 거른다(빈 배열)."""
        item = _problem(slug="x", exam_type=ExamType.수능)
        resp = _client([item]).get("/v1/gating/suneung", params={"persona": "D_학종고2"})
        assert resp.status_code == 200
        assert resp.json() == []

    def test_invalid_persona_returns_422(self) -> None:
        """enum 밖 persona 값 → 422."""
        resp = _client([]).get("/v1/gating/suneung", params={"persona": "nope"})
        assert resp.status_code == 422


# ──────────────────────────────────────────────────────────────────────
# GET /v1/gating/school-progress
# ──────────────────────────────────────────────────────────────────────
class TestSchoolProgress:
    def test_unit_code_overlap_exposes_matching_item(self) -> None:
        """`?unit_codes=X&unit_codes=Y` → 진도 단원과 겹치는 문항만 노출(단원 정합)."""
        match = _problem(slug="match", unit_codes=["CAL-INT-DEF", "FUN-COMPOSITE"])
        # 진도 단원과 전혀 안 겹치는 문항 → 게이팅이 진도 부정합으로 탈락.
        miss = _problem(slug="miss", unit_codes=["GEO-CIRCLE"])
        client = _client([miss, match])
        resp = client.get(
            "/v1/gating/school-progress",
            params={
                "persona": "A_일반고고3",
                "unit_codes": ["CAL-INT-DEF", "PROB-COND"],
            },
        )
        assert resp.status_code == 200, resp.text
        assert _slugs(resp.json()) == ["match"]

    def test_curriculum_mismatch_blocked(self) -> None:
        """curriculum_version 불일치 → 게이팅이 차단(2022 진도에 2015 문항 미혼입)."""
        item_2015 = _problem(
            slug="old",
            curriculum_version=Curriculum.REVISION_2015,
            unit_codes=["CAL-INT-DEF"],
        )
        client = _client([item_2015])
        resp = client.get(
            "/v1/gating/school-progress",
            params={
                "persona": "A_일반고고3",
                "unit_codes": ["CAL-INT-DEF"],
                "curriculum_version": "2022_REVISION",
            },
        )
        assert resp.status_code == 200
        assert resp.json() == []  # 교육과정 불일치로 차단

    def test_curriculum_match_passes(self) -> None:
        """curriculum_version 일치 + 단원 겹침 → 노출(정합 통과)."""
        item = _problem(
            slug="ok",
            curriculum_version=Curriculum.REVISION_2022,
            unit_codes=["CAL-INT-DEF"],
        )
        resp = _client([item]).get(
            "/v1/gating/school-progress",
            params={
                "persona": "A_일반고고3",
                "unit_codes": ["CAL-INT-DEF"],
                "curriculum_version": "2022_REVISION",
            },
        )
        assert resp.status_code == 200
        assert _slugs(resp.json()) == ["ok"]

    def test_no_target_units_falls_back_to_persona_fit(self) -> None:
        """target 미지정 → persona_fit 폴백으로 판정(진도 단원 정보 부재 시)."""
        fit = _problem(slug="fit", persona_fit={Persona.A_일반고고3: 0.8})
        nofit = _problem(slug="nofit", persona_fit={Persona.A_일반고고3: 0.2})
        client = _client([nofit, fit])
        # unit_codes 미지정 → persona_fit >= 0.5인 'fit'만 통과.
        resp = client.get("/v1/gating/school-progress", params={"persona": "A_일반고고3"})
        assert resp.status_code == 200
        assert _slugs(resp.json()) == ["fit"]

    def test_pyeonggawon_body_source_blocked(self) -> None:
        """저작권 게이트 — 평가원(본문 미보유) 출처는 진도 정합이어도 응답에서 차단."""
        ok = _problem(slug="ok", unit_codes=["CAL-INT-DEF"])
        blocked = _problem(
            slug="pyeonggawon",
            source_type=SourceType.평가원,
            unit_codes=["CAL-INT-DEF"],
        )
        resp = _client([blocked, ok]).get(
            "/v1/gating/school-progress",
            params={"persona": "A_일반고고3", "unit_codes": ["CAL-INT-DEF"]},
        )
        assert resp.status_code == 200
        payload = resp.json()
        assert _slugs(payload) == ["ok"]
        assert "평가원" not in _source_types(payload)

    def test_priority_orders_by_overlap_count(self) -> None:
        """진도 단원 *겹침 개수*가 많은 문항이 앞에 온다(게이팅 우선순위)."""
        two = _problem(slug="two", unit_codes=["CAL-INT-DEF", "FUN-COMPOSITE"])
        one = _problem(slug="one", unit_codes=["CAL-INT-DEF"])
        # 입력은 역순으로 줘서 정렬이 일어나는지 본다. 진도에 두 단원 모두 포함.
        client = _client([one, two])
        resp = client.get(
            "/v1/gating/school-progress",
            params={
                "persona": "A_일반고고3",
                "unit_codes": ["CAL-INT-DEF", "FUN-COMPOSITE"],
            },
        )
        assert resp.status_code == 200
        assert _slugs(resp.json()) == ["two", "one"]

    def test_non_target_persona_b_returns_empty(self) -> None:
        """N수(B)는 비재학 → 학교진도 비대상 → 게이팅이 거른다(빈 배열)."""
        item = _problem(slug="x", unit_codes=["CAL-INT-DEF"])
        resp = _client([item]).get(
            "/v1/gating/school-progress",
            params={"persona": "B_자사고N수", "unit_codes": ["CAL-INT-DEF"]},
        )
        assert resp.status_code == 200
        assert resp.json() == []

    def test_invalid_persona_returns_422(self) -> None:
        """enum 밖 persona 값 → 422."""
        resp = _client([]).get("/v1/gating/school-progress", params={"persona": "bad"})
        assert resp.status_code == 422

    def test_invalid_curriculum_returns_422(self) -> None:
        """enum 밖 curriculum_version 값 → 422."""
        resp = _client([]).get(
            "/v1/gating/school-progress",
            params={"persona": "A_일반고고3", "curriculum_version": "9999_REVISION"},
        )
        assert resp.status_code == 422


# ──────────────────────────────────────────────────────────────────────
# GET /v1/gating/thinking
# ──────────────────────────────────────────────────────────────────────
class TestThinking:
    def test_persona_d_sees_top_bloom_item(self) -> None:
        """persona=D(기본) → Bloom 상위 단계(CREATE) 자체생성 문항이 노출된다."""
        item = _problem(
            slug="thinking",
            bloom_level=BloomLevel.CREATE,
            persona_fit={Persona.D_학종고2: 0.9},
        )
        resp = _client([item]).get("/v1/gating/thinking")  # persona 기본 D
        assert resp.status_code == 200, resp.text
        assert _slugs(resp.json()) == ["thinking"]

    def test_lower_bloom_item_not_exposed(self) -> None:
        """하위 인지 수준(APPLY) 문항은 사고력 주신호가 아니라 게이팅이 거른다(빈 배열)."""
        item = _problem(
            slug="apply",
            bloom_level=BloomLevel.APPLY,
            persona_fit={Persona.D_학종고2: 0.9},
        )
        resp = _client([item]).get("/v1/gating/thinking")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_pyeonggawon_body_source_blocked(self) -> None:
        """저작권 게이트 — 평가원(본문 미보유) 출처는 최상위 bloom이어도 응답에서 차단."""
        ok = _problem(
            slug="own",
            bloom_level=BloomLevel.CREATE,
            persona_fit={Persona.D_학종고2: 0.9},
        )
        # 평가원 출처(본문 미보유) — CREATE 신호가 있어도 노출 불가.
        blocked = _problem(
            slug="pyeonggawon",
            source_type=SourceType.평가원,
            bloom_level=BloomLevel.CREATE,
            persona_fit={Persona.D_학종고2: 0.9},
        )
        resp = _client([blocked, ok]).get("/v1/gating/thinking")
        assert resp.status_code == 200
        payload = resp.json()
        assert _slugs(payload) == ["own"]
        assert "평가원" not in _source_types(payload)

    def test_priority_orders_by_bloom_level(self) -> None:
        """Bloom 상위 단계(CREATE>EVALUATE)가 앞에 온다(게이팅 우선순위)."""
        create = _problem(
            slug="create",
            bloom_level=BloomLevel.CREATE,
            persona_fit={Persona.D_학종고2: 0.9},
        )
        evaluate = _problem(
            slug="evaluate",
            bloom_level=BloomLevel.EVALUATE,
            persona_fit={Persona.D_학종고2: 0.9},
        )
        # 입력은 역순으로 줘서 정렬이 실제로 일어나는지 본다.
        resp = _client([evaluate, create]).get("/v1/gating/thinking")
        assert resp.status_code == 200
        assert _slugs(resp.json()) == ["create", "evaluate"]

    def test_mvp_persona_a_sees_thinking_item(self) -> None:
        """A(MVP 고3)도 적합도 충족이면 사고력 문항이 노출된다(닫힌 집합 게이트 없음)."""
        item = _problem(
            slug="a-thinking",
            bloom_level=BloomLevel.EVALUATE,
            persona_fit={Persona.A_일반고고3: 0.8},
        )
        resp = _client([item]).get("/v1/gating/thinking", params={"persona": "A_일반고고3"})
        assert resp.status_code == 200
        assert _slugs(resp.json()) == ["a-thinking"]

    def test_persona_without_fit_returns_empty(self) -> None:
        """조회 페르소나의 적합도가 없으면 상위 bloom이어도 게이팅이 거른다(빈 배열)."""
        item = _problem(
            slug="x",
            bloom_level=BloomLevel.CREATE,
            persona_fit={Persona.E_홈스쿨링영재: 0.9},  # 조회 대상 A는 없음
        )
        resp = _client([item]).get("/v1/gating/thinking", params={"persona": "A_일반고고3"})
        assert resp.status_code == 200
        assert resp.json() == []

    def test_invalid_persona_returns_422(self) -> None:
        """enum 밖 persona 값 → 422."""
        resp = _client([]).get("/v1/gating/thinking", params={"persona": "nope"})
        assert resp.status_code == 422


# ──────────────────────────────────────────────────────────────────────
# 공통 — limit 범위 검증
# ──────────────────────────────────────────────────────────────────────
class TestLimitValidation:
    def test_limit_out_of_range_returns_422(self) -> None:
        """limit은 1~200 범위 — 벗어나면 422(problems.py 페이지네이션과 동형)."""
        client = _client([])
        assert (
            client.get(
                "/v1/gating/retake", params={"persona": "B_자사고N수", "limit": 0}
            ).status_code
            == 422
        )
        assert (
            client.get(
                "/v1/gating/retake", params={"persona": "B_자사고N수", "limit": 999}
            ).status_code
            == 422
        )


def test_problem_id_in_response_is_uuid_string() -> None:
    """게이팅 응답이 정상 ProblemSchema 직렬화(problem_id가 UUID 문자열)인지 확인."""
    item = _problem(slug="rt", question_format=QuestionFormat.재수전용형)
    resp = _client([item]).get("/v1/gating/retake", params={"persona": "B_자사고N수"})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    # problem_id가 유효한 UUID 문자열이어야 한다(schema 직렬화 정상).
    uuid.UUID(body[0]["problem_id"])
