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
    def test_이중별표는_경로_구분자를_넘는다(self):
        rx = glob_to_regex("src/backend/**")
        assert rx.match("src/backend/api/routes.py")
        assert rx.match("src/backend/x.py")
        assert not rx.match("src/data-pipeline/x.py")

    def test_이중별표_슬래시는_영깊이도_매치(self):
        rx = glob_to_regex("src/**/routes.py")
        assert rx.match("src/backend/api/routes.py")
        assert rx.match("src/routes.py")  # '**/' = 0개 이상 디렉토리

    def test_단일별표는_경로_구분자를_넘지_않는다(self):
        rx = glob_to_regex("src/backend/*.py")
        assert not rx.match("src/backend/api/routes.py")
        assert rx.match("src/backend/main.py")

    def test_물음표는_한_글자(self):
        rx = glob_to_regex("docs/v?.md")
        assert rx.match("docs/v1.md")
        assert not rx.match("docs/v12.md")

    def test_디렉토리성_패턴은_하위_전체로_확장(self):
        # 끝 '/'인 패턴은 'p/**' 취급
        assert normalize("src/backend/") == "src/backend/**"
        rx = glob_to_regex("src/backend/")
        assert rx.match("src/backend/api/routes.py")


class TestStaticPrefix:
    def test_와일드카드_앞_프리픽스(self):
        assert static_prefix("src/backend/**") == "src/backend/"
        assert static_prefix("src/backend/api/*.py") == "src/backend/api/"

    def test_리터럴_경로는_디렉토리까지(self):
        assert static_prefix("src/backend/api/routes.py") == "src/backend/api/"

    def test_루트_수준_글롭은_빈_프리픽스(self):
        assert static_prefix("*.md") == ""


class TestExpandAndScope:
    def test_실파일_전개(self):
        assert expand(["src/backend/api/**"], FILES) == {
            "src/backend/api/routes.py",
            "src/backend/api/deps.py",
        }

    def test_단건_스코프_판정(self):
        globs = ["src/backend/**", "docs/standards/build_harness.md"]
        assert path_in_scope("src/backend/api/routes.py", globs)
        assert path_in_scope("docs/standards/build_harness.md", globs)
        assert not path_in_scope("src/mobile/lib/main.dart", globs)


class TestOverlap:
    def test_실파일_교집합_검출(self):
        result = overlap("A", ["src/backend/api/**"], "B", ["src/backend/**"], FILES)
        assert isinstance(result, Overlap)
        assert "src/backend/api/routes.py" in result.files

    def test_프리픽스_포함_검출_신규파일_대비(self):
        # 아직 존재하지 않는 파일(1단이 못 봄)도 프리픽스 포함으로 잡는다
        result = overlap("A", ["src/backend/**"], "B", ["src/backend/api/new_file.py"], files=[])
        assert result is not None
        assert result.prefix_hit is not None

    def test_도메인_분리는_무겹침(self):
        assert overlap("A", ["src/backend/**"], "B", ["src/data-pipeline/**"], FILES) is None
        assert overlap("A", ["src/mobile/**"], "B", ["docs/**"], FILES) is None

    def test_한쪽_paths_미선언이면_판정_불가(self):
        assert overlap("A", [], "B", ["src/backend/**"], FILES) is None

    def test_리터럴_동일_파일은_1단이_잡는다(self):
        result = overlap(
            "A", ["docs/standards/build_harness.md"],
            "B", ["docs/standards/build_harness.md"], FILES,
        )
        assert result is not None
        assert result.files == ["docs/standards/build_harness.md"]

    def test_describe는_근거를_요약한다(self):
        result = overlap("A", ["src/backend/**"], "B", ["src/backend/api/**"], FILES)
        assert result is not None
        assert "교집합" in result.describe() or "프리픽스" in result.describe()
