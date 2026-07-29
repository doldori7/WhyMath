"""pathscope.py — 파일 범위 겹침 판정(보수적 2단 근사) 테스트."""

from __future__ import annotations

from pathscope import (
    Overlap,
    expand,
    glob_to_regex,
    normalize,
    overlap,
    path_in_scope,
    static_prefix,
)

FILES = [
    "src/backend/api/routes.py",
    "src/backend/api/deps.py",
    "src/backend/schema/task.py",
    "src/data-pipeline/crawler/ncic.py",
    "docs/standards/build_harness.md",
    "README.md",
]


class TestGlobToRegex:
    def test_double_star_crosses_path_separator(self):
        """이중별표는 경로 구분자를 넘는다."""
        rx = glob_to_regex("src/backend/**")
        assert rx.match("src/backend/api/routes.py")
        assert rx.match("src/backend/x.py")
        assert not rx.match("src/data-pipeline/x.py")

    def test_double_star_slash_matches_zero_depth(self):
        """이중별표 슬래시는 영깊이도 매치."""
        rx = glob_to_regex("src/**/routes.py")
        assert rx.match("src/backend/api/routes.py")
        assert rx.match("src/routes.py")  # '**/' = 0개 이상 디렉토리

    def test_single_star_does_not_cross_separator(self):
        """단일별표는 경로 구분자를 넘지 않는다."""
        rx = glob_to_regex("src/backend/*.py")
        assert not rx.match("src/backend/api/routes.py")
        assert rx.match("src/backend/main.py")

    def test_question_mark_matches_one_character(self):
        """물음표는 한 글자."""
        rx = glob_to_regex("docs/v?.md")
        assert rx.match("docs/v1.md")
        assert not rx.match("docs/v12.md")

    def test_directory_pattern_expands_to_subtree(self):
        """디렉토리성 패턴은 하위 전체로 확장."""
        # 끝 '/'인 패턴은 'p/**' 취급
        assert normalize("src/backend/") == "src/backend/**"
        rx = glob_to_regex("src/backend/")
        assert rx.match("src/backend/api/routes.py")


class TestStaticPrefix:
    def test_prefix_before_wildcard(self):
        """와일드카드 앞 프리픽스."""
        assert static_prefix("src/backend/**") == "src/backend/"
        assert static_prefix("src/backend/api/*.py") == "src/backend/api/"

    def test_literal_path_includes_directory(self):
        """리터럴 경로는 디렉토리까지."""
        assert static_prefix("src/backend/api/routes.py") == "src/backend/api/"

    def test_root_level_glob_has_empty_prefix(self):
        """루트 수준 글롭은 빈 프리픽스."""
        assert static_prefix("*.md") == ""


class TestExpandAndScope:
    def test_expands_real_files(self):
        """실파일 전개."""
        assert expand(["src/backend/api/**"], FILES) == {
            "src/backend/api/routes.py",
            "src/backend/api/deps.py",
        }

    def test_single_scope_decision(self):
        """단건 스코프 판정."""
        globs = ["src/backend/**", "docs/standards/build_harness.md"]
        assert path_in_scope("src/backend/api/routes.py", globs)
        assert path_in_scope("docs/standards/build_harness.md", globs)
        assert not path_in_scope("src/mobile/lib/main.dart", globs)


class TestOverlap:
    def test_detects_real_file_intersection(self):
        """실파일 교집합 검출."""
        result = overlap("A", ["src/backend/api/**"], "B", ["src/backend/**"], FILES)
        assert isinstance(result, Overlap)
        assert "src/backend/api/routes.py" in result.files

    def test_detects_prefix_containment_for_new_files(self):
        """프리픽스 포함 검출 신규파일 대비."""
        # 아직 존재하지 않는 파일(1단이 못 봄)도 프리픽스 포함으로 잡는다
        result = overlap("A", ["src/backend/**"], "B", ["src/backend/api/new_file.py"], files=[])
        assert result is not None
        assert result.prefix_hit is not None

    def test_separate_domains_do_not_overlap(self):
        """도메인 분리는 무겹침."""
        assert overlap("A", ["src/backend/**"], "B", ["src/data-pipeline/**"], FILES) is None
        assert overlap("A", ["src/mobile/**"], "B", ["docs/**"], FILES) is None

    def test_undeclared_paths_yields_no_decision(self):
        """한쪽 paths 미선언이면 판정 불가."""
        assert overlap("A", [], "B", ["src/backend/**"], FILES) is None

    def test_identical_literal_file_caught_at_first_stage(self):
        """리터럴 동일 파일은 1단이 잡는다."""
        result = overlap(
            "A",
            ["docs/standards/build_harness.md"],
            "B",
            ["docs/standards/build_harness.md"],
            FILES,
        )
        assert result is not None
        assert result.files == ["docs/standards/build_harness.md"]

    def test_describe_summarizes_the_evidence(self):
        """describe는 근거를 요약한다."""
        result = overlap("A", ["src/backend/**"], "B", ["src/backend/api/**"], FILES)
        assert result is not None
        assert "교집합" in result.describe() or "프리픽스" in result.describe()
