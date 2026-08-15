"""DSL 다중 검증 엔진 — 문법 → 스키마 → 의미 → 수학 → 교육 → 중복.

설계 정본: `docs/architecture/03d_dsl_content_generator.md` §5.

각 검증기는 독립적으로 교체 가능하며, ValidationReport를 통해 통합된다.
"""

from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass

from pydantic import ValidationError

from whymath_backend.l3.dsl.models import ProblemDSL, ValidationReport
from whymath_backend.l3.pregenerate.models import ValidationSignal


@dataclass(frozen=True, slots=True)
class ValidationResult:
    """검증기 한 개의 결과."""

    passed: bool
    signal: ValidationSignal | None = None


class BaseDSLValidator(ABC):
    """DSL 검증기 경계."""

    @property
    @abstractmethod
    def stage(self) -> str:
        """검증 단계 이름."""

    @abstractmethod
    def validate(self, dsl: ProblemDSL) -> ValidationResult:
        """검증을 수행한다."""


class SyntaxValidator(BaseDSLValidator):
    """① 문법 검증 — Pydantic이 이미 수행한 최소 위생 확인.

    ProblemDSL이 생성되면 대부분의 문법 검증은 끝난다. 이 단계는
    YAML/JSON → Pydantic 변환 시점의 오류를 포착하는 외부 경계다.
    """

    @property
    def stage(self) -> str:
        return "syntax"

    def validate(self, dsl: ProblemDSL) -> ValidationResult:
        # ProblemDSL이 성공적으로 생성됐다면 문법 검증은 통과.
        return ValidationResult(passed=True)


class SchemaValidator(BaseDSLValidator):
    """② 스키마 검증 — Pydantic 모델 재검증."""

    @property
    def stage(self) -> str:
        return "schema"

    def validate(self, dsl: ProblemDSL) -> ValidationResult:
        try:
            ProblemDSL.model_validate(dsl.model_dump())
        except ValidationError as exc:
            return ValidationResult(
                passed=False,
                signal=ValidationSignal(kind="other", reason=str(exc)),
            )
        return ValidationResult(passed=True)


class SemanticValidator(BaseDSLValidator):
    """③ 의미 검증 — 학년-개념 일관성 등 교육과정 논리."""

    @property
    def stage(self) -> str:
        return "semantic"

    def validate(self, dsl: ProblemDSL) -> ValidationResult:
        # 학년과 개념 도메인의 상식적 일관성 검사.
        grade = dsl.curriculum.grade.lower()
        concept = dsl.curriculum.concept.lower()

        # 간단한 규칙: 고등학교 개념이 초등학교에 등장하면 FAIL.
        if "elementary" in grade and any(
            kw in concept for kw in ("calculus", "derivative", "integral", "limit")
        ):
            return ValidationResult(
                passed=False,
                signal=ValidationSignal(
                    kind="other",
                    reason="초등학교 학년에 미적분 개념이 배정되었습니다.",
                ),
            )

        return ValidationResult(passed=True)


class EducationValidator(BaseDSLValidator):
    """⑤ 교육학 검증 — 읽기 수준, 성취기준 매핑 등."""

    @property
    def stage(self) -> str:
        return "education"

    def validate(self, dsl: ProblemDSL) -> ValidationResult:
        # 문제 본문이 너무 길면 경고(초기에는 단순 휴리스틱).
        statement = dsl.problem.statement or dsl.problem.template or ""
        if len(statement) > 2000:
            return ValidationResult(
                passed=False,
                signal=ValidationSignal(
                    kind="other",
                    reason="문제 본문이 2000자를 초과합니다.",
                ),
            )
        return ValidationResult(passed=True)


class DuplicateValidator(BaseDSLValidator):
    """⑥ 중복 검사 — 해시 기반 최소 구현."""

    def __init__(self, existing_hashes: set[str] | None = None) -> None:
        self._existing_hashes = existing_hashes or set()

    @property
    def stage(self) -> str:
        return "duplicate"

    def validate(self, dsl: ProblemDSL) -> ValidationResult:
        content = dsl.model_dump_json(exclude={"content_id", "dsl_version"})
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        if content_hash in self._existing_hashes:
            return ValidationResult(
                passed=False,
                signal=ValidationSignal(
                    kind="other",
                    reason="동일한 내용의 콘텐츠가 이미 존재합니다.",
                ),
            )
        return ValidationResult(passed=True)


class DSLValidationPipeline:
    """6단계 검증 파이프라인 조립."""

    def __init__(
        self,
        *,
        syntax: BaseDSLValidator | None = None,
        schema: BaseDSLValidator | None = None,
        semantic: BaseDSLValidator | None = None,
        math: BaseDSLValidator | None = None,
        education: BaseDSLValidator | None = None,
        duplicate: BaseDSLValidator | None = None,
    ) -> None:
        self._validators: dict[str, BaseDSLValidator] = {}
        if syntax is not None:
            self._validators["syntax"] = syntax
        if schema is not None:
            self._validators["schema"] = schema
        if semantic is not None:
            self._validators["semantic"] = semantic
        if math is not None:
            self._validators["math"] = math
        if education is not None:
            self._validators["education"] = education
        if duplicate is not None:
            self._validators["duplicate"] = duplicate

    def validate(self, dsl: ProblemDSL) -> ValidationReport:
        """모든 검증기를 실행하고 ValidationReport를 만든다."""
        results: dict[str, ValidationResult] = {}
        signals: list[dict[str, str]] = []

        for stage, validator in self._validators.items():
            result = validator.validate(dsl)
            results[stage] = result
            if result.signal is not None:
                signals.append(
                    {
                        "stage": stage,
                        "kind": result.signal.kind,
                        "reason": result.signal.reason,
                    }
                )

        def status(stage: str) -> str:
            r = results.get(stage)
            if r is None:
                return "PASS"
            return "PASS" if r.passed else "FAIL"

        math_status = status("math")
        if math_status == "FAIL":
            math_status = "FAIL"
        elif math_status == "PASS":
            math_status = "PASS"

        # 수학 정답 FAIL은 전체 FAIL
        publishable = (
            status("syntax") == "PASS"
            and status("schema") == "PASS"
            and status("semantic") == "PASS"
            and math_status == "PASS"
            and status("education") == "PASS"
            and status("duplicate") == "PASS"
        )

        return ValidationReport(
            syntax=status("syntax"),
            schema_validation=status("schema"),
            semantic=status("semantic"),
            math=math_status,  # type: ignore[arg-type]
            education=status("education"),
            duplicate=status("duplicate"),
            publishable=publishable,
            signals=tuple(signals),
        )


__all__ = [
    "BaseDSLValidator",
    "DSLValidationPipeline",
    "DuplicateValidator",
    "EducationValidator",
    "SchemaValidator",
    "SemanticValidator",
    "SyntaxValidator",
    "ValidationResult",
]
