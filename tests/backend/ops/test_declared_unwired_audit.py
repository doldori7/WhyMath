"""선언≠배선 일반 탐지기 hermetic 테스트 — OPS-22.

전부 DB·LLM·HTTP 0(빌드타임 결정론). 합성 패키지 트리(`tmp_path`)로 4축 수집기의 변별력을
직접 실측한다 — "성공/실패 양쪽에서 같은 값을 내는 검사는 검증이 아니라 위장"(CLAUDE.md)을
따라 각 축마다 ⑴탐지됨(양성) ⑵탐지 안 됨(음성) 양쪽을 확인한다. 그랜드파더 만료 계약
(`_classify`)은 `ops/provenance_audit.py`(ARCH-25) 테스트 패턴을 그대로 답습한다.

실 저장소 스캔(`build_report()` 기본 인자)은 회귀 테스트 1건만 — 그 상세 분류는
`declared_unwired_audit._MANIFEST`(코드 리뷰 대상)의 소관이지 이 테스트의 소관이 아니다.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from whymath_backend.ops import declared_unwired_audit as dua


def _write_task_yaml(tasks_dir: Path, task_id: str, *, status: str) -> None:
    tasks_dir.mkdir(parents=True, exist_ok=True)
    (tasks_dir / f"{task_id}.yaml").write_text(
        yaml.safe_dump({"id": task_id, "status": status}, allow_unicode=True),
        encoding="utf-8",
    )


# ──────────────────────────────────────────────────────────────────────────
# 경로 정규화·템플릿 매칭
# ──────────────────────────────────────────────────────────────────────────


class TestPathNormalization:
    def test_server_param_normalized(self) -> None:
        assert dua.normalize_server_path("/v1/problems/{problem_id}") == "/v1/problems/{param}"

    def test_dart_interpolation_normalized(self) -> None:
        assert dua.normalize_client_path("/v1/problems/$problemId") == "/v1/problems/{param}"
        assert dua.normalize_client_path("/v1/problems/${problemId}") == "/v1/problems/{param}"

    def test_python_fstring_interpolation_normalized(self) -> None:
        assert dua.normalize_client_path("/v1/me/sessions/{jti}/end") == (
            "/v1/me/sessions/{param}/end"
        )

    def test_literal_segment_untouched(self) -> None:
        """테스트가 흔히 쓰는 리터럴 더미 값(`j1`)은 인터폴레이션이 아니므로 안 건드린다 —
        매칭은 `_route_reached`의 템플릿 정규식이 담당한다(아래 클래스)."""
        assert dua.normalize_client_path("/v1/jobs/j1") == "/v1/jobs/j1"


class TestRouteReached:
    def test_literal_dummy_id_matches_template(self) -> None:
        """`client.get('/v1/jobs/j1')`처럼 인터폴레이션 없는 리터럴 더미 ID도 서버 템플릿
        `/v1/jobs/{job_id}`에 매칭돼야 한다(과거 실패 사례 — exact-string 비교로는 놓친다)."""
        callers = frozenset({("GET", "/v1/jobs/j1")})
        assert dua._route_reached("GET", "/v1/jobs/{job_id}", callers) is True

    def test_unmatched_route_not_reached(self) -> None:
        callers = frozenset({("GET", "/v1/jobs/j1")})
        assert dua._route_reached("GET", "/v1/problems/{problem_id}", callers) is False

    def test_method_mismatch_not_reached(self) -> None:
        callers = frozenset({("POST", "/v1/problems/1")})
        assert dua._route_reached("GET", "/v1/problems/{problem_id}", callers) is False


# ──────────────────────────────────────────────────────────────────────────
# 축 1 — HTTP 호출 추출(dart·python 테스트)
# ──────────────────────────────────────────────────────────────────────────


class TestCallExtraction:
    def test_dart_dio_call_extracted(self, tmp_path: Path) -> None:
        lib = tmp_path / "lib"
        lib.mkdir()
        (lib / "api.dart").write_text(
            "class Api {\n"
            "  Future<void> call() async {\n"
            "    await _dio.get<Map<String, dynamic>>(\n"
            "      '/v1/problems/$problemId',\n"
            "    );\n"
            "  }\n"
            "}\n",
            encoding="utf-8",
        )
        entries = dua.dart_call_entries(lib)
        assert ("GET", "/v1/problems/{param}") in entries

    def test_dart_call_with_no_lib_dir_returns_empty(self, tmp_path: Path) -> None:
        assert dua.dart_call_entries(tmp_path / "missing") == frozenset()

    def test_python_test_client_call_extracted(self, tmp_path: Path) -> None:
        tests_root = tmp_path / "tests_backend"
        tests_root.mkdir()
        (tests_root / "test_x.py").write_text(
            'def test_foo(client):\n    client.get("/v1/me/sessions?limit=1")\n',
            encoding="utf-8",
        )
        entries = dua.test_call_entries(tests_root)
        assert ("GET", "/v1/me/sessions") in entries  # 쿼리스트링 제거됨

    def test_python_test_client_request_variant_extracted(self, tmp_path: Path) -> None:
        """`client.request("DELETE", "/v1/me", ...)` 변형(바디를 실어야 하는 DELETE 등)."""
        tests_root = tmp_path / "tests_backend"
        tests_root.mkdir()
        (tests_root / "test_x.py").write_text(
            "def test_foo(client):\n"
            '    client.request("DELETE", "/v1/me", json={"confirmation": "y"})\n',
            encoding="utf-8",
        )
        entries = dua.test_call_entries(tests_root)
        assert ("DELETE", "/v1/me") in entries

    def test_unrelated_dict_get_not_extracted(self, tmp_path: Path) -> None:
        """`dict.get(...)` 같은 무관 호출이 라우트로 오탐되지 않는다(접두사 제한)."""
        tests_root = tmp_path / "tests_backend"
        tests_root.mkdir()
        (tests_root / "test_x.py").write_text(
            'def test_foo(payload):\n    payload.get("something")\n',
            encoding="utf-8",
        )
        assert dua.test_call_entries(tests_root) == frozenset()


# ──────────────────────────────────────────────────────────────────────────
# 축 2 — EventType 생산자·소비자
# ──────────────────────────────────────────────────────────────────────────


class TestEventProducerConsumer:
    def test_producer_detected(self, tmp_path: Path) -> None:
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "writer.py").write_text(
            "def emit():\n" "    return build_event_data(EventType.검산결과, passed=True)\n",
            encoding="utf-8",
        )
        assert "검산결과" in dua.produced_event_types(pkg)

    def test_producer_via_variable_not_detected(self, tmp_path: Path) -> None:
        """변수로 우회한 EventType 호출은 AST 리터럴 패턴에 안 잡힌다(안전 방향 — 모듈
        docstring 명시: 그런 EventType은 미도달로 보고돼 대장 등재를 강제받는다)."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "writer.py").write_text(
            "et = EventType.검산결과\n"
            "def emit():\n"
            "    return build_event_data(et, passed=True)\n",
            encoding="utf-8",
        )
        assert "검산결과" not in dua.produced_event_types(pkg)

    def test_consumer_compare_detected(self, tmp_path: Path) -> None:
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "reader.py").write_text(
            "def q(row):\n    return row.event_type == EventType.검산결과\n",
            encoding="utf-8",
        )
        assert "검산결과" in dua.consumed_event_types(pkg)

    def test_producer_only_not_a_consumer(self, tmp_path: Path) -> None:
        """생산 좌석(`build_event_data` 첫 인자)은 `ast.Compare`가 아니므로 소비로 안 잡힌다
        — 축 2의 핵심 변별력(생산≠소비를 같은 AST 패턴으로 뭉개지 않는다)."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "writer.py").write_text(
            "def emit():\n" "    return build_event_data(EventType.막힘, turn_count=5)\n",
            encoding="utf-8",
        )
        assert "막힘" not in dua.consumed_event_types(pkg)

    def test_contract_definition_file_excluded_from_consumers(self, tmp_path: Path) -> None:
        """`enums.py`/`event_data_contract.py` 자신은 정의이지 소비가 아니다."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "event_data_contract.py").write_text(
            "MAP = {EventType.검산결과: SomeSchema}\n"
            "def q(row):\n    return row.event_type == EventType.검산결과\n",
            encoding="utf-8",
        )
        assert "검산결과" not in dua.consumed_event_types(pkg)


# ──────────────────────────────────────────────────────────────────────────
# 축 3 — 타임시리즈 writer/reader
# ──────────────────────────────────────────────────────────────────────────


def _write_timeseries_models(pkg: Path, class_names: list[str]) -> None:
    models_dir = pkg / "db" / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    (models_dir / "__init__.py").write_text("", encoding="utf-8")
    body = "\n".join(
        f"class {name}(Base):\n    __tablename__ = '{name.lower()}'\n" for name in class_names
    )
    (models_dir / "timeseries.py").write_text("class Base:\n    pass\n\n" + body, encoding="utf-8")


class TestTimeseriesUsage:
    def test_models_extracted(self, tmp_path: Path) -> None:
        pkg = tmp_path / "fakepkg"
        _write_timeseries_models(pkg, ["Foo", "Bar"])
        assert dua.timeseries_models(pkg) == ("Bar", "Foo")

    def test_writer_detected_via_constructor_call(self, tmp_path: Path) -> None:
        pkg = tmp_path / "fakepkg"
        _write_timeseries_models(pkg, ["Foo"])
        writer_dir = pkg / "writers"
        writer_dir.mkdir()
        (writer_dir / "job.py").write_text(
            "from fakepkg.db.models.timeseries import Foo\n" "def run():\n    return Foo(x=1)\n",
            encoding="utf-8",
        )
        usage = dua.timeseries_usage(pkg, ("Foo",))
        assert usage["Foo"].writers == ("writers.job",)
        assert usage["Foo"].readers == ()

    def test_reader_detected_without_constructor_call(self, tmp_path: Path) -> None:
        """`(Foo, "user_id")`처럼 생성자 호출 없이 이름만 참조하는 삭제/반출 계획 튜플도
        reader로 잡혀야 한다(writer와 구분 — 실제 erasure.py 관용구와 동형)."""
        pkg = tmp_path / "fakepkg"
        _write_timeseries_models(pkg, ["Foo"])
        reader_dir = pkg / "privacy"
        reader_dir.mkdir()
        (reader_dir / "erasure.py").write_text(
            "from fakepkg.db.models.timeseries import Foo\n" "PLAN = ((Foo, 'user_id'),)\n",
            encoding="utf-8",
        )
        usage = dua.timeseries_usage(pkg, ("Foo",))
        assert usage["Foo"].writers == ()
        assert usage["Foo"].readers == ("privacy.erasure",)

    def test_neither_writer_nor_reader_when_unreferenced(self, tmp_path: Path) -> None:
        pkg = tmp_path / "fakepkg"
        _write_timeseries_models(pkg, ["Foo"])
        usage = dua.timeseries_usage(pkg, ("Foo",))
        assert usage["Foo"].writers == ()
        assert usage["Foo"].readers == ()

    def test_schema_pydantic_namespace_collision_not_counted(self, tmp_path: Path) -> None:
        """`schema.timeseries`의 동명 Pydantic 클래스 import는 ORM 소비로 오인되지 않는다
        (`db.models`에서 온 import만 candidates로 센다)."""
        pkg = tmp_path / "fakepkg"
        _write_timeseries_models(pkg, ["Foo"])
        schema_dir = pkg / "schema"
        schema_dir.mkdir()
        (schema_dir / "timeseries.py").write_text("class Foo:\n    pass\n", encoding="utf-8")
        consumer_dir = pkg / "api"
        consumer_dir.mkdir()
        (consumer_dir / "endpoint.py").write_text(
            "from fakepkg.schema.timeseries import Foo\n" "def handler():\n    return Foo()\n",
            encoding="utf-8",
        )
        usage = dua.timeseries_usage(pkg, ("Foo",))
        assert usage["Foo"].writers == ()
        assert usage["Foo"].readers == ()


# ──────────────────────────────────────────────────────────────────────────
# 축 4 — harness/ops CLI ↔ CI/전이 import
# ──────────────────────────────────────────────────────────────────────────


class TestCliReachability:
    def _make_pkg(self, tmp_path: Path) -> Path:
        pkg = tmp_path / "fakepkg"
        (pkg / "harness").mkdir(parents=True)
        (pkg / "ops").mkdir(parents=True)
        return pkg

    def test_cli_modules_require_module_level_main(self, tmp_path: Path) -> None:
        pkg = self._make_pkg(tmp_path)
        (pkg / "harness" / "with_main.py").write_text(
            "def main():\n    return 0\n", encoding="utf-8"
        )
        (pkg / "harness" / "no_main.py").write_text(
            "def helper():\n    return 0\n", encoding="utf-8"
        )
        clis = dua.cli_modules(pkg)
        assert "harness.with_main" in clis
        assert "harness.no_main" not in clis

    def test_ci_direct_invocation_reached(self, tmp_path: Path) -> None:
        pkg = self._make_pkg(tmp_path)
        (pkg / "harness" / "gate.py").write_text("def main():\n    return 0\n", encoding="utf-8")
        clis = dua.cli_modules(pkg)
        ci_roots = frozenset({"harness.gate"})
        reached = dua.reached_clis(pkg, clis, ci_roots)
        assert "harness.gate" in reached

    def test_unreached_cli_is_not_reached(self, tmp_path: Path) -> None:
        pkg = self._make_pkg(tmp_path)
        (pkg / "harness" / "orphan.py").write_text("def main():\n    return 0\n", encoding="utf-8")
        clis = dua.cli_modules(pkg)
        reached = dua.reached_clis(pkg, clis, frozenset())
        assert "harness.orphan" not in reached

    def test_production_import_reaches_cli(self, tmp_path: Path) -> None:
        pkg = self._make_pkg(tmp_path)
        (pkg / "harness" / "metrics.py").write_text("def main():\n    return 0\n", encoding="utf-8")
        (pkg / "api").mkdir()
        (pkg / "api" / "endpoint.py").write_text(
            "from fakepkg.harness import metrics\n", encoding="utf-8"
        )
        clis = dua.cli_modules(pkg)
        reached = dua.reached_clis(pkg, clis, frozenset())
        assert "harness.metrics" in reached

    def test_transitive_in_process_import_reaches_cli(self, tmp_path: Path) -> None:
        """`qa_pipeline`류 관용구 — CI가 orchestrator만 직접 실행해도, orchestrator가
        in-process import하는 하위 CLI까지 전이 도달로 잡혀야 한다."""
        pkg = self._make_pkg(tmp_path)
        (pkg / "harness" / "sub_check.py").write_text(
            "def main():\n    return 0\n", encoding="utf-8"
        )
        (pkg / "harness" / "orchestrator.py").write_text(
            "from fakepkg.harness import sub_check\n" "def main():\n    return sub_check.main()\n",
            encoding="utf-8",
        )
        clis = dua.cli_modules(pkg)
        ci_roots = frozenset({"harness.orchestrator"})
        reached = dua.reached_clis(pkg, clis, ci_roots)
        assert "harness.orchestrator" in reached
        assert "harness.sub_check" in reached

    def test_test_only_import_does_not_reach_cli(self, tmp_path: Path) -> None:
        """스코프는 `src/backend`뿐 — 테스트 트리는 이 수집 대상 밖이라(패키지 루트 밖) 애초에
        스캔되지 않는다는 사실 자체가 계약이다(별도 `tests/`를 package_root로 넘기지 않는 한
        아예 보이지 않는다 — 여기선 패키지 안에 아무 것도 import하지 않는 구성으로 대체 확인)."""
        pkg = self._make_pkg(tmp_path)
        (pkg / "harness" / "only_tested.py").write_text(
            "def main():\n    return 0\n", encoding="utf-8"
        )
        clis = dua.cli_modules(pkg)
        reached = dua.reached_clis(pkg, clis, frozenset())
        assert "harness.only_tested" not in reached


# ──────────────────────────────────────────────────────────────────────────
# 분류(그랜드파더 만료 계약) — ARCH-25 패턴 이식
# ──────────────────────────────────────────────────────────────────────────


class TestClassify:
    def test_reached_with_no_manifest_entry_is_reached(self, tmp_path: Path) -> None:
        verdict = dua._classify("axis", "key", True, tmp_path)
        assert verdict.status == "reached"

    def test_unreached_with_no_manifest_entry_is_unclassified(self, tmp_path: Path) -> None:
        verdict = dua._classify("axis", "key", False, tmp_path)
        assert verdict.status == "unclassified"
        assert verdict.is_violation is True

    def test_reached_with_manifest_entry_is_stale_waiver(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setitem(dua._MANIFEST, "axis", {"key": "by-design:테스트"})
        verdict = dua._classify("axis", "key", True, tmp_path)
        assert verdict.status == "stale-waiver"
        assert verdict.is_violation is True

    def test_by_design_with_empty_reason_is_missing_reason(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setitem(dua._MANIFEST, "axis", {"key": "by-design:"})
        verdict = dua._classify("axis", "key", False, tmp_path)
        assert verdict.status == "missing-reason"
        assert verdict.is_violation is True

    def test_pending_task_nonexistent_is_expired_waiver(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setitem(dua._MANIFEST, "axis", {"key": "pending-task:NONEXISTENT-XYZ"})
        verdict = dua._classify("axis", "key", False, tmp_path)
        assert verdict.status == "expired-waiver"
        assert verdict.is_violation is True

    def test_pending_task_done_is_expired_waiver(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _write_task_yaml(tmp_path, "FAKE-DONE", status="done")
        monkeypatch.setitem(dua._MANIFEST, "axis", {"key": "pending-task:FAKE-DONE"})
        verdict = dua._classify("axis", "key", False, tmp_path)
        assert verdict.status == "expired-waiver"
        assert verdict.is_violation is True

    def test_pending_task_open_is_valid_waiver(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _write_task_yaml(tmp_path, "FAKE-TODO", status="todo")
        monkeypatch.setitem(dua._MANIFEST, "axis", {"key": "pending-task:FAKE-TODO"})
        verdict = dua._classify("axis", "key", False, tmp_path)
        assert verdict.status == "pending-task"
        assert verdict.is_violation is False


# ──────────────────────────────────────────────────────────────────────────
# 수집기 파손 방어(exit 2)
# ──────────────────────────────────────────────────────────────────────────


class TestCollectorFloorGuard:
    def test_below_floor_raises_collector_error(self, tmp_path: Path) -> None:
        """실 저장소가 아닌 빈 루트를 넘기면(라우트·CLI 등 전 축 0건) `CollectorError`가 나야
        한다 — '0건 통과'로 위장하지 않는다. `create_app()`은 실 앱을 그대로 쓰므로 라우트
        축은 항상 하한을 넘긴다(수집기 파손 조건은 dart/test 호출·CLI·타임시리즈 축에서
        인위적으로 재현한다)."""
        empty_root = tmp_path / "empty_repo"
        (empty_root / "src" / "backend" / "whymath_backend").mkdir(parents=True)
        (empty_root / "backlog" / "tasks").mkdir(parents=True)
        with pytest.raises(dua.CollectorError):
            dua.build_report(empty_root)


# ──────────────────────────────────────────────────────────────────────────
# 실 저장소 회귀 — 상세 분류는 `_MANIFEST`(코드 리뷰) 소관, 여기선 exit 0만 고정.
# ──────────────────────────────────────────────────────────────────────────


class TestRealRepositoryReport:
    def test_real_repo_report_passes(self) -> None:
        report = dua.build_report()
        assert report.exit_code == 0, [v.to_json() for v in report.violations]
