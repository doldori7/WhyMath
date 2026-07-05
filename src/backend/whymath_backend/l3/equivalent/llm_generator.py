"""실 LLM 동등문제 생성기 — S2-e(프로덕션 `EquivalentProblemGenerator` 구현).

S2-d 오케스트레이터(`orchestrator.run_equivalent_generation`)의 stub 생성기
(`generator.ScriptedGenerator`)를 대체하는 *프로덕션 LLM 생성기*다. `EquivalenceSpec`을
받아 실 LLM(Phaiakes9 로컬 Qwen3-Math·라우터 경유)으로 *자체생성 동등문제 후보*를 만들어
`CandidateProblem`으로 조립한다. 오케스트레이터는 이 후보를 *신뢰하지 않고* S2-a 게이트
(`evaluate_equivalent_candidate`)로 검증한 뒤에야 저장한다(좌석 계약 동형·재구현 0).

선례(S1-a `harness/wh1_llm_policy.py::LLMTutorPolicy`)를 정확히 미러한다:
  - **provider 주입**: `LLMProvider | None`(None이면 표준 `CompositeProvider` 구성·지연 연결).
    이 환경(클라우드)엔 Ollama·키가 없어 **FakeProvider로 hermetic 검증**하고, Kiki가 Phaiakes9
    에서 실 Ollama provider를 주입해 라이브 구동한다(mock→live 동형·아래 라이브 핸드오프 참조).
  - **라우터 경유**(CLAUDE.md "LLM 호출은 항상 라우터 경유·직접 호출 금지"): `Router().route()`가
    비용·크기를 결정하고 `provider.generate(prompt, system, decision)`로 위임한다.
  - **JSON 관대 파싱**(`_extract_json` 미러·코드펜스/주변 산문 허용).
  - **안전 폴백**(조용한 크래시 금지): 파싱 실패·필수 필드 결측·미지 오개념·provider 예외·
    Problem/Provenance 생성 불변식 위반(저작권 게이트가 생성 거부)은 *전부* `None` 반환 +
    로그. 오케스트레이터가 이를 `generation_failed`로 정직히 기록한다.

**저작권 이중(삼중) 방어** — CLAUDE.md 최우선 금기("검정 교과서·평가원·EBS 본문 복제 절대 금지"):
  ① **프롬프트 지시**: 시스템 프롬프트가 "평가원·EBS·교과서 본문·기출을 절대 복제·재현 금지·
     순수 자작 수식 문제만"을 명령한다.
  ② **코드 강제(구조적)**: LLM 출력의 출처 주장을 *읽지 않고* `Problem.source_type=자체생성`·
     `ContentProvenance.license=WHYMATH_GENERATED`·`generation_type=FULLY_GENERATED`·
     `original_source=None`(본문성 키 0)을 **무조건 박는다**. LLM이 응답에 "평가원 …"이라 써도
     provenance는 자체생성으로 고정된다(구조적 봉인).
  ③ **게이트 최종 봉인**: 생성기가 ①②를 어겨도 S2-a 저작권 게이트(`_evaluate_copyright`)가
     최종 차단한다(오케스트레이터가 `rejected_gate`). 생성기는 *본문 복제 여부를 판정하지 않는다*
     — 그건 사람 검수·후속이며, 여기서는 구조적으로 자체생성 메타만 박고 게이트에 맡긴다.

**레이어 순수성(import-linter 7계층 계약)**: 이 모듈은 **L3**에 산다. L3는 L4를 import할 수
없으므로(역방향 금지) `l4.misconception.catalog.CATALOG_BY_ID`를 *직접 참조하지 않는다*. 대신
오개념 카탈로그(id→한국어 라벨)를 **주입**받는다(`misconception_catalog`) — DistractorEntry
docstring이 못 박은 원칙("L1/L3은 형태만, 카탈로그 실재는 L4·게이트 소관")과 정합한다.
카탈로그를 주입하면 그 키를 allowlist로 삼아 미존재 오개념 id를 드롭하고, 라벨을 프롬프트에
싣는다. 주입이 없으면 `spec.target_misconception_ids`(스펙 저자가 이미 검증한 카탈로그-실재
집합)를 안전 allowlist로 폴백한다. 테스트·라이브 배선은 `CATALOG_BY_ID`를 주입한다(둘 다
계약 면제 지점).

────────────────────────────────────────────────────────────────────────────
라이브 핸드오프 (Kiki·Phaiakes9 실 Ollama Qwen3-Math 구동 절차)
────────────────────────────────────────────────────────────────────────────
이 환경엔 LLM 키·Ollama가 없어 라이브 호출을 하지 않는다(hermetic·FakeProvider만). Phaiakes9
에서 실제로 코퍼스를 생성하려면:

  1. **로컬 Ollama 준비**: Phaiakes9에 Qwen 계열 모델을 pull(라우터 매트릭스 모델 —
     `whymath_backend.l3.router.LOCAL_MODEL_MATRIX`·`QUALITY_MODEL_ID`). 데몬 주소는 환경변수로
     주입한다(시크릿 아님·값 아닌 변수명만):
         export WHYMATH_OLLAMA_HOST=http://127.0.0.1:11434
         export WHYMATH_OLLAMA_REQUEST_TIMEOUT_S=120
     `/status`(OllamaProvider.check_status)로 라우팅 매트릭스 모델 설치 여부를 먼저 확인한다.

  2. **실 provider 주입**(mock→live 전환):
         from whymath_backend.l3.providers.ollama import OllamaProvider
         from whymath_backend.l4.misconception.catalog import CATALOG_BY_ID  # 배선부는 계약 면제
         gen = LLMEquivalentProblemGenerator(
             OllamaProvider(),                       # 실 Ollama(지연 연결)
             misconception_catalog={mid: m.name_kr for mid, m in CATALOG_BY_ID.items()},
             subject=Subject.미적분,
             slug_prefix="wm-gen-cal",
         )
     provider=None으로 두면 표준 CompositeProvider(Ollama+Anthropic)가 자동 구성된다(라우터가
     로컬로 결정하면 Anthropic 키 없이도 로컬만 태운다).

  3. **배치 생성**(`orchestrator.run_batch`)로 코퍼스를 채운다 — 생성물은 **S2-a 게이트 +
     S2-c dedup을 통과한 분만** 저장된다(store 좌석 주입 시). 게이트가 `검수필요`로 보낸 분은
     `needs_review`(사람 검수 큐)로 남고 자동 저장되지 않는다:
         from whymath_backend.l3.equivalent.orchestrator import run_batch
         outcomes = run_batch(spec, gen, n=50, store=store,
                              dedup_index=index, embed_provider=embed)
         # outcome.status ∈ {accepted_stored, needs_review, rejected_gate,
         #                    rejected_duplicate, generation_failed}

  4. **사람 검수 큐**: `needs_review`·저작권 경계·사용자 신고분은 사람 검수로(§03 정본·환각 방어
     ④/5번). 생성기는 판정하지 않고 게이트가 분류한 것을 오케스트레이터가 큐로 흘린다.

주의(CLAUDE.md 절대 금기): provider가 돌려주는 텍스트는 *검증 전 원시 출력*이다. 학생 노출 전
반드시 S2-a 게이트(→ 스키마·SymPy·위생·동등성)를 통과해야 한다 — 이 생성기의 후보는 그 자체로
학생 노출 자격을 갖지 않는다.

범위 밖(후속): 실 Ollama 베이스라인 품질 측정·PRM·Lean·자기검증 패스 결선은 이 환경 밖이다.
본 슬라이스는 *생성기 좌석의 프로덕션 구현* + hermetic 검증까지다.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
from collections.abc import Mapping, Sequence

from pydantic import ValidationError

from whymath_backend.config import Settings
from whymath_backend.l1.problem_bank.populate import ConceptTag
from whymath_backend.l3.equivalent.acceptance import EquivalenceSpec
from whymath_backend.l3.equivalent.generator import CandidateProblem
from whymath_backend.l3.interfaces import LLMProvider
from whymath_backend.l3.models import RoutingDecision, RoutingRequest
from whymath_backend.l3.router import Router
from whymath_backend.schema.enums import (
    AnswerFormat,
    ConceptRole,
    Curriculum,
    GenerationType,
    LicenseType,
    SourceType,
    Subject,
)
from whymath_backend.schema.problem import DistractorEntry, Problem
from whymath_backend.schema.provenance import ContentProvenance

__all__ = ["LLMEquivalentProblemGenerator"]

_LOGGER = logging.getLogger(__name__)

# 개념 태깅 role 유효값(ConceptRole) — LLM이 낸 role 문자열 검증용(schema는 최하위·import 허용).
_VALID_ROLES: frozenset[str] = frozenset(r.value for r in ConceptRole)

# 유효하지 않은 JSON 백슬래시 이스케이프 탐지 — LLM이 발문·해설에 LaTeX(`\(`·`\)`·`\frac`·`\sqrt`
# 등)를 넣으면 `json.loads`가 "Invalid \escape"로 거부한다(실 LLM 실측·Phaiakes9). 유효 이스케이프
# (`\"`·`\\`·`\/`·`\b`·`\f`·`\n`·`\r`·`\t`·`\uXXXX`)를 뒤따르지 *않는* 백슬래시만 매칭한다.
_INVALID_JSON_ESCAPE = re.compile(r'\\(?!["\\/bfnrtu])')

# 난이도 float(1~5) → 라우팅 난이도 라벨. 라우터는 문자열(easy/medium/hard/killer)을 받는다.
# 콘텐츠·게이트는 spec.difficulty_overall(float)을 그대로 쓰고, 이 라벨은 *라우팅 신호*로만 쓴다.
_DIFFICULTY_EASY_MAX = 2.0
_DIFFICULTY_MEDIUM_MAX = 3.5
_DIFFICULTY_HARD_MAX = 4.5


# ──────────────────────────────────────────────────────────────────────────
# 시스템 프롬프트 — 저작권 절대 금기 + 출력 JSON 스키마 명세.
# LLM 출력의 출처 주장은 코드가 무시하므로(source_type/license 구조적 강제), 프롬프트는
# "본문 복제 금지·순수 자작"을 명령하고 정확성·형식만 요구한다.
# ──────────────────────────────────────────────────────────────────────────
_SYSTEM_PROMPT = """당신은 WhyMath의 **동등문제 저작자**입니다. 주어진 스펙(성취기준·타깃
오개념·난이도·답 형태)에 *대응하는 새 수학 문제를 스스로 생성*하세요.

## 절대 금기 (반드시 지킬 것)
- **평가원·EBS·검정 교과서의 본문·문제·풀이·그림·기출을 절대 복제·재현하지 마세요.**
  기억에 있는 기출 문항을 그대로 옮기거나 살짝 바꾸지 말고, **순수하게 새로 만든 자작 수식
  문제**만 출제하세요(저작권 절대 금기).
- 정답이 반드시 문제의 원 조건을 만족해야 합니다(거짓 문제 금지).
- 발문·해설에 틀린 수치 등식("3×4=11" 같은)을 쓰지 마세요.

## 출력 형식 (엄수)
JSON 객체 **하나만** 출력하세요. 코드펜스·설명·다른 텍스트 없이 JSON만:
{
  "question_text": "발문(자작·한국어·순수 자작 수식)",
  "answer": "정답(문자열)",
  "answer_explanation": "간결한 해설(틀린 수치 등식 금지)",
  "conditions": "정답 검산용 조건식(SymPy 표기, 예: 'x**2 - 5*x + 6 = 0'). 여러 개면 배열",
  "answer_map": {"변수": "값"},   // 조건에 정답을 대입할 치환맵, 예: {"x": "3"}
  "difficulty_overall": 3.0,       // 1.0~5.0
  "unit_codes": ["단원코드", ...], // 최소 1개
  "answer_format": "자연수",       // 자연수/분수/실수/식 중 하나
  "achievement_standard_codes": ["성취기준 고시코드", ...],
  "distractor_map": [{"choice_index": 1, "misconception_id": "오개념id"}],  // 선택
  "solution_steps": ["단계1", "단계2", ...],   // 선택(제공 시 각 단계가 검증돼야 함)
  "concept_tags": [{"concept_src_id": "개념id", "role": "PRIMARY", "relevance": 0.9}]  // 선택
}

수식은 SymPy가 파싱할 수 있는 표기(`**`=거듭제곱·`*`=곱)로 쓰세요. `conditions`와 `answer_map`은
정답이 조건을 만족하는지 기계가 검산하는 데 쓰이니 정확히 채우세요.

**중요(JSON 안전)**: 발문·해설 등 *모든 문자열*에 LaTeX 백슬래시 명령(`\\(`·`\\)`·`\\frac`·`\\sqrt`
등)을 쓰지 마세요 — JSON이 깨집니다. 수식은 `x^2`·`(x-2)(x-3)`처럼 일반 텍스트로 쓰고, 백슬래시
자체를 문자열에 넣지 마세요.
"""


class LLMEquivalentProblemGenerator:
    """프로덕션 LLM 동등문제 생성기 — `EquivalentProblemGenerator` 좌석 구현(S2-e).

    `generate(spec)`는 스펙을 비민감 요약 프롬프트로 만들어 라우터 경유로 LLM을 호출하고,
    응답 JSON을 `CandidateProblem`으로 조립한다. 저작권 메타(자체생성·WHYMATH_GENERATED·
    FULLY_GENERATED)는 LLM 출력과 무관하게 *구조적으로 강제*한다. 실패는 전부 None(안전 폴백).

    provider는 주입 가능(테스트=FakeProvider)하며 None이면 표준 `CompositeProvider`를 구성한다
    (LLMTutorPolicy·app.py 패턴 재사용·지연 연결이라 구성만으로 네트워크 미발생).
    """

    def __init__(
        self,
        provider: LLMProvider | None = None,
        *,
        settings: Settings | None = None,
        misconception_catalog: Mapping[str, str] | None = None,
        subscription: str = "free",
        difficulty: str | None = None,
        slug_prefix: str = "wm-gen",
        subject: Subject = Subject.공통,
        curriculum_version: Curriculum = Curriculum.REVISION_2022,
        valid_from_year: int = 2022,
        fallback_unit_codes: Sequence[str] = (),
    ) -> None:
        """생성기 구성.

        Args:
            provider: L3 LLM provider(라우터 경유 필수). None이면 표준 CompositeProvider 구성.
            settings: 앱 설정(선택·후속 튜닝 좌석). 지금은 보관만.
            misconception_catalog: 오개념 id→한국어 라벨 맵(주입). **L4 카탈로그를 직접 import하지
                않기 위한 주입 지점**(레이어 순수성) — 키는 distractor 오개념 allowlist, 값은
                프롬프트 라벨. None이면 `spec.target_misconception_ids`를 안전 allowlist로 폴백.
            subscription: 라우팅 신호(구독 — 클라우드 승급 가드).
            difficulty: 라우팅 난이도 라벨(None이면 spec.difficulty_overall에서 파생).
            slug_prefix: 안정 slug 접두사(결정론 해시와 결합해 멱등 upsert 키 생성).
            subject·curriculum_version·valid_from_year: Problem 필수 메타 기본값(스펙 밖·저작 배선).
            fallback_unit_codes: LLM이 unit_codes를 안 주면 쓰는 폴백(비면 결측 시 생성 실패).
        """
        if provider is None:
            # 표준 구성 재사용(LLMTutorPolicy·app.py 동형) — 지연 연결이라 구성만으로 네트워크 0.
            from whymath_backend.l3.providers.anthropic import AnthropicProvider
            from whymath_backend.l3.providers.composite import CompositeProvider
            from whymath_backend.l3.providers.ollama import OllamaProvider

            provider = CompositeProvider(local=OllamaProvider(), cloud=AnthropicProvider())
        self._provider = provider
        self._settings = settings
        self._catalog = dict(misconception_catalog) if misconception_catalog is not None else None
        self._subscription = subscription
        self._difficulty = difficulty
        self._slug_prefix = slug_prefix
        self._subject = subject
        self._curriculum_version = curriculum_version
        self._valid_from_year = valid_from_year
        self._fallback_unit_codes = list(fallback_unit_codes)

    # ── EquivalentProblemGenerator 좌석 ────────────────────────────────
    def generate(self, spec: EquivalenceSpec) -> CandidateProblem | None:
        """스펙에 맞는 동등문제 후보 1건을 생성(실패 시 None·크래시 금지).

        흐름: 프롬프트 조립 → 라우터 결정 → provider.generate(동기 경계) → JSON 관대 파싱 →
        CandidateProblem 조립(저작권 메타 구조적 강제). 어느 단계든 실패하면 로그 + None을
        돌려 오케스트레이터가 `generation_failed`로 정직히 처리하게 한다.
        """
        prompt = self._build_user_prompt(spec)
        decision = Router().route(self._routing_request(spec))
        try:
            raw = self._invoke(prompt, decision)
        except Exception as exc:  # noqa: BLE001 — provider 장애 시 배치 크래시 금지·안전 폴백.
            _LOGGER.warning("동등문제 생성 provider 호출 실패 — None 폴백: %s", exc)
            return None

        data = self._extract_json(raw)
        if data is None:
            _LOGGER.warning("동등문제 생성 응답 JSON 파싱 실패 — None 폴백.")
            return None

        try:
            candidate = self._assemble(spec, data)
        except (ValidationError, ValueError, KeyError, TypeError) as exc:
            # Problem/Provenance 불변식 위반(저작권 게이트가 생성 거부)·필수 결측·타입 오류.
            # 조용히 통과시키지 않고 로그 + None(게이트에 도달하기 전 정직한 생성 실패).
            _LOGGER.warning("동등문제 후보 조립 실패 — None 폴백: %s", exc)
            return None
        return candidate

    # ── 동기 경계(async provider.generate를 배치 sync 문맥에서 호출) ─────
    def _invoke(self, prompt: str, decision: RoutingDecision) -> str:
        """provider.generate(async)를 sync 경계에서 실행 — 오프라인 배치 문맥 전용.

        오케스트레이터(`run_batch`)는 sync라 여기서 `asyncio.run`으로 코루틴을 완주시킨다
        (LLMTutorPolicy 테스트의 `asyncio.run(next_action)` 경계 미러). 이미 러닝 루프가 있는
        async 문맥에서의 호출은 이 배치 좌석의 계약 밖이다(명확한 RuntimeError로 드러남).
        """
        return asyncio.run(self._provider.generate(prompt, _SYSTEM_PROMPT, decision))

    # ── 라우팅 신호 ────────────────────────────────────────────────────
    def _routing_request(self, spec: EquivalenceSpec) -> RoutingRequest:
        """생성 호출의 라우팅 신호 — task_type='generate'(→ MATH 패밀리·수학 저작).

        난이도는 스펙에서 파생(생성자 override 우선), 다단계 추론 필요(정답이 조건을 만족하는
        새 문제 구성). 무료·예산 0이면 라우터가 LOCAL로 강제한다(Phaiakes9 로컬 우선).
        """
        difficulty = self._difficulty or self._difficulty_label(spec.difficulty_overall)
        return RoutingRequest(
            task_type="generate",
            difficulty=difficulty,
            requires_reasoning=True,
            student_subscription=self._subscription,
            sync=True,
        )

    @staticmethod
    def _difficulty_label(overall: float) -> str:
        """난이도 float(1~5) → 라우팅 라벨(easy/medium/hard/killer)."""
        if overall < _DIFFICULTY_EASY_MAX:
            return "easy"
        if overall < _DIFFICULTY_MEDIUM_MAX:
            return "medium"
        if overall < _DIFFICULTY_HARD_MAX:
            return "hard"
        return "killer"

    # ── 사용자 프롬프트(비민감 스펙 요약·Minimal context) ───────────────
    def _build_user_prompt(self, spec: EquivalenceSpec) -> str:
        """스펙을 비민감 요약으로 압축 — 과다 주입 금지(Minimal context·플레이북 Part 8).

        성취기준 코드·오개념 id(주입된 라벨 병기)·난이도·답 형태만 싣는다. 원본 본문·풀이는
        스펙에 없고(애초에 자작 대응이므로) 프롬프트에도 없다.
        """
        misconceptions = [
            {"id": mid, "label": self._label_for(mid)}
            for mid in sorted(spec.target_misconception_ids)
        ]
        summary: dict[str, object] = {
            "achievement_standard_codes": sorted(spec.achievement_standard_codes),
            "target_misconceptions": misconceptions,
            "difficulty_overall": spec.difficulty_overall,
            "answer_format": self._enum_value(spec.answer_format),
        }
        spec_json = json.dumps(summary, ensure_ascii=False, indent=2)
        return (
            "다음 스펙에 대응하는 *새 자작 동등문제*를 만들어 JSON 하나로만 출력하세요"
            "(평가원·EBS·교과서 본문/기출 복제 절대 금지):\n"
            f"{spec_json}"
        )

    def _label_for(self, misconception_id: str) -> str:
        """오개념 id의 한국어 라벨 — 주입된 카탈로그에 있으면 그 라벨, 없으면 id 자체."""
        if self._catalog is not None:
            return self._catalog.get(misconception_id, misconception_id)
        return misconception_id

    # ── JSON 관대 추출(LLMTutorPolicy `_extract_json` 미러 + LaTeX 이스케이프 내성) ──
    @classmethod
    def _extract_json(cls, raw: str) -> dict[str, object] | None:
        """원시 텍스트에서 JSON 객체를 관대하게 추출 — 코드펜스·주변 산문·LaTeX 백슬래시 허용.

        후보(통째로 / 첫 `{`…마지막 `}` 구간) 각각을 *원문* 그리고 *이스케이프 sanitize본*으로
        파싱 시도한다. sanitize는 LaTeX(`\\(`·`\\frac` 등) 유효하지 않은 백슬래시 이스케이프를
        리터럴로 이중화해 `json.loads`의 "Invalid \\escape" 실패를 구제한다(실 LLM 실측). 유효
        이스케이프는 보존하므로 정상 JSON은 그대로 파싱된다(무해).
        """
        text = raw.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
        candidates = [text]
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end > start:
            candidates.append(text[start : end + 1])
        for candidate in candidates:
            for attempt in (candidate, _INVALID_JSON_ESCAPE.sub(r"\\\\", candidate)):
                try:
                    obj = json.loads(attempt)
                except json.JSONDecodeError:
                    continue
                if isinstance(obj, dict):
                    return obj
        return None

    # ── CandidateProblem 조립(저작권 메타 구조적 강제) ──────────────────
    def _assemble(self, spec: EquivalenceSpec, data: dict[str, object]) -> CandidateProblem:
        """파싱된 응답 → `CandidateProblem`. 저작권 메타는 LLM과 무관하게 구조적으로 박는다.

        필수 결측·타입 오류·불변식 위반은 예외로 전파돼(호출자가) None 폴백된다. distractor 오개념
        id는 allowlist(주입 카탈로그 키 ∪ 스펙 타깃)에 없는 것을 드롭한다.
        """
        question_text = self._require_str(data, "question_text")
        answer = self._require_str(data, "answer")
        answer_explanation = self._opt_str(data, "answer_explanation")
        conditions = self._parse_conditions(data.get("conditions"))
        answer_map = self._parse_answer_map(data.get("answer_map"))
        difficulty_overall = self._parse_difficulty(data.get("difficulty_overall"), spec)
        unit_codes = self._parse_unit_codes(data.get("unit_codes"))
        answer_format = self._parse_answer_format(data.get("answer_format"), spec)
        standard_codes = self._parse_standard_codes(data.get("achievement_standard_codes"), spec)
        distractor_map = self._parse_distractor_map(data.get("distractor_map"), spec)
        solution_steps = self._parse_solution_steps(data.get("solution_steps"))
        concept_tags = self._parse_concept_tags(data.get("concept_tags"))
        slug = self._stable_slug(question_text, answer, standard_codes)

        # ── 저작권 구조적 강제(② 코드 방어) — LLM 출력의 출처 주장은 읽지 않는다. ──
        problem = Problem(
            slug=slug,
            source_type=SourceType.자체생성,  # 무조건 자체생성(본문 보유 자격)
            curriculum_version=self._curriculum_version,
            valid_from_year=self._valid_from_year,
            subject=self._subject,
            unit_codes=unit_codes,
            difficulty_overall=difficulty_overall,
            answer_format=answer_format,
            achievement_standard_codes=standard_codes,
            distractor_map=distractor_map or None,
            question_text=question_text,
            answer=answer,
            answer_explanation=answer_explanation,
        )
        provenance = ContentProvenance(
            generation_type=GenerationType.FULLY_GENERATED,  # AI 완전 생성
            license=LicenseType.WHYMATH_GENERATED,  # 지배 license 고정
            original_source=None,  # 원본 없음(자작) — 본문성 키 0
            transformation_pipeline={
                "steps": [
                    "LLM 자작 초안(라우터 경유)",
                    "S2-a 수용 게이트",
                    "사람 검수 큐(필요 시)",
                ],
            },
        )
        return CandidateProblem(
            problem=problem,
            provenance=provenance,
            conditions=conditions,
            answer_map=answer_map,
            solution_steps=solution_steps,
            concept_tags=concept_tags,
        )

    # ── 필드 파싱·강제 헬퍼(전부 결정론·순수) ──────────────────────────
    @staticmethod
    def _require_str(data: Mapping[str, object], key: str) -> str:
        """필수 문자열 필드 — 결측·빈값·비문자열은 ValueError(→ None 폴백)."""
        value = data.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"필수 문자열 필드 결측/무효: {key!r}")
        return value.strip()

    @staticmethod
    def _opt_str(data: Mapping[str, object], key: str) -> str | None:
        """선택 문자열 — 없거나 비문자열이면 None."""
        value = data.get(key)
        return value.strip() if isinstance(value, str) and value.strip() else None

    @staticmethod
    def _parse_conditions(value: object) -> str | list[str]:
        """조건 — 문자열 또는 문자열 배열. 무효면 ValueError(정확성 검산 재료 결측)."""
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, list):
            items = [str(v).strip() for v in value if isinstance(v, str) and str(v).strip()]
            if items:
                return items
        raise ValueError("conditions 결측/무효 — 정확성 검산 재료가 없습니다.")

    @staticmethod
    def _parse_answer_map(value: object) -> dict[str, str]:
        """치환맵 — {변수: 값} 문자열 맵. 무효면 ValueError(정확성 검산 재료 결측)."""
        if isinstance(value, dict) and value:
            result: dict[str, str] = {}
            for var, val in value.items():
                if not isinstance(var, str) or not str(var).strip():
                    raise ValueError("answer_map 변수 키 무효.")
                result[str(var).strip()] = str(val).strip()
            if result:
                return result
        raise ValueError("answer_map 결측/무효 — 정확성 검산 재료가 없습니다.")

    def _parse_difficulty(self, value: object, spec: EquivalenceSpec) -> float:
        """난이도 — LLM값을 1.0~5.0으로 클램프, 무효면 스펙 난이도로 폴백."""
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return min(5.0, max(1.0, float(value)))
        return spec.difficulty_overall

    def _parse_unit_codes(self, value: object) -> list[str]:
        """단원 코드 — 문자열 배열(최소 1). 없으면 폴백, 폴백도 비면 ValueError."""
        if isinstance(value, list):
            codes = [str(v).strip() for v in value if isinstance(v, str) and str(v).strip()]
            if codes:
                return codes
        if self._fallback_unit_codes:
            return list(self._fallback_unit_codes)
        raise ValueError("unit_codes 결측 — Problem은 단원 코드 최소 1개가 필요합니다.")

    def _parse_answer_format(self, value: object, spec: EquivalenceSpec) -> AnswerFormat | None:
        """답 형태 — 유효 enum 값이면 그대로, 무효면 스펙 답형태로 폴백."""
        if isinstance(value, str):
            try:
                return AnswerFormat(value.strip())
            except ValueError:
                pass
        return spec.answer_format

    @staticmethod
    def _parse_standard_codes(value: object, spec: EquivalenceSpec) -> list[str]:
        """성취기준 코드 — LLM 배열이 있으면 그것(게이트가 스펙 대비 검증), 없으면 스펙 폴백."""
        if isinstance(value, list):
            codes = [str(v).strip() for v in value if isinstance(v, str) and str(v).strip()]
            if codes:
                return codes
        return sorted(spec.achievement_standard_codes)

    def _acceptable_misconceptions(self, spec: EquivalenceSpec) -> frozenset[str]:
        """distractor 오개념 allowlist — 주입 카탈로그 키(있으면), 없으면 스펙 타깃(안전 폴백).

        레이어 순수성: L3는 L4 카탈로그를 import하지 않으므로 주입된 키집합을 실재 검증에 쓴다.
        미주입 시 `spec.target_misconception_ids`(스펙 저자가 검증한 카탈로그-실재 집합)로 폴백.
        """
        if self._catalog is not None:
            return frozenset(self._catalog)
        return spec.target_misconception_ids

    def _parse_distractor_map(self, value: object, spec: EquivalenceSpec) -> list[DistractorEntry]:
        """오답→오개념 매핑 — allowlist 밖 오개념 id는 드롭(미존재 방어). 무효 원소도 스킵."""
        if not isinstance(value, list):
            return []
        acceptable = self._acceptable_misconceptions(spec)
        entries: list[DistractorEntry] = []
        for raw in value:
            if not isinstance(raw, dict):
                continue
            mid = raw.get("misconception_id")
            idx = raw.get("choice_index")
            if not isinstance(mid, str) or mid.strip() not in acceptable:
                continue  # 미존재/미지 오개념 — 드롭(조용한 채택 금지)
            if not isinstance(idx, int) or isinstance(idx, bool) or idx < 0:
                continue
            op_raw = raw.get("op_code")
            op_code = op_raw.strip() if isinstance(op_raw, str) and op_raw.strip() else None
            entries.append(
                DistractorEntry(choice_index=idx, misconception_id=mid.strip(), op_code=op_code)
            )
        return entries

    @staticmethod
    def _parse_solution_steps(value: object) -> list[str] | None:
        """풀이 단계(선택) — 문자열 배열, 없거나 비면 None(미제공)."""
        if isinstance(value, list):
            steps = [str(v).strip() for v in value if isinstance(v, str) and str(v).strip()]
            if steps:
                return steps
        return None

    @staticmethod
    def _parse_concept_tags(value: object) -> list[ConceptTag]:
        """개념 태깅(선택) — (concept_src_id·role·relevance). role은 ConceptRole 값·기본 PRIMARY."""
        if not isinstance(value, list):
            return []
        tags: list[ConceptTag] = []
        for raw in value:
            if not isinstance(raw, dict):
                continue
            src_id = raw.get("concept_src_id")
            if not isinstance(src_id, str) or not src_id.strip():
                continue
            role_raw = raw.get("role")
            role = role_raw if isinstance(role_raw, str) and role_raw in _VALID_ROLES else "PRIMARY"
            rel_raw = raw.get("relevance")
            relevance = (
                float(rel_raw)
                if isinstance(rel_raw, (int, float)) and not isinstance(rel_raw, bool)
                else None
            )
            tags.append(ConceptTag(concept_src_id=src_id.strip(), role=role, relevance=relevance))
        return tags

    def _stable_slug(self, question_text: str, answer: str, standard_codes: Sequence[str]) -> str:
        """결정론 안정 slug — `slug_prefix` + 내용 해시. 멱등 upsert 안정 키(재실행 재현).

        같은 내용은 같은 slug → S2-b 멱등 upsert가 중복 저장을 방지한다. 해시는 발문·정답·
        성취기준으로 만들어 콘텐츠가 바뀌면 slug도 바뀐다(내용-주소화).
        """
        payload = "|".join([question_text, answer, ",".join(sorted(standard_codes))])
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
        return f"{self._slug_prefix}-{digest}"

    @staticmethod
    def _enum_value(value: object) -> object:
        """enum이면 .value, 아니면 그대로(프롬프트 직렬화용·use_enum_values 대응)."""
        if isinstance(value, AnswerFormat):
            return value.value
        return value
