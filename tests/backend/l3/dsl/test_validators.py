"""DSL 검증 파이프라인 테스트."""

from whymath_backend.l3.dsl.models import (
    AnswerSpec,
    CurriculumMeta,
    DifficultyMeta,
    ProblemDSL,
    ProblemTemplate,
)
from whymath_backend.l3.dsl.validators import (
    DSLValidationPipeline,
    DuplicateValidator,
    EducationValidator,
    SchemaValidator,
    SemanticValidator,
    SyntaxValidator,
)


def _make_valid_dsl() -> ProblemDSL:
    return ProblemDSL(
        content_id="TEST-VAL-001",
        curriculum=CurriculumMeta(
            subject="mathematics", grade="middle_2", concept="linear_equation"
        ),
        difficulty=DifficultyMeta(level=3),
        problem=ProblemTemplate(statement="x + 2 = 5 일 때 x를 구하여라."),
        answer=AnswerSpec(type="integer", value="3"),
    )


def test_validation_pipeline_all_pass() -> None:
    pipeline = DSLValidationPipeline(
        syntax=SyntaxValidator(),
        schema=SchemaValidator(),
        semantic=SemanticValidator(),
        education=EducationValidator(),
        duplicate=DuplicateValidator(),
    )
    report = pipeline.validate(_make_valid_dsl())
    assert report.syntax == "PASS"
    assert report.schema_validation == "PASS"
    assert report.semantic == "PASS"
    assert report.education == "PASS"
    assert report.duplicate == "PASS"
    assert report.publishable is True


def test_semantic_validator_rejects_calculus_in_elementary() -> None:
    dsl = ProblemDSL(
        content_id="TEST-VAL-002",
        curriculum=CurriculumMeta(subject="mathematics", grade="elementary_3", concept="calculus"),
        difficulty=DifficultyMeta(level=3),
        problem=ProblemTemplate(statement="미분을 구하여라."),
        answer=AnswerSpec(type="expression", expression="x"),
    )
    validator = SemanticValidator()
    result = validator.validate(dsl)
    assert result.passed is False
    assert "초등학교" in (result.signal.reason if result.signal else "")


def test_education_validator_rejects_long_statement() -> None:
    long_text = "a" * 2001
    dsl = ProblemDSL(
        content_id="TEST-VAL-003",
        curriculum=CurriculumMeta(
            subject="mathematics", grade="middle_2", concept="linear_equation"
        ),
        difficulty=DifficultyMeta(level=3),
        problem=ProblemTemplate(statement=long_text),
        answer=AnswerSpec(type="integer", value="3"),
    )
    validator = EducationValidator()
    result = validator.validate(dsl)
    assert result.passed is False


def test_duplicate_validator_rejects_duplicate() -> None:
    dsl = _make_valid_dsl()
    # 첫 번째는 통과
    dup = DuplicateValidator()
    result1 = dup.validate(dsl)
    assert result1.passed is True

    # 같은 내용을 가진 다른 content_id는 중복으로 판정
    dsl2 = dsl.model_copy(update={"content_id": "TEST-VAL-002"})
    # 직접 해시 주입
    import hashlib

    content = dsl2.model_dump_json(exclude={"content_id", "dsl_version"})
    hash_val = hashlib.sha256(content.encode("utf-8")).hexdigest()
    dup_with_hash = DuplicateValidator(existing_hashes={hash_val})
    result2 = dup_with_hash.validate(dsl2)
    assert result2.passed is False
