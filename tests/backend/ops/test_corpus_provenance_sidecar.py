"""코퍼스 사이드카 생성·갱신 CLI hermetic 테스트 — PB-11.

전부 `tmp_path`에서 돈다(실 `data/corpus` 26개 사이드카는 읽기조차 하지 않는다 — 이 태스크의
범위는 "도구만 만든다"였다). 검증 축:

① **변별력 방향 1** — 사이드카 없는 코퍼스에 CLI를 돌리면 `provenance_audit`이 exit 1 → 0.
② **변별력 방향 2** — `pool`이 든 기존 사이드카에 재실행해도 `pool`이 살아남고(비파괴),
   같은 인자 재실행은 바이트가 동일하다(멱등 — `unchanged`).
③ 비파괴의 세부: 지정하지 않은 자유 필드·키 순서 보존, `--overwrite`는 명시했을 때만 파괴.
④ 거부 경로: `pool` 무단 변경(exit 2) · `pool` 없이 신규 생성(exit 1·파일 미생성) · 서지 정보
   0건(exit 1) · 손상된 기존 JSON(exit 2·예외 타입명 포함) · 잘못된 `--set`/`--pool`.
⑤ `--dry-run`은 아무 파일도 만들지 않는다.

①②는 `data_pipeline`의 `_write_provenance()`가 실측으로 **둘 다 실패하는** 지점이다(PB-11
acceptance ② — payload에 `pool` 없음 / `write_text` 통째 덮어쓰기). 성공·실패 양쪽에서 같은 값을
내면 위장이므로, 두 방향 모두 "고치기 전 상태"를 같은 테스트 안에서 함께 단언한다.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from whymath_backend.ops import corpus_provenance_sidecar as cps
from whymath_backend.ops import provenance_audit as pa

# 실 사이드카(`data/corpus/skill_graph_v1/_provenance.json`)의 키 구성을 그대로 본뜬 픽스처 —
# ARCH-20이 손으로 백필한 `pool` + 코퍼스별 자유 서술이 섞인 상태가 비파괴 계약의 실제 대상이다.
_EXISTING_SIDECAR: dict[str, object] = {
    "pool": "whymath-original",
    "source_file": "skills.jsonl",
    "source_sha256": "0" * 64,
    "source_citation": "행동영역·스킬 택소노미: 와이매스 자체작성(성취기준 본문 미포함).",
    "counts": {"skills": 27, "families": 16},
    "validation": {"success": True, "errors": 0},
    "skipped": [],
    "determinism": "결정론 — 동일 sha256 입력 2회 transform 시 byte 동일 산출",
}


def _corpus(tmp_path: Path, name: str = "corpus_a") -> Path:
    corpus_dir = tmp_path / name
    corpus_dir.mkdir(parents=True, exist_ok=True)
    return corpus_dir


def _write_existing(corpus_dir: Path, payload: dict[str, object]) -> Path:
    path = corpus_dir / cps.SIDECAR_FILENAME
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _read(path: Path) -> dict[str, object]:
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


class TestDiscriminatingPowerAuditFlips:
    """변별력 방향 1 — 게이트 판정이 CLI 하나로 exit 1에서 0으로 바뀐다."""

    def test_audit_exit_1_before_and_0_after_cli(self, tmp_path: Path) -> None:
        corpus_dir = _corpus(tmp_path, "newcorpus_v1")

        before = pa.audit_corpus_root(tmp_path)
        assert before.exit_code == 1, "사이드카 없는 코퍼스가 통과하면 게이트 자체가 무력하다"
        assert before.violations[0].kind == "SIDECAR_MISSING"

        exit_code = cps.main(
            [
                str(corpus_dir),
                "--pool",
                "whymath-original",
                "--source-citation",
                "와이매스 자체작성(원문 미포함).",
            ]
        )
        assert exit_code == 0

        after = pa.audit_corpus_root(tmp_path)
        assert after.exit_code == 0, f"CLI 산출물이 계약을 못 만족했다: {after.violations}"
        assert after.violations == []

    def test_created_sidecar_satisfies_minimum_contract(self, tmp_path: Path) -> None:
        """최소 계약 = `pool` + (`source_citation` | `license_notice`) 중 1건.

        `license_notice`만 준 경로도(그래프 계열이 아니라 오개념 크로스링크 계열의 실제 형태)
        똑같이 통과해야 한다.
        """
        corpus_dir = _corpus(tmp_path, "notice_only_v1")
        assert (
            cps.main(
                [
                    str(corpus_dir),
                    "--pool",
                    "external-sharealike",
                    "--license-notice",
                    "CC BY-SA 4.0",
                ]
            )
            == 0
        )
        payload = _read(corpus_dir / cps.SIDECAR_FILENAME)
        assert payload["pool"] == "external-sharealike"
        assert payload["license_notice"] == "CC BY-SA 4.0"
        assert pa.audit_corpus_root(tmp_path).exit_code == 0


class TestDiscriminatingPowerPoolSurvives:
    """변별력 방향 2 — 기존 `pool`이 재실행에 살아남고 바이트가 안정적이다(멱등·비파괴).

    `data_pipeline._write_provenance()`가 정확히 여기서 실패한다(통째 덮어쓰기 → `pool` 소실).
    """

    def test_pool_survives_rerun_without_pool_argument(self, tmp_path: Path) -> None:
        corpus_dir = _corpus(tmp_path)
        path = _write_existing(corpus_dir, _EXISTING_SIDECAR)

        assert cps.main([str(corpus_dir), "--license-notice", "CC BY 4.0"]) == 0

        payload = _read(path)
        assert payload["pool"] == "whymath-original", "재실행에 pool이 소실됐다 — 비파괴 계약 위반"
        assert payload["license_notice"] == "CC BY 4.0"
        assert pa.audit_corpus_root(tmp_path).exit_code == 0

    def test_rerun_is_byte_identical(self, tmp_path: Path) -> None:
        corpus_dir = _corpus(tmp_path)
        path = _write_existing(corpus_dir, _EXISTING_SIDECAR)
        args = [str(corpus_dir), "--license-notice", "CC BY 4.0"]

        assert cps.main(args) == 0
        first = path.read_bytes()
        assert cps.main(args) == 0
        assert path.read_bytes() == first, "같은 인자 재실행이 바이트를 바꿨다 — 멱등 위반"

    def test_unspecified_free_fields_and_key_order_preserved(self, tmp_path: Path) -> None:
        """지정하지 않은 자유 서술(코퍼스별 감사 이력)은 건드리지 않고, 키 순서도 보존한다."""
        corpus_dir = _corpus(tmp_path)
        path = _write_existing(corpus_dir, _EXISTING_SIDECAR)

        assert cps.main([str(corpus_dir), "--license-notice", "CC BY 4.0"]) == 0

        payload = _read(path)
        for key in ("source_file", "source_sha256", "counts", "validation", "determinism"):
            assert payload[key] == _EXISTING_SIDECAR[key], f"{key} 가 변형됐다"
        # 신규 키는 뒤에 붙고 기존 순서는 그대로 — diff 최소화(자유 서술 재배열 금지).
        assert list(payload)[: len(_EXISTING_SIDECAR)] == list(_EXISTING_SIDECAR)
        assert list(payload)[-1] == "license_notice"

    def test_same_pool_value_explicitly_given_is_not_a_change(self, tmp_path: Path) -> None:
        corpus_dir = _corpus(tmp_path)
        path = _write_existing(corpus_dir, _EXISTING_SIDECAR)
        before = path.read_bytes()
        assert cps.main([str(corpus_dir), "--pool", "whymath-original"]) == 0
        assert path.read_bytes() == before


class TestOverwriteIsOptIn:
    """`--overwrite`(파괴적)는 명시했을 때만 동작한다 — 기본값은 병합."""

    def test_default_merge_keeps_other_keys(self, tmp_path: Path) -> None:
        corpus_dir = _corpus(tmp_path)
        path = _write_existing(corpus_dir, _EXISTING_SIDECAR)
        assert cps.main([str(corpus_dir), "--source-citation", "새 출처"]) == 0
        assert "counts" in _read(path)

    def test_overwrite_flag_drops_unspecified_keys(self, tmp_path: Path) -> None:
        corpus_dir = _corpus(tmp_path)
        path = _write_existing(corpus_dir, _EXISTING_SIDECAR)
        assert (
            cps.main(
                [
                    str(corpus_dir),
                    "--overwrite",
                    "--pool",
                    "whymath-original",
                    "--source-citation",
                    "새 출처",
                ]
            )
            == 0
        )
        payload = _read(path)
        assert payload == {"pool": "whymath-original", "source_citation": "새 출처"}

    def test_overwrite_allows_pool_change_without_extra_flag(self, tmp_path: Path) -> None:
        """`--overwrite`는 payload를 통째로 버리므로 pool 변경 가드가 적용되지 않는다
        (명시적 파괴 요구가 이미 있으므로 이중 확인을 요구하지 않는다 — 문서화된 동작)."""
        corpus_dir = _corpus(tmp_path)
        path = _write_existing(corpus_dir, _EXISTING_SIDECAR)
        assert (
            cps.main(
                [
                    str(corpus_dir),
                    "--overwrite",
                    "--pool",
                    "external-licensed",
                    "--license-notice",
                    "협상 타결분",
                ]
            )
            == 0
        )
        assert _read(path)["pool"] == "external-licensed"


class TestPoolChangeGuard:
    def test_pool_change_refused_by_default(self, tmp_path: Path) -> None:
        corpus_dir = _corpus(tmp_path)
        path = _write_existing(corpus_dir, _EXISTING_SIDECAR)
        assert cps.main([str(corpus_dir), "--pool", "external-sharealike"]) == 2
        assert _read(path)["pool"] == "whymath-original", "거부인데 파일이 바뀌었다"

    def test_pool_change_allowed_with_explicit_flag(self, tmp_path: Path) -> None:
        corpus_dir = _corpus(tmp_path)
        path = _write_existing(corpus_dir, _EXISTING_SIDECAR)
        assert (
            cps.main([str(corpus_dir), "--pool", "external-sharealike", "--allow-pool-change"]) == 0
        )
        assert _read(path)["pool"] == "external-sharealike"


class TestContractViolationsRefuseToWrite:
    def test_new_sidecar_without_pool_is_refused(self, tmp_path: Path) -> None:
        corpus_dir = _corpus(tmp_path)
        assert cps.main([str(corpus_dir), "--source-citation", "출처만"]) == 1
        assert not (corpus_dir / cps.SIDECAR_FILENAME).exists(), "거부인데 파일을 만들었다"

    def test_no_bibliographic_field_is_refused(self, tmp_path: Path) -> None:
        """`pool`만 있고 서지 정보 0건이면 계약 위반(exit 1) — 계약은 schema가 판정한다."""
        corpus_dir = _corpus(tmp_path)
        assert cps.main([str(corpus_dir), "--pool", "whymath-original"]) == 1
        assert not (corpus_dir / cps.SIDECAR_FILENAME).exists()

    def test_existing_sidecar_left_intact_on_contract_violation(self, tmp_path: Path) -> None:
        """계약을 깨는 갱신(`--overwrite`로 서지 정보를 날리는 시도)은 기존 파일을 남긴다."""
        corpus_dir = _corpus(tmp_path)
        path = _write_existing(corpus_dir, _EXISTING_SIDECAR)
        before = path.read_bytes()
        assert cps.main([str(corpus_dir), "--overwrite", "--pool", "whymath-original"]) == 1
        assert path.read_bytes() == before


class TestInputErrors:
    def test_missing_directory_is_input_error(self, tmp_path: Path) -> None:
        assert cps.main([str(tmp_path / "nope"), "--pool", "whymath-original"]) == 2

    def test_corrupt_existing_json_is_input_error_with_exception_type(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """손상된 사이드카를 조용히 덮지 않고, 예외 타입명을 남긴다(CLAUDE.md 침묵 실패 금지)."""
        corpus_dir = _corpus(tmp_path)
        path = corpus_dir / cps.SIDECAR_FILENAME
        path.write_text("{not valid json", encoding="utf-8")

        assert cps.main([str(corpus_dir), "--pool", "whymath-original"]) == 2
        assert path.read_text(encoding="utf-8") == "{not valid json"
        assert "JSONDecodeError" in capsys.readouterr().err

    def test_overwrite_can_repair_corrupt_json(self, tmp_path: Path) -> None:
        """`--overwrite`는 손상된 사이드카를 고치는 **유일한 CLI 경로**다(안내 문구와 동작 일치).

        기본 경로가 exit 2로 거부하는 바로 그 입력에 `--overwrite`만 더해 성공하는지 확인한다 —
        거부 메시지가 안내하는 탈출구가 실제로 열려 있지 않으면 그 안내는 빈말이다.
        """
        corpus_dir = _corpus(tmp_path)
        path = corpus_dir / cps.SIDECAR_FILENAME
        path.write_text("{not valid json", encoding="utf-8")

        assert (
            cps.main(
                [
                    str(corpus_dir),
                    "--overwrite",
                    "--pool",
                    "whymath-original",
                    "--source-citation",
                    "복구본 출처",
                ]
            )
            == 0
        )
        assert _read(path) == {"pool": "whymath-original", "source_citation": "복구본 출처"}
        assert pa.audit_corpus_root(tmp_path).exit_code == 0

    def test_non_object_existing_sidecar_is_input_error(self, tmp_path: Path) -> None:
        corpus_dir = _corpus(tmp_path)
        (corpus_dir / cps.SIDECAR_FILENAME).write_text("[1, 2, 3]", encoding="utf-8")
        assert cps.main([str(corpus_dir), "--pool", "whymath-original"]) == 2

    def test_invalid_pool_value_rejected_by_argparse(self, tmp_path: Path) -> None:
        """자유 문자열 pool 금지 — `ContentPool` 3종 폐쇄(argparse choices에서 거부)."""
        corpus_dir = _corpus(tmp_path)
        with pytest.raises(SystemExit) as excinfo:
            cps.main([str(corpus_dir), "--pool", "내가-만든-풀"])
        assert excinfo.value.code == 2
        assert not (corpus_dir / cps.SIDECAR_FILENAME).exists()

    def test_malformed_set_option_is_input_error(self, tmp_path: Path) -> None:
        corpus_dir = _corpus(tmp_path)
        assert cps.main([str(corpus_dir), "--pool", "whymath-original", "--set", "키만"]) == 2

    def test_set_cannot_write_contract_fields(self, tmp_path: Path) -> None:
        corpus_dir = _corpus(tmp_path)
        assert (
            cps.main([str(corpus_dir), "--pool", "whymath-original", "--set", "pool=아무거나"]) == 2
        )


class TestSetOption:
    def test_json_value_parsed_and_plain_string_kept(self, tmp_path: Path) -> None:
        corpus_dir = _corpus(tmp_path)
        assert (
            cps.main(
                [
                    str(corpus_dir),
                    "--pool",
                    "whymath-original",
                    "--source-citation",
                    "출처",
                    "--set",
                    "record_count=120",
                    "--set",
                    "corpus_name=corpus_a",
                    "--set",
                    'tags=["a","b"]',
                ]
            )
            == 0
        )
        payload = _read(corpus_dir / cps.SIDECAR_FILENAME)
        assert payload["record_count"] == 120
        assert payload["corpus_name"] == "corpus_a"
        assert payload["tags"] == ["a", "b"]

    def test_parse_set_option_unit(self) -> None:
        assert cps.parse_set_option("n=1") == ("n", 1)
        assert cps.parse_set_option("s=hello") == ("s", "hello")
        with pytest.raises(cps.SidecarInputError):
            cps.parse_set_option("=1")


class TestDryRun:
    def test_dry_run_writes_nothing(self, tmp_path: Path) -> None:
        corpus_dir = _corpus(tmp_path)
        assert (
            cps.main(
                [
                    str(corpus_dir),
                    "--pool",
                    "whymath-original",
                    "--source-citation",
                    "출처",
                    "--dry-run",
                ]
            )
            == 0
        )
        assert not (corpus_dir / cps.SIDECAR_FILENAME).exists()
        assert pa.audit_corpus_root(tmp_path).exit_code == 1, "dry-run이 실제로 파일을 썼다"

    def test_dry_run_on_existing_does_not_modify(self, tmp_path: Path) -> None:
        corpus_dir = _corpus(tmp_path)
        path = _write_existing(corpus_dir, _EXISTING_SIDECAR)
        before = path.read_bytes()
        assert cps.main([str(corpus_dir), "--license-notice", "CC BY 4.0", "--dry-run"]) == 0
        assert path.read_bytes() == before


class TestMultipleCorpora:
    def test_all_targets_processed(self, tmp_path: Path) -> None:
        first = _corpus(tmp_path, "one_v1")
        second = _corpus(tmp_path, "two_v1")
        assert (
            cps.main(
                [
                    str(first),
                    str(second),
                    "--pool",
                    "whymath-original",
                    "--source-citation",
                    "출처",
                ]
            )
            == 0
        )
        assert pa.audit_corpus_root(tmp_path).exit_code == 0
        assert pa.audit_corpus_root(tmp_path).corpora_scanned == 2


class TestApplyToCorpusApi:
    """함수 API(오케스트레이션 재사용 좌석) — action·pool_preserved 판정을 직접 고정."""

    def test_actions_created_updated_unchanged(self, tmp_path: Path) -> None:
        corpus_dir = _corpus(tmp_path)
        update = cps.SidecarUpdate(pool=None, source_citation="출처", license_notice=None, extra={})
        created = cps.apply_to_corpus(
            corpus_dir,
            cps.SidecarUpdate(pool=cps.ContentPool.WHYMATH_ORIGINAL, source_citation="출처"),
        )
        assert created.action == cps.ACTION_CREATED
        assert created.pool_preserved is False

        unchanged = cps.apply_to_corpus(corpus_dir, update)
        assert unchanged.action == cps.ACTION_UNCHANGED
        assert unchanged.pool_preserved is True  # pool 인자 없이 기존 값 보존

        updated = cps.apply_to_corpus(corpus_dir, cps.SidecarUpdate(license_notice="CC BY 4.0"))
        assert updated.action == cps.ACTION_UPDATED
        assert updated.payload["pool"] == "whymath-original"

    def test_merge_payload_is_pure(self) -> None:
        existing = {"pool": "whymath-original", "counts": {"n": 1}}
        merged, preserved = cps.merge_payload(existing, cps.SidecarUpdate(source_citation="출처"))
        assert preserved is True
        assert merged == {
            "pool": "whymath-original",
            "counts": {"n": 1},
            "source_citation": "출처",
        }
        assert existing == {"pool": "whymath-original", "counts": {"n": 1}}, "입력을 변형했다"
