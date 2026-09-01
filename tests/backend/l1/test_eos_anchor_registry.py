"""EOS 앵커 세트 1급 등록 — 무결성 게이트 (EOS-56 acceptance ②).

이 테스트가 막는 것
-------------------
앵커는 12월 검증의 **조인 축**이다 — 성취기준 코드가 사라지거나 개정되면 원자·오개념·문항
집계가 조용히 0으로 떨어지고, 리포트는 "자산 없음"을 정상 출력으로 낸다. 코드 소멸을 소리내는
장치가 없으면 그 무증상 붕괴가 12월 판정까지 발견되지 않는다. 그래서 앵커 코드 전건이 성취기준
코퍼스에 실재하는지를 매 PR 검사한다(코드 소멸 = 적색).

트리거 배선 (이 테스트가 *실제로 도는가*)
------------------------------------------
`.github/workflows/ci.yml`의 backend 경로 필터에 `data/corpus/`가 포함돼 있으므로, 성취기준
코퍼스 단독 수정 PR에서도 backend 잡이 깨어나 이 테스트가 실행된다 — 게이트가 자기 입력 변경에
깨어난다. 그 배선 자체를 `TestCiTriggerWiring`이 파일에서 읽어 단언한다(주석의 주장이 아니라
기계 검사 — "검증 장치를 만들고 배선 확인 없이 완료 선언 금지").

변별력
------
`TestGateDiscrimination`이 뮤테이션(코드 1건 삭제·중복 귀속·scope 오타·코퍼스 0건)으로
"실패 상태에서 실제로 실패하는가"를 실측한다. 성공·실패 양쪽에서 같은 값을 내는 검사는 검증이
아니라 위장이다(2026-07-17 logconfig 선례).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import yaml

from whymath_backend.l1.standards.anchor_registry import (
    SCOPE_DECEMBER_2026,
    SCOPE_DEFERRED_2027_01,
    AnchorRegistryError,
    load_anchor_registry,
    load_standards_codes,
    main,
    verify_codes_exist,
)

# tests/backend/l1/<이 파일> 기준 3단계 위가 레포 루트.
_REPO_ROOT = Path(__file__).resolve().parents[3]
_REGISTRY_PATH = _REPO_ROOT / "data/corpus/eos_anchor_set_v1/anchors.yaml"
_SIDECAR_PATH = _REPO_ROOT / "data/corpus/eos_anchor_set_v1/_provenance.json"
_CI_WORKFLOW = _REPO_ROOT / ".github/workflows/ci.yml"
_DESIGN_DOC = _REPO_ROOT / "docs/standards/eos_verification_design_v1.md"


@pytest.fixture(scope="module")
def registry():
    return load_anchor_registry(_REGISTRY_PATH)


class TestCodeExistenceGate:
    """acceptance ② — 앵커 코드가 성취기준 데이터에 실재하는가(코드 소멸 시 적색)."""

    def test_every_anchor_code_exists_in_standards_corpus(self, registry) -> None:
        known = load_standards_codes(registry, repo_root=_REPO_ROOT)
        violations = verify_codes_exist(registry, known)
        assert not violations, "앵커 동결 코드가 성취기준 코퍼스에서 사라졌다:\n" + "\n".join(
            violations
        )

    def test_standards_index_is_not_silently_empty(self, registry) -> None:
        """색인 0건은 '위반 없음'이 아니라 '읽기 실패'다 — 상시 green 위장 차단."""
        known = load_standards_codes(registry, repo_root=_REPO_ROOT)
        assert len(known) > 100, f"성취기준 색인이 비정상적으로 작다({len(known)}건)"

    def test_cli_exits_zero_on_healthy_registry(self, capsys) -> None:
        """판정은 exit 0/1 — 인상 판정 금지(CLAUDE.md 검증 권위)."""
        assert main(["--registry", str(_REGISTRY_PATH)]) == 0
        assert "판정: 통과" in capsys.readouterr().out


class TestG0FreezeInvariants:
    """acceptance ① — G0 서명(2026-08-30)이 확정한 세트가 그대로 등록됐는가."""

    def test_frozen_provenance_points_at_the_signing_gate(self, registry) -> None:
        assert registry.frozen_by_gate == "G-eos-g0-verification-design-freeze"
        assert registry.frozen_at == "2026-08-30"
        assert registry.design_doc == "docs/standards/eos_verification_design_v1.md"
        assert (_REPO_ROOT / registry.design_doc).exists()

    def test_december_scope_is_exactly_the_six_confirmed_anchors(self, registry) -> None:
        december = registry.in_scope(SCOPE_DECEMBER_2026)
        assert [a.id for a in december] == ["A1", "A2", "A3", "A4", "A5", "A6"]

    def test_university_anchors_are_deferred_not_deleted(self, registry) -> None:
        """이월은 삭제가 아니다 — 지우면 '왜 빠졌는가'의 근거가 사라진다(옵션 ② 명시 손실)."""
        deferred = registry.in_scope(SCOPE_DEFERRED_2027_01)
        assert [a.id for a in deferred] == ["A7", "A8"]

    def test_cu_volume_matches_signed_design_table(self, registry) -> None:
        """§2 표의 생산 450 · 검수 185 — 물량이 바뀌면 시간 예산 재검산이 필요하다."""
        december = registry.in_scope(SCOPE_DECEMBER_2026)
        assert sum(a.production_cu or 0 for a in december) == 450
        assert sum(a.review_cu or 0 for a in december) == 185

    def test_baseline_and_depth_anchors(self, registry) -> None:
        """F-Ⅰ(기준선 A3·A4)·깊이 폐쇄루프(A4) 판정 대상의 데이터화."""
        assert {a.id for a in registry.anchors if a.baseline} == {"A3", "A4"}
        assert {a.id for a in registry.anchors if a.depth} == {"A4"}

    def test_two_anchors_per_school_level(self, registry) -> None:
        """학교급당 2개 원칙 — n=1이면 '학교급이 어려운 것'과 '단원이 어려운 것'을 구분 불가."""
        counts: dict[str, int] = {}
        for a in registry.in_scope(SCOPE_DECEMBER_2026):
            counts[a.school_level] = counts.get(a.school_level, 0) + 1
        assert counts == {"초등": 2, "중등": 2, "고등": 2}

    def test_no_code_belongs_to_two_anchors(self, registry) -> None:
        """조인 축의 대전제 — 중복 귀속은 자산 이중 계상이다."""
        codes = registry.all_codes()
        assert len(set(codes)) == len(codes)

    def test_excluded_boundaries_carry_reasons(self, registry) -> None:
        """제외 경계는 사유와 함께 데이터로 남는다(재현 가능성)."""
        a4 = registry.by_id("A4")
        assert "[9수02-19]" in a4.excluded  # 인수분해 — 선수 소단원
        assert all(reason.strip() for reason in a4.excluded.values())

    def test_reverse_index_joins_code_to_anchor(self, registry) -> None:
        assert registry.anchor_for_code("[9수02-20]").id == "A4"
        assert registry.anchor_for_code("[존재하지-않는-코드]") is None


class TestCorpusHygiene:
    """코퍼스 관례 — 사이드카(pool·서지)와 단방향(YAML=소스) 표기."""

    def test_provenance_sidecar_declares_pool_and_citation(self) -> None:
        payload = json.loads(_SIDECAR_PATH.read_text(encoding="utf-8"))
        assert payload["pool"] == "whymath-original"
        assert payload["source_citation"].strip()
        assert payload["counts"]["anchors"] == 8
        assert payload["counts"]["december_2026"] == 6

    def test_sidecar_counts_match_the_registry(self, registry) -> None:
        """사이드카 숫자가 레지스트리와 어긋나면 감사 산출물이 거짓말을 한다."""
        payload = json.loads(_SIDECAR_PATH.read_text(encoding="utf-8"))
        counts = payload["counts"]
        assert counts["anchors"] == len(registry.anchors)
        assert counts["december_2026"] == len(registry.in_scope(SCOPE_DECEMBER_2026))
        assert counts["deferred_2027_01"] == len(registry.in_scope(SCOPE_DEFERRED_2027_01))
        assert counts["codes"] == len(registry.all_codes())
        assert counts["codes_december_2026"] == sum(
            len(a.codes) for a in registry.in_scope(SCOPE_DECEMBER_2026)
        )


class TestAuditScriptReadsTheRegistry:
    """acceptance ③ 집행 — EOS-52 실사 스크립트가 하드코딩 상수 대신 등록을 읽는가."""

    _SCRIPT = _REPO_ROOT / "scripts/analysis/eos_anchor_asset_audit.py"

    def test_hardcoded_anchor_defs_literal_is_gone(self) -> None:
        source = self._SCRIPT.read_text(encoding="utf-8")
        assert (
            "ANCHOR_DEFS: tuple[dict[str, Any], ...] = (" not in source
        ), "앵커 정의가 스크립트 상수로 되살아났다 — 이중 진실 원천"

    def test_script_loads_the_registry_file(self) -> None:
        source = self._SCRIPT.read_text(encoding="utf-8")
        assert "eos_anchor_set_v1/anchors.yaml" in source

    def test_script_anchor_defs_match_the_registry(self, registry) -> None:
        """스크립트가 읽은 결과와 레지스트리가 같은 코드셋인가(이관 무손실)."""
        import importlib.util

        spec = importlib.util.spec_from_file_location("_eos_audit", self._SCRIPT)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        loaded = {a["id"]: tuple(a["codes"]) for a in module.ANCHOR_DEFS}
        assert loaded == {a.id: a.codes for a in registry.anchors}


class TestCiTriggerWiring:
    """게이트가 자기 입력 변경에 깨어나는가 — 주석이 아니라 파일에서 읽어 단언한다."""

    def test_corpus_changes_trigger_the_backend_job(self) -> None:
        workflow = _CI_WORKFLOW.read_text(encoding="utf-8")
        backend_filter = re.search(
            r"grep -qE '\^\((?P<pat>[^']*)\)'\s*;\s*then\s*\n\s*be=true", workflow
        )
        assert backend_filter, "ci.yml backend 경로 필터를 찾지 못함 — 배선 검사 자체가 무효"
        pattern = backend_filter.group("pat")
        assert "data/corpus/" in pattern, (
            "backend 잡이 data/corpus/ 변경에 깨어나지 않는다 — 성취기준 코퍼스 단독 수정 PR에서 "
            "이 게이트가 SKIP되고 skip은 required check에서 충족으로 계상된다"
        )
        assert "tests/backend/" in pattern


class TestGateDiscrimination:
    """뮤테이션 — 실패 상태에서 *실제로* 실패하는지 실측(변별력 없는 검증 스텝 금지)."""

    @staticmethod
    def _mutate(tmp_path: Path, mutate) -> Path:
        doc = yaml.safe_load(_REGISTRY_PATH.read_text(encoding="utf-8"))
        mutate(doc)
        target = tmp_path / "anchors.yaml"
        target.write_text(
            yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), encoding="utf-8"
        )
        return target

    def test_missing_standard_code_is_detected(self, registry, tmp_path) -> None:
        """코드 소멸 = 이 게이트의 존재 이유 — 없는 코드를 넣으면 반드시 위반이 잡힌다."""
        path = self._mutate(tmp_path, lambda d: d["anchors"][3]["codes"].append("[9수99-99]"))
        mutated = load_anchor_registry(path)
        known = load_standards_codes(mutated, repo_root=_REPO_ROOT)
        violations = verify_codes_exist(mutated, known)
        assert any("[9수99-99]" in v for v in violations)

    def test_cli_exits_one_on_violation(self, tmp_path) -> None:
        path = self._mutate(tmp_path, lambda d: d["anchors"][0]["codes"].append("[4수99-99]"))
        assert main(["--registry", str(path)]) == 1

    def test_duplicate_code_across_anchors_is_rejected(self, tmp_path) -> None:
        path = self._mutate(tmp_path, lambda d: d["anchors"][1]["codes"].append("[4수01-09]"))
        with pytest.raises(AnchorRegistryError, match="중복 귀속"):
            load_anchor_registry(path)

    def test_unknown_scope_is_rejected(self, tmp_path) -> None:
        path = self._mutate(
            tmp_path, lambda d: d["anchors"][0].__setitem__("scope", "december2026")
        )
        with pytest.raises(AnchorRegistryError, match="scope"):
            load_anchor_registry(path)

    def test_excluded_code_may_not_also_be_included(self, tmp_path) -> None:
        path = self._mutate(tmp_path, lambda d: d["anchors"][3]["codes"].append("[9수02-19]"))
        with pytest.raises(AnchorRegistryError, match="포함·제외"):
            load_anchor_registry(path)

    def test_missing_required_field_is_explicit_failure(self, tmp_path) -> None:
        path = self._mutate(tmp_path, lambda d: d["anchors"][0].pop("baseline"))
        with pytest.raises(AnchorRegistryError, match="baseline"):
            load_anchor_registry(path)

    def test_absent_registry_file_raises_with_exception_type(self, tmp_path) -> None:
        """부재를 '앵커 0건·위반 없음'으로 통과시키지 않는다(침묵 실패 금지)."""
        with pytest.raises(AnchorRegistryError, match="FileNotFoundError"):
            load_anchor_registry(tmp_path / "nope.yaml")

    def test_empty_standards_corpus_raises_instead_of_passing(self, registry, tmp_path) -> None:
        """코퍼스가 비면 '위반 0건 통과'가 아니라 명시 실패여야 한다(게이트 무력화 방지)."""
        fake_root = tmp_path / "root"
        for rel, _rev in registry.standards_sources:
            target = fake_root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps({"standards": []}), encoding="utf-8")
        with pytest.raises(AnchorRegistryError, match="0건"):
            load_standards_codes(registry, repo_root=fake_root)

    def test_revision_filter_rejects_2015_only_codes(self, registry, tmp_path) -> None:
        """2015 개정 행이 앵커를 살려 주면 드리프트가 은폐된다 — 필터가 실제로 거른다."""
        fake_root = tmp_path / "root"
        first_rel, _ = registry.standards_sources[0]
        target = fake_root / first_rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps({"standards": [{"code": "[4수01-09]", "curriculum_revision": "2015 개정"}]}),
            encoding="utf-8",
        )
        for rel, _rev in registry.standards_sources[1:]:
            other = fake_root / rel
            other.parent.mkdir(parents=True, exist_ok=True)
            other.write_text(json.dumps({"standards": []}), encoding="utf-8")
        with pytest.raises(AnchorRegistryError, match="0건"):
            load_standards_codes(registry, repo_root=fake_root)


class TestLoaderFailurePaths:
    """실패 경로 설계 — 깨진 입력이 '앵커 0건 정상'으로 통과하지 않는다.

    측정·수집 도구를 성공 경로만 보고 설계하지 않는다(CLAUDE.md 2026-08-22). 각 실패는 예외
    타입명·원인을 메시지에 남긴다 — 무타입 경고는 8개의 서로 다른 실패를 같은 글자로 보이게 한다.
    """

    @staticmethod
    def _write(tmp_path: Path, text: str) -> Path:
        path = tmp_path / "anchors.yaml"
        path.write_text(text, encoding="utf-8")
        return path

    def test_malformed_yaml_reports_exception_type(self, tmp_path: Path) -> None:
        path = self._write(tmp_path, "anchors: [\n  - id: A1\n   bad indent\n")
        with pytest.raises(AnchorRegistryError, match="YAML 파싱 실패"):
            load_anchor_registry(path)

    def test_top_level_must_be_a_mapping(self, tmp_path: Path) -> None:
        with pytest.raises(AnchorRegistryError, match="매핑이 아니다"):
            load_anchor_registry(self._write(tmp_path, "- A1\n- A2\n"))

    def test_empty_anchor_list_is_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(AnchorRegistryError, match="anchors가 비어"):
            load_anchor_registry(self._write(tmp_path, "anchors: []\n"))

    def test_anchor_entry_must_be_a_mapping(self, tmp_path: Path) -> None:
        with pytest.raises(AnchorRegistryError, match="매핑이 아니다"):
            load_anchor_registry(self._write(tmp_path, "anchors:\n  - A1\n"))

    def test_duplicate_anchor_id_is_rejected(self, registry, tmp_path: Path) -> None:
        doc = yaml.safe_load(_REGISTRY_PATH.read_text(encoding="utf-8"))
        doc["anchors"][1]["id"] = "A1"
        doc["anchors"][1]["codes"] = ["[6수02-02]"]
        path = tmp_path / "anchors.yaml"
        path.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), encoding="utf-8")
        with pytest.raises(AnchorRegistryError, match="id 중복"):
            load_anchor_registry(path)

    def test_excluded_reason_may_not_be_blank(self, registry, tmp_path: Path) -> None:
        doc = yaml.safe_load(_REGISTRY_PATH.read_text(encoding="utf-8"))
        doc["anchors"][0]["excluded"]["[4수01-12]"] = "   "
        path = tmp_path / "anchors.yaml"
        path.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), encoding="utf-8")
        with pytest.raises(AnchorRegistryError, match="제외 사유"):
            load_anchor_registry(path)

    def test_standards_sources_are_required(self, registry, tmp_path: Path) -> None:
        doc = yaml.safe_load(_REGISTRY_PATH.read_text(encoding="utf-8"))
        doc["standards_sources"] = []
        path = tmp_path / "anchors.yaml"
        path.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), encoding="utf-8")
        with pytest.raises(AnchorRegistryError, match="standards_sources"):
            load_anchor_registry(path)

    def test_unreadable_standards_corpus_reports_exception_type(
        self, registry, tmp_path: Path
    ) -> None:
        with pytest.raises(AnchorRegistryError, match="FileNotFoundError"):
            load_standards_codes(registry, repo_root=tmp_path / "absent")

    def test_standards_payload_without_array_is_explicit_failure(
        self, registry, tmp_path: Path
    ) -> None:
        fake_root = tmp_path / "root"
        first_rel, _ = registry.standards_sources[0]
        target = fake_root / first_rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps({"rows": []}), encoding="utf-8")
        with pytest.raises(AnchorRegistryError, match="standards"):
            load_standards_codes(registry, repo_root=fake_root)

    def test_unknown_id_lookup_raises(self, registry) -> None:
        with pytest.raises(KeyError):
            registry.by_id("A99")

    def test_unknown_scope_filter_raises(self, registry) -> None:
        with pytest.raises(AnchorRegistryError, match="scope"):
            registry.in_scope("2027")

    def test_cli_reports_load_failure_as_exit_one(self, tmp_path: Path, capsys) -> None:
        """적재 실패를 exit 0으로 가리지 않는다 — 측정 실패는 측정 실패로 보여야 한다."""
        assert main(["--registry", str(tmp_path / "absent.yaml")]) == 1
        assert "적재 실패" in capsys.readouterr().err

    def test_cli_json_output_is_machine_readable(self, capsys) -> None:
        assert main(["--registry", str(_REGISTRY_PATH), "--json"]) == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["anchors_december_2026"] == 6
        assert payload["violations"] == []

    def test_december_scope_flag_on_anchor(self, registry) -> None:
        assert registry.by_id("A4").is_december_scope
        assert not registry.by_id("A7").is_december_scope
