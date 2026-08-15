"""품질 게이트 — 콘텐츠 품질 점수 산출 및 출판 판정.

설계 정본: `docs/architecture/03d_dsl_content_generator.md` §5.3.

- 수학 정답 FAIL은 다른 점수로 상쇄할 수 없다.
- 초기에는 Human-in-the-loop으로 운영하고, 데이터 축적 후 자동 출판 비율을 높인다.
"""

from __future__ import annotations

from whymath_backend.l3.dsl.models import ValidationReport


class QualityGate:
    """품질 게이트 — ValidationReport를 최종 출판 판정으로 변환한다."""

    def evaluate(self, report: ValidationReport) -> ValidationReport:
        """품질 점수를 계산하고 publishable을 갱신한다."""
        if not report.math_passed:
            # 수학 정답 FAIL은 무조건 전체 FAIL.
            return report.model_copy(update={"quality_score": 0.0, "publishable": False})

        score = self._compute_score(report)
        publishable = report.publishable and score >= 0.95
        return report.model_copy(update={"quality_score": score, "publishable": publishable})

    def _compute_score(self, report: ValidationReport) -> float:
        """품질 점수 공식.

        Q = 0.25 × Math Correctness
          + 0.20 × Educational Alignment
          + 0.15 × Solution Consistency
          + 0.15 × Difficulty Accuracy
          + 0.10 × Language Quality
          + 0.10 × Originality
          + 0.05 × Metadata Completeness
        """
        math_score = 1.0 if report.math == "PASS" else 0.0
        edu_score = 1.0 if report.education == "PASS" else 0.0
        solution_score = 1.0 if report.semantic == "PASS" else 0.0
        difficulty_score = 0.9  # TODO: 실제 난이도 모델 연동
        language_score = 0.9  # TODO: 언어 품질 평가 모델 연동
        originality_score = 1.0 if report.duplicate == "PASS" else 0.0
        metadata_score = 1.0 if report.schema_validation == "PASS" else 0.0

        return (
            0.25 * math_score
            + 0.20 * edu_score
            + 0.15 * solution_score
            + 0.15 * difficulty_score
            + 0.10 * language_score
            + 0.10 * originality_score
            + 0.05 * metadata_score
        )


__all__ = ["QualityGate"]
