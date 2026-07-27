"""policy.yaml — 조율 정책 로드/저장/검증 테스트."""

from __future__ import annotations

from pathlib import Path

import store
from models import Policy


class TestPolicyDefaults:
    def test_파일_부재_시_전부_기본값(self, tmp_path: Path):
        policy, errors = store.load_policy(tmp_path)
        assert errors == []
        assert policy.path_overlap == "warn"
        assert policy.scope_drift == "warn"
        assert policy.adhoc_edit == "warn"
        assert policy.claim_ttl_hours == 72
        assert policy.remote_claims is True

    def test_기본값은_검증_통과(self):
        assert Policy().validate() == []


class TestPolicyValidation:
    def test_잘못된_모드_거부(self):
        errors = Policy(path_overlap="strict").validate()
        assert any("path_overlap" in e for e in errors)

    def test_ttl_음수_거부(self):
        errors = Policy(claim_ttl_hours=0).validate()
        assert any("claim_ttl_hours" in e for e in errors)

    def test_로드_시_잘못된_값이_오류로_보고된다(self, tmp_path: Path):
        (tmp_path / "backlog").mkdir()
        (tmp_path / "backlog" / "policy.yaml").write_text(
            "path_overlap: aggressive\n", encoding="utf-8"
        )
        _, errors = store.load_policy(tmp_path)
        assert any("path_overlap" in e for e in errors)

    def test_미지_필드는_오류(self, tmp_path: Path):
        (tmp_path / "backlog").mkdir()
        (tmp_path / "backlog" / "policy.yaml").write_text("unknown_rule: warn\n", encoding="utf-8")
        _, errors = store.load_policy(tmp_path)
        assert any("미지 필드" in e for e in errors)


class TestPolicyRoundtrip:
    def test_저장_후_로드_동일(self, tmp_path: Path):
        policy = Policy(path_overlap="block", claim_ttl_hours=24)
        store.save_policy(tmp_path, policy)
        loaded, errors = store.load_policy(tmp_path)
        assert errors == []
        assert loaded == policy

    def test_dump_결정성(self):
        # 같은 입력이면 항상 같은 출력 (diff 안정)
        a = store.dump_policy(Policy())
        b = store.dump_policy(Policy())
        assert a == b
        assert "path_overlap: warn" in a
        assert "remote_claims: true" in a
