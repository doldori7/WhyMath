"""백업 암호화·스케줄·상태 대장 계약 테스트 (OPS-31).

세 축을 각각 다른 방식으로 고정한다 — 검증 방법이 대상의 성질을 따라간다:

  A. **PS1 텍스트 동결** — `backup_whymath_pg.ps1`·`register_backup_schedule.ps1`은 Kiki
     머신(Windows)에서만 실행된다. CI·샌드박스에 PowerShell이 없으므로 실행 검증이
     구조적으로 불가능하다(`scripts/ops/check_ps_scripts.py`가 같은 공백을 다루는 선례).
     그래서 *의미를 지고 있는 문장*만 골라 텍스트로 동결한다.
  B. **파이썬 판정기 실동작** — `backup_status.py`는 실제로 돌려서 검사한다.
  C. **암호화 왕복 실측** — `verify_encrypted_backup.py`는 실 `age`·`pg_restore`로
     암호문을 만들어 태운다. 도구가 없으면 skip이며, **skip을 통과로 세지 않는다**.

A축의 한계를 명시한다: 텍스트 동결은 "그 문장이 있다"까지만 증명하고 "그 문장이 의도대로
동작한다"는 증명하지 못한다. 그 구간은 런북 §3·§4의 자가검증 스텝(실행 후 산출물 확인)이
담당하며, 여기서 대신했다고 주장하지 않는다.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_BACKUP_DIR = _ROOT / "scripts" / "backup"
_DUMP_SCRIPT = _BACKUP_DIR / "backup_whymath_pg.ps1"
_SCHEDULE_SCRIPT = _BACKUP_DIR / "register_backup_schedule.ps1"
_STATUS_MODULE = _BACKUP_DIR / "backup_status.py"
_VERIFY_MODULE = _BACKUP_DIR / "verify_encrypted_backup.py"

sys.path.insert(0, str(_BACKUP_DIR))

import backup_status as bs  # noqa: E402
import verify_encrypted_backup as vb  # noqa: E402


def _strip_ps_comments(src: str) -> str:
    """PS 주석만 제거하고 **문자열 리터럴은 남긴다**.

    `scripts/ops/check_ps_scripts.strip_noncode`는 괄호 균형 검사용이라 문자열까지
    지운다 — 여기서는 `"*.dump.age"` 같은 리터럴 자체가 계약이므로 쓸 수 없다.
    한편 원문 전체를 검사하면 헤더 주석이 코드 결함을 통과시킨다(뮤테이션 ①②⑫ 미검출
    실측). 그 사이가 이 헬퍼다: 줄 주석·블록 주석만 걷어낸다.
    """
    out: list[str] = []
    in_block = False
    for line in src.splitlines():
        stripped = line.strip()
        if in_block:
            if "#>" in stripped:
                in_block = False
            continue
        if stripped.startswith("<#"):
            if "#>" not in stripped:
                in_block = True
            continue
        if stripped.startswith("#"):
            continue
        out.append(line)
    return "\n".join(out)


def _dump_text() -> str:
    return _DUMP_SCRIPT.read_text(encoding="ascii")


def _schedule_text() -> str:
    return _SCHEDULE_SCRIPT.read_text(encoding="ascii")


def _dump_code() -> str:
    return _strip_ps_comments(_dump_text())


def _schedule_code() -> str:
    return _strip_ps_comments(_schedule_text())


# ===========================================================================
# A. PS1 텍스트 동결 — 암호화 스텝
# ===========================================================================
class TestEncryptionContract:
    def test_scripts_exist(self) -> None:
        assert _DUMP_SCRIPT.is_file(), f"백업 스크립트 부재: {_DUMP_SCRIPT}"
        assert _SCHEDULE_SCRIPT.is_file(), f"스케줄 스크립트 부재: {_SCHEDULE_SCRIPT}"

    @pytest.mark.parametrize("script", [_DUMP_SCRIPT, _SCHEDULE_SCRIPT])
    def test_ascii_only(self, script: Path) -> None:
        """cp949(한국어 Windows 로케일)로도 깨지지 않는다 — 2026-07-17 logconfig 선례."""
        data = script.read_bytes()
        try:
            data.decode("ascii")
        except UnicodeDecodeError as exc:
            pytest.fail(
                f"{script.name}에 비ASCII 바이트 (offset {exc.start}: "
                f"{data[exc.start:exc.start + 8]!r}) — PS 5.1이 cp949로 읽다 깨진다. "
                "한국어 설명은 런북에 둔다."
            )
        data.decode("cp949")
        assert not data.startswith(b"\xef\xbb\xbf"), f"{script.name}에 BOM — PS 5.1이 깨진다"

    def test_recipients_default_lives_in_backup_dir(self) -> None:
        """플래그를 잊어도 암호화가 사라지지 않는다 — 디렉터리 기본값이 그 보장이다.

        스케줄 실행에는 아무도 인자를 붙여 주지 않는다. 명시 플래그로만 암호화되면
        자동 회차는 영구히 평문이 된다.
        """
        text = _dump_code()
        assert (
            'Join-Path $BackupDir "recipients.txt"' in text
        ), "recipients.txt 디렉터리 기본값이 사라짐 — 스케줄 회차가 조용히 평문으로 돈다"

    def test_plaintext_is_removed_after_encryption(self) -> None:
        """암호화 성공 후 평문 삭제 — 이 스텝이 없으면 암호화는 사본을 하나 늘릴 뿐이다."""
        text = _dump_text()
        marker = "# Plaintext removal is the point of the whole step."
        assert marker in text, "평문 삭제 스텝이 사라짐"
        after = text[text.index(marker) :]
        assert (
            "Remove-Item $hostPath" in after.split("$encrypted = $true")[0]
        ), "암호화 성공 경로에서 평문 삭제가 사라짐"

    def test_every_post_resolution_failure_deletes_the_plaintext(self) -> None:
        """★ fail-closed 전수 — 수신자 해석 *이후*의 모든 Fail 앞에 평문 삭제가 있다.

        이 테스트가 이 파일에서 가장 중요하다. 절반만 암호화된 회차는 실패한 회차보다
        나쁘다 — 처리된 것처럼 보이는 이름 아래 판독 가능한 미성년 PII가 남는다.
        한 갈래라도 삭제를 빠뜨리면 여기서 red가 난다(문장 존재가 아니라 *전수* 검사).
        """
        text = _dump_text()
        start = text.index('$resolvedRecipients = ""')
        end = text.index("# Step 7: record the success")
        region = text[start:end]

        # 각 Fail 호출 직전 6줄 안에 평문 삭제가 있어야 한다.
        lines = region.splitlines()
        offenders: list[str] = []
        for i, line in enumerate(lines):
            if "Fail " not in line:
                continue
            window = "\n".join(lines[max(0, i - 6) : i])
            if "Remove-Item $hostPath" not in window:
                offenders.append(line.strip()[:90])
        assert (
            not offenders
        ), (
            "수신자 해석 이후 Fail 경로에 평문 삭제가 없다 — 판독 가능한 PII가 남는다: "
            + " | ".join(offenders)
        )

    def test_magic_selfcheck_is_discriminating(self) -> None:
        """암호문이 PGDMP로 시작하면 거부 — age가 cp로 대체돼도 잡힌다.

        "암호화했다"를 종료코드 0만으로 믿지 않는 자리다(선언이 아니라 산출물 판독).
        """
        text = _dump_code()
        assert '$headText -eq "PGDMP"' in text, "암호문 매직 자가검증이 사라짐"
        assert 'PG_CUSTOM_DUMP_MAGIC = b"PGDMP"' in _VERIFY_MODULE.read_text(
            encoding="utf-8"
        ), "파이썬 검증기의 매직 상수가 PS1과 어긋남"

    def test_empty_recipients_file_is_refused(self) -> None:
        """빈 수신자 파일이 '암호화 없음'으로 조용히 강등되지 않는다."""
        text = _dump_code()
        assert (
            "$recipientLines.Count -eq 0" in text
        ), "빈 recipients 파일 거부가 사라짐 — 주석만 남은 파일이 평문 회차를 만든다"

    def test_require_encryption_switch_refuses_plaintext(self) -> None:
        """거부가 *경고*로 완화되지 않는다 — 동사(Fail)까지 함께 동결한다.

        초판은 메시지 문면만 봤다. `Fail`을 `Write-Host`로 바꾸면 문면은 그대로 남고
        스크립트는 평문 백업을 만들고도 exit 0으로 끝난다(뮤테이션 ⑫ 미검출).
        """
        text = _dump_text()
        assert "[switch]$RequireEncryption" in _dump_code()
        assert (
            'Fail "-RequireEncryption was given but no recipients file was found' in text
        ), "-RequireEncryption 위반이 실패가 아닌 경고로 완화됐다"
        # 코드측에도 그 분기가 실재하는지(주석만 남은 유령이 아닌지) 확인한다.
        code = _dump_code()
        assert "if ($RequireEncryption) {" in code

    def test_retention_covers_encrypted_artifacts(self) -> None:
        """보존 정책이 .dump.age도 본다 — 아니면 암호화본이 영원히 쌓인다."""
        text = _dump_code()
        assert (
            '$_.Name -like "*.dump.age"' in text
        ), "보존 정책이 암호화 산출물을 못 본다 — .age 파일이 만료되지 않고 누적된다"
        assert "Select-Object -Skip 1" in text, "최신본 보존(최소 1개) 계약이 사라짐"

    def test_status_is_written_on_success(self) -> None:
        text = _dump_code()
        assert "function Write-BackupStatus" in text
        assert 'Join-Path $BackupDir "backup_status.json"' in text
        assert bs.STATUS_FILENAME == "backup_status.json"

    def test_ps1_status_keys_match_the_python_reader(self) -> None:
        """★ 생산자(PS1)와 소비자(파이썬)의 필드명 교차 동결.

        한쪽만 개명하면 상태 파일이 조용히 판독 불가가 되고, 그러면 '누락 탐지'가
        누락을 못 잡는다 — 감시 장치가 무증상으로 죽는 형태다.
        """
        text = _dump_text()
        required = [
            "last_success_utc",
            "artifact",
            "size_bytes",
            "encrypted",
            "recipients_fingerprint",
        ]
        missing = [k for k in required if f"{k} " not in text and f"{k}=" not in text]
        assert not missing, f"PS1이 쓰지 않는 상태 필드: {missing}"

        # 소비자가 실제로 그 키들을 읽는지도 본다(이름만 같고 안 읽으면 의미 없다).
        reader = _STATUS_MODULE.read_text(encoding="utf-8")
        for key in required:
            assert f'"{key}"' in reader, f"파이썬 판독기가 {key}를 읽지 않는다"

    def test_atomic_status_write(self) -> None:
        """중간에 죽어도 잘린 상태 파일이 남지 않는다."""
        text = _dump_code()
        assert "Move-Item -Path $tmp -Destination $StatusPath -Force" in text

    def test_existing_safeguards_survived(self) -> None:
        """OPS-02가 세운 안전장치가 이번 확장으로 사라지지 않았다."""
        text = _dump_text()
        assert "whymath-demo-db" in text, "demo DB 거부 가드 소실"
        assert "pg_restore --list" in text, "덤프 카탈로그 자가검증 소실"
        assert text.index("pg_restore --list") < text.index(
            "docker cp"
        ), "자가검증이 호스트 회수 뒤로 밀림"


# ===========================================================================
# A'. PS1 텍스트 동결 — 스케줄 등록
# ===========================================================================
class TestScheduleContract:
    def test_s4u_removes_the_logon_dependency(self) -> None:
        """런북 §6이 자인한 '로그온 의존'을 실제로 없애는 설정이 S4U다."""
        # ★ 주석이 아니라 *코드*에서 본다. 초판은 원문 전체를 검사해서 실제 설정을
        # Password로 바꿔도 헤더 주석의 같은 문자열이 통과시켰다(뮤테이션 ① 미검출).
        text = _schedule_code()
        assert "-LogonType S4U" in text, (
            "S4U가 사라짐 — 태스크가 다시 대화형 로그온에 의존하게 되고, "
            "로그인하지 않은 날의 회차가 조용히 누락된다"
        )

    def test_missed_occurrence_is_not_dropped(self) -> None:
        text = _schedule_code()
        assert (
            "-StartWhenAvailable" in text
        ), "StartWhenAvailable 소실 — 머신이 꺼져 있던 회차가 그냥 버려진다"

    def test_registration_is_verified_by_reading_back(self) -> None:
        """★ 등록 성공은 설정이 옳다는 증거가 아니다 — 되읽어 LogonType을 확인한다.

        '검증 장치를 만들고 배선 확인 없이 완료 선언 금지'의 스크립트판이다.
        """
        text = _schedule_code()
        reg = text.index("Register-ScheduledTask -TaskName $TaskName -Action")
        after = text[reg:]
        assert "Get-ScheduledTask -TaskName $TaskName" in after, "등록 후 되읽기 검증 부재"
        assert (
            '"$logonType" -ne "S4U"' in after
        ), "되읽기는 하는데 LogonType을 판정하지 않음 — 변별력 없는 검증 스텝"
        assert "$check.Settings.StartWhenAvailable" in after

    def test_absolute_script_path(self) -> None:
        """태스크는 임의 작업 디렉터리에서 뜬다 — 상대 경로면 트리거 시각에 실패한다."""
        text = _schedule_code()
        assert "$PSScriptRoot" in text

    def test_unregister_path_verifies_removal(self) -> None:
        text = _schedule_text()
        assert "[switch]$Unregister" in text
        assert "is still registered" in text, "제거 후 잔존 확인이 없다"

    def test_scheduling_does_not_claim_to_make_misses_observable(self) -> None:
        """스케줄은 누락을 *줄이고*, 관측은 상태 파일이 한다 — 그 구분이 문서에 남아 있다."""
        text = _schedule_text()
        assert "Scheduling" in text and "reduces misses" in text


# ===========================================================================
# B. backup_status.py 실동작
# ===========================================================================
class TestBackupStatus:
    def test_never_recorded_is_its_own_reason(self, tmp_path: Path) -> None:
        """기록 없음과 오래됨을 뭉치면 조사 방향을 잃는다."""
        verdict = bs.evaluate_staleness(None)
        assert verdict.ok is False
        assert verdict.reason == "never_recorded"
        assert verdict.age_hours is None

    def test_fresh_and_stale_are_separated_by_the_threshold(self, tmp_path: Path) -> None:
        now = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)
        path = tmp_path / bs.STATUS_FILENAME
        bs.record_success(
            path,
            artifact="x.dump.age",
            size_bytes=10,
            encrypted=True,
            moment=now - timedelta(hours=10),
        )
        loaded = bs.load_status(path)
        assert bs.evaluate_staleness(loaded, max_age_hours=24, now=now).reason == "fresh"
        assert bs.evaluate_staleness(loaded, max_age_hours=5, now=now).reason == "stale"

    def test_record_round_trips_every_field(self, tmp_path: Path) -> None:
        path = tmp_path / bs.STATUS_FILENAME
        moment = datetime(2026, 9, 1, 3, 4, 5, tzinfo=UTC)
        bs.record_success(
            path,
            artifact="whymath_20260901_030405.dump.age",
            size_bytes=4096,
            encrypted=True,
            recipients_fingerprint="qmm59p6",
            moment=moment,
        )
        got = bs.load_status(path)
        assert got is not None
        assert got.artifact.endswith(".dump.age")
        assert got.size_bytes == 4096
        assert got.encrypted is True
        assert got.recipients_fingerprint == "qmm59p6"
        assert got.last_success_utc == moment

    def test_corrupt_status_raises_instead_of_defaulting(self, tmp_path: Path) -> None:
        """손상된 상태 파일을 '기록 없음'이나 '신선함'으로 넘기면 무증상 실패가 된다."""
        path = tmp_path / bs.STATUS_FILENAME
        path.write_text("{ this is not json", encoding="utf-8")
        with pytest.raises(bs.BackupStatusError) as exc:
            bs.load_status(path)
        assert (
            "JSONDecodeError" in str(exc.value) or "json" in str(exc.value).lower()
        ), "예외 타입·사유가 메시지에 없다 — 무타입 경고 금지(2026-07-16 langfuse 교훈)"

    def _cli(self, tmp_path: Path, *args: str) -> int:
        return bs.main(list(args))

    def test_cli_never_recorded_exits_one(self, tmp_path: Path, capsys) -> None:
        assert self._cli(tmp_path, "check", "--backup-dir", str(tmp_path)) == 1
        captured = capsys.readouterr()
        # 실패 사유는 stderr로 나간다(성공 요약과 섞이지 않게). 사유 문면에 "0회"와
        # "오래됨"의 구분이 남아 있는지까지 본다 — 뭉뚱그린 실패는 조사 방향을 못 준다.
        assert "기록이 없다" in captured.err
        assert "오래됨" in captured.err

    def test_cli_record_then_check_passes(self, tmp_path: Path) -> None:
        assert (
            self._cli(
                tmp_path,
                "record",
                "--backup-dir",
                str(tmp_path),
                "--artifact",
                "a.dump.age",
                "--size-bytes",
                "10",
                "--encrypted",
                "true",
            )
            == 0
        )
        assert self._cli(tmp_path, "check", "--backup-dir", str(tmp_path)) == 0

    def test_cli_require_encrypted_rejects_a_plaintext_run(self, tmp_path: Path) -> None:
        """오프사이트 운용에서 평문 산출물은 통과시키지 않는다 (런북 §4-1)."""
        self._cli(
            tmp_path,
            "record",
            "--backup-dir",
            str(tmp_path),
            "--artifact",
            "a.dump",
            "--size-bytes",
            "10",
            "--encrypted",
            "false",
        )
        assert self._cli(tmp_path, "check", "--backup-dir", str(tmp_path)) == 0
        assert (
            self._cli(tmp_path, "check", "--backup-dir", str(tmp_path), "--require-encrypted") == 1
        )

    def test_cli_json_output_is_machine_readable(self, tmp_path: Path, capsys) -> None:
        self._cli(tmp_path, "check", "--backup-dir", str(tmp_path), "--json")
        payload = json.loads(capsys.readouterr().out)
        assert payload["ok"] is False
        assert payload["reason"] == "never_recorded"


# ===========================================================================
# C. 암호화 왕복 실측 (실 age·pg_restore)
# ===========================================================================
_AGE = shutil.which("age")
_AGE_KEYGEN = shutil.which("age-keygen")
_PG_RESTORE = shutil.which("pg_restore")
_TOOLS = bool(_AGE and _AGE_KEYGEN and _PG_RESTORE)
_skip_no_tools = pytest.mark.skipif(
    not _TOOLS, reason="age/age-keygen/pg_restore 부재 — 왕복 실측 불가(skip은 통과가 아니다)"
)


@pytest.fixture
def keypair(tmp_path: Path) -> tuple[Path, Path]:
    """age 키쌍 — 개인키 파일과 수신자(공개키) 파일을 분리해 만든다(§4-5 키 분리)."""
    identity = tmp_path / "backup-identity.key"
    subprocess.run([_AGE_KEYGEN, "-o", str(identity)], check=True, capture_output=True)
    recipient = ""
    for line in identity.read_text(encoding="utf-8").splitlines():
        if line.startswith("# public key: "):
            recipient = line.removeprefix("# public key: ").strip()
    assert recipient, "age-keygen 출력에서 공개키를 찾지 못함"
    recipients = tmp_path / "recipients.txt"
    recipients.write_text(recipient + "\n", encoding="utf-8")
    return identity, recipients


@pytest.fixture
def fake_dump(tmp_path: Path) -> Path:
    """pg_dump 커스텀 포맷 헤더를 갖춘 최소 산출물.

    실 DB 없이도 ①매직 판별 ②pg_restore가 *거부*하는 축을 검사할 수 있다. 실 덤프의
    왕복(카탈로그 판독 성공)은 이 세션이 실 PG 16으로 별도 실측했다(PR 본문 표).
    """
    path = tmp_path / "whymath_20260901_000000.dump"
    path.write_bytes(vb.PG_CUSTOM_DUMP_MAGIC + b"\x01\x0e\x00" + b"\x00" * 64)
    return path


class TestEncryptedVerification:
    def test_magic_detection(self, fake_dump: Path, tmp_path: Path) -> None:
        assert vb.looks_like_pg_custom_dump(fake_dump) is True
        other = tmp_path / "other.bin"
        other.write_bytes(b"age-encryption.org/v1\n")
        assert vb.looks_like_pg_custom_dump(other) is False

    def test_missing_input_is_named(self, tmp_path: Path) -> None:
        result = vb.verify_encrypted_backup(
            tmp_path / "nope.age", identity_file=tmp_path / "k", age_bin="age"
        )
        assert result.reason == "missing_input"
        assert result.locked_ok is False and result.restorable_ok is False

    @_skip_no_tools
    def test_plaintext_masquerading_as_ciphertext_is_caught(
        self, fake_dump: Path, keypair: tuple[Path, Path], tmp_path: Path
    ) -> None:
        """확장자만 .age인 평문 — 암호화 스텝이 통째로 빠져도 여기서 걸린다."""
        identity, _ = keypair
        fake = tmp_path / "fake.dump.age"
        fake.write_bytes(fake_dump.read_bytes())
        result = vb.verify_encrypted_backup(fake, identity_file=identity)
        assert result.reason == "not_encrypted"
        assert result.locked_ok is False

    @_skip_no_tools
    def test_wrong_identity_fails_with_a_typed_reason(
        self, fake_dump: Path, keypair: tuple[Path, Path], tmp_path: Path
    ) -> None:
        identity, recipients = keypair
        enc = tmp_path / "x.dump.age"
        subprocess.run(
            [_AGE, "-R", str(recipients), "-o", str(enc), str(fake_dump)],
            check=True,
            capture_output=True,
        )
        wrong = tmp_path / "wrong.key"
        subprocess.run([_AGE_KEYGEN, "-o", str(wrong)], check=True, capture_output=True)

        result = vb.verify_encrypted_backup(enc, identity_file=wrong)
        assert result.locked_ok is True, "암호문은 pg_restore가 거부해야 한다"
        assert result.restorable_ok is False
        assert result.reason == "decrypt_failed"
        assert result.detail, "실패 사유 본문이 비었다 — 예외 타입만으론 원인이 구분되지 않는다"

    @_skip_no_tools
    def test_truncated_ciphertext_fails(
        self, fake_dump: Path, keypair: tuple[Path, Path], tmp_path: Path
    ) -> None:
        identity, recipients = keypair
        enc = tmp_path / "x.dump.age"
        subprocess.run(
            [_AGE, "-R", str(recipients), "-o", str(enc), str(fake_dump)],
            check=True,
            capture_output=True,
        )
        truncated = tmp_path / "t.dump.age"
        truncated.write_bytes(enc.read_bytes()[: len(enc.read_bytes()) // 2])
        result = vb.verify_encrypted_backup(truncated, identity_file=identity)
        assert result.restorable_ok is False
        assert result.reason == "decrypt_failed"

    @_skip_no_tools
    def test_missing_tool_is_undecidable_not_pass(
        self, fake_dump: Path, keypair: tuple[Path, Path], tmp_path: Path
    ) -> None:
        """★ 도구 부재는 exit 2 — '검사 못 함'이 '문제 없음'으로 위장되지 않는다."""
        identity, recipients = keypair
        enc = tmp_path / "x.dump.age"
        subprocess.run(
            [_AGE, "-R", str(recipients), "-o", str(enc), str(fake_dump)],
            check=True,
            capture_output=True,
        )
        code = vb.main([str(enc), "--identity", str(identity), "--age-bin", "/nonexistent/age"])
        assert code == 2, "도구 부재가 0(통과)이나 1(실패)로 뭉개지면 안 된다"

    @_skip_no_tools
    def test_decrypted_copy_does_not_survive(
        self, fake_dump: Path, keypair: tuple[Path, Path], tmp_path: Path
    ) -> None:
        """복호본이 남으면 이 검증 자체가 §4 취급 규칙 위반이 된다."""
        identity, recipients = keypair
        enc = tmp_path / "x.dump.age"
        subprocess.run(
            [_AGE, "-R", str(recipients), "-o", str(enc), str(fake_dump)],
            check=True,
            capture_output=True,
        )
        before = {p.name for p in tmp_path.iterdir()}
        vb.verify_encrypted_backup(enc, identity_file=identity)
        after = {p.name for p in tmp_path.iterdir()}
        assert after == before, f"검증이 파일을 남겼다: {after - before}"
