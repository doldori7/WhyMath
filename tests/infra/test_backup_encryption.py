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
import re
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
_CHECK_SCRIPT = _BACKUP_DIR / "check_backup_freshness.ps1"
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
    실측). 그 사이가 이 헬퍼다.

    **줄 끝 주석까지 지운다**: 초판은 줄 전체 주석만 걷어냈는데, 그러면 호출을
    `Write-Host "skip" # Register-ScheduledTask ...`처럼 *주석 처리해* 무력화해도
    문자열이 코드에 남아 계약 단언이 통과한다(뮤테이션 ③ 미검출 실측 — 가드 자신이
    위장이었던 사례). `#`이 따옴표 안이면 주석이 아니므로 인용 상태를 추적한다.
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
        # 줄 끝 주석 제거 — 따옴표 밖의 첫 `#`부터 잘라 낸다.
        quote = ""
        cut = None
        for idx, ch in enumerate(line):
            if quote:
                if ch == quote:
                    quote = ""
            elif ch in ("'", '"'):
                quote = ch
            elif ch == "#":
                cut = idx
                break
        out.append(line if cut is None else line[:cut])
    return "\n".join(out)


def _dump_text() -> str:
    return _DUMP_SCRIPT.read_text(encoding="ascii")


def _schedule_text() -> str:
    return _SCHEDULE_SCRIPT.read_text(encoding="ascii")


def _dump_code() -> str:
    return _strip_ps_comments(_dump_text())


def _schedule_code() -> str:
    return _strip_ps_comments(_schedule_text())


def _check_text() -> str:
    return _CHECK_SCRIPT.read_text(encoding="ascii")


def _check_code() -> str:
    return _strip_ps_comments(_check_text())


# ===========================================================================
# A. PS1 텍스트 동결 — 암호화 스텝
# ===========================================================================
class TestEncryptionContract:
    def test_scripts_exist(self) -> None:
        assert _DUMP_SCRIPT.is_file(), f"백업 스크립트 부재: {_DUMP_SCRIPT}"
        assert _SCHEDULE_SCRIPT.is_file(), f"스케줄 스크립트 부재: {_SCHEDULE_SCRIPT}"
        assert _CHECK_SCRIPT.is_file(), f"신선도 검사 스크립트 부재: {_CHECK_SCRIPT}"

    @pytest.mark.parametrize("script", [_DUMP_SCRIPT, _SCHEDULE_SCRIPT, _CHECK_SCRIPT])
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
        """★ 두 태스크 *각각*을 본다.

        초판은 파일 어딘가에 `-StartWhenAvailable`이 있으면 통과했다. 검사 태스크가
        생기면서 그 문자열이 두 번 나오게 되자 **백업 태스크에서 지워도 검사 태스크의
        것이 통과시켰다**(뮤테이션 재실행에서 미검출로 드러남 — 계약이 늘 때 기존
        단언의 변별력이 조용히 사라지는 형태다). 설정 변수별로 특정한다.
        """
        text = _schedule_code()
        for var, what in (("$settings", "백업"), ("$checkSettings", "신선도 검사")):
            line = next(
                (ln for ln in text.splitlines() if ln.strip().startswith(f"{var} = New-Scheduled")),
                None,
            )
            assert line is not None, f"{what} 태스크의 설정 정의를 찾지 못함 ({var})"
            assert "-StartWhenAvailable" in line, (
                f"{what} 태스크에서 StartWhenAvailable 소실 — "
                "머신이 꺼져 있던 회차가 그냥 버려진다"
            )

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


# ===========================================================================
# C-3. 오프사이트 미러 생명주기 (PR #974 Codex P1-2)
#
# 1회 복사는 두 방향으로 썩는다: 이후 백업이 오프사이트에 안 가서 RPO가 무한히
# 자라고, 만료 사본이 클라우드에 남아 §4-3이 PIPA 파기 창의 상한이라고 선언한
# 보존 기간이 거짓이 된다. 그래서 미러는 스케줄 스크립트에 편입돼야 한다.
# ===========================================================================
class TestOffsiteMirror:
    def test_backup_script_accepts_offsite_dir(self) -> None:
        body = (_BACKUP_DIR / "backup_whymath_pg.ps1").read_text(encoding="utf-8")
        assert "$OffsiteDir" in body, "백업 스크립트에 오프사이트 미러 경로 인자가 없다"

    def test_offsite_is_opt_in(self) -> None:
        """기본값이 비어 있어야 기존 스케줄이 재등록 전까지 동작을 바꾸지 않는다."""
        body = (_BACKUP_DIR / "backup_whymath_pg.ps1").read_text(encoding="utf-8")
        assert '[string]$OffsiteDir = ""' in body, "오프사이트가 opt-in이 아니다"

    def test_plaintext_is_never_mirrored(self) -> None:
        """★ 평문 회차에 -OffsiteDir가 주어지면 거부해야 한다.

        평문 덤프에는 학적·프로필·활동 메타가 그대로 들어 있다(§4 표). 미러가
        암호화 여부를 보지 않으면 미성년 PII가 클라우드로 나간다.
        """
        body = (_BACKUP_DIR / "backup_whymath_pg.ps1").read_text(encoding="utf-8")
        offsite = body.split("Step 9", 1)[1]
        assert "if (-not $encrypted)" in offsite, "미러가 암호화 여부를 확인하지 않는다"

    def test_offsite_retention_applies_the_same_window(self) -> None:
        """★ 만료 사본이 클라우드에 남으면 §4-3의 PIPA 파기 창 선언이 거짓이 된다."""
        body = (_BACKUP_DIR / "backup_whymath_pg.ps1").read_text(encoding="utf-8")
        offsite = body.split("Step 9", 1)[1]
        assert "$offsiteExpired" in offsite, "오프사이트에 보존 정책이 적용되지 않는다"
        assert "$cutoff" in offsite, "로컬과 다른 만료 기준을 쓰고 있다"
        assert (
            "Select-Object -Skip 1" in offsite
        ), "최신 1개 보존 불변식이 오프사이트에 없다 — 전멸 가능"

    def test_offsite_copy_is_verified_by_size(self) -> None:
        """존재 검사만으로는 잘린 사본을 못 잡는다 — 있으면서 열리지 않는다."""
        body = (_BACKUP_DIR / "backup_whymath_pg.ps1").read_text(encoding="utf-8")
        offsite = body.split("Step 9", 1)[1]
        assert "$offsiteSize -ne $sizeBytes" in offsite, "사본 크기를 대조하지 않는다"

    def test_offsite_failure_is_fatal_not_a_warning(self) -> None:
        """★ 무인 실행에서 경고는 아무도 안 읽는다 — 종료코드만 사람에게 닿는다."""
        body = (_BACKUP_DIR / "backup_whymath_pg.ps1").read_text(encoding="utf-8")
        offsite = body.split("Step 9", 1)[1]
        assert 'Fail "offsite copy failed' in offsite, "복사 실패가 치명이 아니다"
        assert (
            "[WARN] offsite" not in offsite
        ), "오프사이트 실패를 경고로 흘리고 있다 — 스케줄러 stdout은 아무도 읽지 않는다"

    def test_registration_failure_is_attributed_to_the_real_step(self) -> None:
        """★ 실패 사유를 실패한 지점에 귀속시킨다.

        2026-09-03 실측: 비관리자 창에서 Register-ScheduledTask가 'Access is denied'로
        실패했는데, 그것이 **비종료 오류**라 스크립트가 계속 진행했고 운영자가 본 유일한
        [FAIL]은 되읽기 단계의 "reported success but cannot be read back"이었다. 등록이
        성공했다고 *주장하면서* 실패를 보고하는 문면이라 진단을 엉뚱한 곳으로 보낸다.
        """
        body = (_BACKUP_DIR / "register_backup_schedule.ps1").read_text(encoding="utf-8")
        assert (
            "-ErrorAction Stop" in body
        ), "CIM 비종료 오류를 종료 오류로 승격하지 않으면 실패가 그냥 스크롤된다"
        assert (
            "reported success but" not in body
        ), "등록이 성공했다고 주장하는 실패 문면이 남아 있다 — 사실과 다르다"

    def test_access_denied_hint_is_locale_independent(self) -> None:
        """★ 한국어 Windows에서는 'Access is denied'가 번역되어 온다.

        영어 문자열만 보는 검사는 이 머신에서 **정상적으로 실패한 상황을 못 알아본다**.
        HRESULT(0x80070005)는 로케일과 무관하다.
        """
        body = (_BACKUP_DIR / "register_backup_schedule.ps1").read_text(encoding="utf-8")
        assert (
            "0x80070005" in body
        ), "권한 오류 판정이 영어 메시지 문자열에만 의존한다 — cp949 로케일에서 뚫린다"

    def test_schedule_passes_offsite_through(self) -> None:
        """★ 스크립트가 받아도 스케줄이 안 넘기면 상시 미러가 아니다(배선 실재성).

        **주석이 아니라 조립되는 인자 문자열을 본다.** 초판은 파일 전체에 대한
        substring 검사여서, argList 조립을 통째로 지워도 상단 usage 주석의
        `-OffsiteDir` 한 글자에 매치돼 통과했다(2026-09-03 뮤테이션 O4에서 실측 —
        검출 실패). CLAUDE.md "정의만 하고 안 써도 통과하는 substring 검사" 그대로다.
        """
        body = (_BACKUP_DIR / "register_backup_schedule.ps1").read_text(encoding="utf-8")
        assert "$OffsiteDir" in body, "스케줄 등록이 오프사이트 인자를 모른다"

        # 주석(#로 시작)을 제외한 실행 라인에서 argList 조립을 찾는다.
        code_lines = [ln for ln in body.splitlines() if not ln.lstrip().startswith("#")]
        assembly = [ln for ln in code_lines if "$argList" in ln and "-OffsiteDir" in ln]
        assert assembly, (
            "argList에 -OffsiteDir를 실어 보내는 실행 라인이 없다 — 인자를 받기만 하고 "
            "작업에 전달하지 않으면 스케줄된 회차는 오프사이트로 가지 않는다"
        )

    def test_runbook_does_not_reference_a_nonexistent_flag(self) -> None:
        """런북이 안내하는 플래그가 스크립트에 실재하는가 (가정 기반 런북 금지).

        2026-09-03에 실제로 존재하지 않는 -BackupArgs를 안내할 뻔했다.
        """
        runbook = (
            Path(__file__).resolve().parents[2]
            / "docs"
            / "architecture"
            / "db_backup_dr_runbook.md"
        ).read_text(encoding="utf-8")
        register = (_BACKUP_DIR / "register_backup_schedule.ps1").read_text(encoding="utf-8")
        for flag in re.findall(r"register_backup_schedule\.ps1([^\n]*)", runbook):
            for opt in re.findall(r"-([A-Z][A-Za-z]+)", flag):
                assert (
                    f"${opt}" in register or f"-{opt}" in register
                ), f"런북이 register_backup_schedule.ps1에 없는 플래그 -{opt} 를 안내한다"


# ===========================================================================
# C-2. 컨테이너 경유 pg_restore (2026-09-03 Phaiakes9 실사용 결함)
#
# 초판은 호스트 PATH의 pg_restore만 받았는데, 런북의 전제는 "호스트에 PostgreSQL
# 클라이언트 불요 — 전 과정이 컨테이너 안에서 실행된다"이다. 그 전제를 정확히
# 지키는 환경에서 이 검증은 영구 exit 2가 됐고, 게이트 G-backup-offsite-move의
# 반출 검증이 거기서 멈췄다. 아래는 그 회귀를 막는다.
# ===========================================================================
class TestContainerPgRestore:
    def test_host_mode_argv_is_unchanged(self, tmp_path: Path) -> None:
        """기본(호스트) 경로는 종전과 같아야 한다 — 회귀 방지."""
        target = tmp_path / "a.dump"
        assert vb.pg_restore_list_argv(target) == ["pg_restore", "--list", str(target)]

    def test_docker_mode_mounts_parent_readonly_and_targets_by_name(self, tmp_path: Path) -> None:
        """★ 컨테이너 안에서는 **마운트 경로**로 파일을 가리켜야 한다.

        호스트 절대경로를 그대로 넘기면 컨테이너 안에 그 경로가 없어 pg_restore가
        '파일 없음'으로 비0을 낸다. 그러면 ①(잠김) 축이 암호화 여부와 무관하게 항상
        통과해, 평문을 .age로 개명만 한 산출물도 잠김 판정을 받는다 — 검사가 위장이 된다.
        """
        target = tmp_path / "whymath_x.dump.age"
        argv = vb.pg_restore_list_argv(target, docker_image="pgvector/pgvector:pg16")

        assert argv[:3] == ["docker", "run", "--rm"], "일회용 실행이어야 한다"
        assert f"{tmp_path}:{vb._CONTAINER_MOUNT}:ro" in argv, "부모 디렉터리를 읽기 전용으로"
        assert (
            argv[-1] == f"{vb._CONTAINER_MOUNT}/{target.name}"
        ), "컨테이너 내부 경로로 가리켜야 한다"
        assert str(target) not in argv, "호스트 절대경로가 컨테이너 인자로 새면 안 된다"
        assert "pgvector/pgvector:pg16" in argv

    def test_docker_mode_mount_is_read_only(self, tmp_path: Path) -> None:
        """검사가 백업 산출물을 건드릴 이유가 없다 — 쓰기 가능 마운트는 거부한다."""
        argv = vb.pg_restore_list_argv(tmp_path / "a.age", docker_image="img")
        mount = argv[argv.index("-v") + 1]
        assert mount.endswith(":ro"), f"읽기 전용이 아니다: {mount}"

    def test_docker_mode_does_not_require_host_pg_restore(self, tmp_path: Path) -> None:
        """★ 컨테이너 모드에서 호스트 pg_restore 부재가 판정 불가를 만들면 안 된다.

        이것이 이 결함의 본체다 — 요구하는 도구가 모드에 따라 달라야 한다.
        docker 자체가 없는 환경에서는 여전히 2가 맞으므로 그 경우는 분기해 확인한다.
        """
        enc = tmp_path / "x.dump.age"
        enc.write_bytes(b"age-encrypted-not-really")
        identity = tmp_path / "id.key"
        identity.write_text("dummy\n", encoding="utf-8")

        code = vb.main(
            [
                str(enc),
                "--identity",
                str(identity),
                "--age-bin",
                _AGE or "age",
                "--pg-restore-bin",
                "/nonexistent/pg_restore",
                "--pg-restore-docker-image",
                "pgvector/pgvector:pg16",
            ]
        )
        if shutil.which("docker") is None or _AGE is None:
            assert code == 2, "docker·age가 없으면 판정 불가가 맞다"
        else:
            assert code != 2, (
                "컨테이너 모드인데 호스트 pg_restore 부재로 판정 불가가 났다 — "
                "요구 도구 분기가 동작하지 않는다"
            )

    def test_missing_host_pg_restore_names_the_container_workaround(
        self, tmp_path: Path, capsys
    ) -> None:
        """실패에 **대처**가 남아야 한다 — 무엇이 없는지만 알리면 사람이 거기서 막힌다.

        2026-09-03 실사용에서 Kiki가 정확히 여기서 멈췄다: exit 2 메시지가 pg_restore
        부재만 말하고 다음 수를 말하지 않았다.
        """
        enc = tmp_path / "x.dump.age"
        enc.write_bytes(b"whatever")
        identity = tmp_path / "id.key"
        identity.write_text("dummy\n", encoding="utf-8")

        code = vb.main(
            [
                str(enc),
                "--identity",
                str(identity),
                "--age-bin",
                _AGE or "age",
                "--pg-restore-bin",
                "/nonexistent/pg_restore",
            ]
        )
        assert code == 2
        err = capsys.readouterr().err
        assert "--pg-restore-docker-image" in err, "대처 경로를 알려주지 않는다"


# ===========================================================================
# D. PR #968 리뷰 회귀 — 텍스트 동결이 잡지 못한 3건
# ===========================================================================
class TestReviewRegressions:
    """Codex 리뷰(2026-09-01) 지적 3건의 회귀 봉인.

    세 건 모두 **계약 테스트가 green인 채로 통과했다**. 이유가 각각 다르다:
      ① BOM — 필드명은 대조했지만 *PS1이 쓴 바이트를 파이썬이 읽는 경로*는 실행된 적이 없다
              (샌드박스·CI에 PowerShell이 없다). 텍스트 동결의 구조적 사각이다.
      ② 미배선 — "상태 대장이 누락을 관측한다"고 선언만 하고 그 대장을 *읽는 주체*를
              배선하지 않았다. "정본화를 집행으로 착각한 완료 선언"의 이 PR 판본.
      ③ 이중 답 — 같은 실행이 JSON과 종료코드로 서로 다른 판정을 냈다.
    """

    # ── ① BOM ──
    def test_reader_accepts_a_bom_written_by_powershell(self, tmp_path: Path) -> None:
        """★ PS 5.1이 붙이는 UTF-8 BOM을 실제 바이트로 재현해 판독을 검사한다.

        `Set-Content -Encoding UTF8`은 BOM을 붙인다. 순수 utf-8로 읽으면
        `JSONDecodeError: Unexpected UTF-8 BOM`이 나고, 그러면 **성공한 백업마다
        신선도 검사가 실패**한다 — 탐지기가 정상을 사고로 신고하는 역방향 무증상 실패.
        """
        path = tmp_path / bs.STATUS_FILENAME
        payload = {
            "last_success_utc": "2026-09-01T03:00:00+00:00",
            "artifact": "whymath_20260901_030000.dump.age",
            "size_bytes": 4096,
            "encrypted": True,
            "recipients_fingerprint": "qmm59p6",
        }
        # utf-8-sig로 쓰면 BOM이 붙는다 — PS 5.1 산출물의 바이트 수준 재현.
        path.write_text(json.dumps(payload), encoding="utf-8-sig")
        assert path.read_bytes().startswith(b"\xef\xbb\xbf"), "픽스처가 BOM을 안 만들었다"

        status = bs.load_status(path)
        assert status is not None
        assert status.artifact.endswith(".dump.age")
        assert status.encrypted is True

    def test_reader_still_accepts_bom_free_files(self, tmp_path: Path) -> None:
        """utf-8-sig가 BOM 없는 파일도 그대로 읽는다 — 관용이 한쪽을 깨뜨리지 않았다."""
        path = tmp_path / bs.STATUS_FILENAME
        bs.record_success(path, artifact="a.dump.age", size_bytes=1, encrypted=True)
        assert not path.read_bytes().startswith(b"\xef\xbb\xbf")
        assert bs.load_status(path) is not None

    def test_writer_does_not_emit_a_bom(self) -> None:
        """PS1이 BOM 없이 쓴다 — 읽기 관용성에만 기대지 않는다(양쪽 다 고친다)."""
        code = _dump_code()
        assert (
            "New-Object System.Text.UTF8Encoding $false" in code
        ), "상태 파일 쓰기가 BOM-free UTF-8이 아니다"
        assert (
            "Set-Content -Path $tmp -Encoding UTF8" not in code
        ), "BOM을 붙이는 Set-Content -Encoding UTF8이 되살아났다 (PS 5.1)"

    # ── ② 신선도 검사 배선 ──
    def test_check_task_is_registered_not_just_documented(self) -> None:
        """★ 대장을 *읽는 주체*가 스케줄로 배선돼 있다.

        사람이 기억해서 돌리는 검사는 검사가 아니다 — 그것이 바로 이 PR이 없애려던
        조용한 누락과 같은 실패 양식이다.
        """
        code = _schedule_code()
        assert '$checkTaskName = "$TaskName-Check"' in code, "검사 태스크 등록이 없다"
        assert "Register-ScheduledTask -TaskName $checkTaskName" in code
        assert "check_backup_freshness.ps1" in code, "검사 스크립트를 부르지 않는다"

    def test_check_task_registration_is_verified_by_reading_back(self) -> None:
        """검사 태스크도 되읽어 LogonType을 판정한다 — 백업 태스크와 같은 기준."""
        code = _schedule_code()
        reg = code.index("Register-ScheduledTask -TaskName $checkTaskName")
        after = code[reg:]
        assert "Get-ScheduledTask -TaskName $checkTaskName" in after
        assert (
            '"$checkLogon" -ne "S4U"' in after
        ), "검사 태스크의 LogonType을 판정하지 않는다 — 무인 상태에서 조용히 멈춘다"

    def test_unregister_removes_both_tasks(self) -> None:
        """백업만 지우면 없어진 백업을 영원히 알리는 검사기가 남는다."""
        code = _schedule_code()
        assert 'foreach ($name in @($TaskName, "$TaskName-Check"))' in code

    def test_alert_clears_on_recovery(self) -> None:
        """★ 알림이 회복 시 사라진다 — 안 사라지는 알림은 가구가 되고, 그러면
        진짜 알림도 안 보인다."""
        code = _check_code()
        assert "function Clear-Alert" in code
        assert "Remove-Item $alertPath -Force" in code
        assert (
            "Clear-Alert" in code.split("if ($code -eq 0)")[1][:200]
        ), "정상 판정 경로에서 알림 파일을 지우지 않는다"

    def test_checker_undecidable_is_exit_two(self) -> None:
        """도구·모듈 부재는 2 — '검사 못 함'이 '문제 없음'(0)으로 접히지 않는다."""
        code = _check_code()
        assert code.count("exit 2") >= 3, "판정 불가 경로가 2로 끝나지 않는다"
        assert "exit 2" in code.split("checker missing")[1][:200]

    def test_checker_records_why_it_could_not_run(self) -> None:
        """실행기 부재도 증거를 남긴다 — 예외를 삼키지 않고 타입명을 적는다."""
        code = _check_code()
        assert "} catch {" in code, "실행기 부재는 예외로 난다(ErrorActionPreference=Stop)"
        assert (
            "$_.Exception.GetType().Name" in code
        ), "예외 타입명이 알림에 남지 않는다 — 무타입 경고 금지"

    def test_checker_does_not_shadow_the_automatic_args_variable(self) -> None:
        """`$args`는 PowerShell 자동 변수다 — 가리면 @args 스플래팅이 어긋난다."""
        code = _check_code()
        assert "$args = @(" not in code
        assert "$checkArgs = @(" in code

    # ── ③ JSON과 종료코드의 단일 판정 ──
    def test_json_verdict_reflects_the_encryption_requirement(self, tmp_path: Path) -> None:
        """★ 평문 산출물을 --json --require-encrypted로 검사하면 JSON도 실패를 말한다.

        이전 판은 JSON이 `{"ok": true, "reason": "fresh"}`인데 exit는 1이었다 —
        같은 실행이 두 개의 다른 답을 내고, JSON 소비자는 반출 금지 산출물을 정상으로 읽는다.
        """
        bs.main(
            [
                "record",
                "--backup-dir",
                str(tmp_path),
                "--artifact",
                "a.dump",
                "--size-bytes",
                "10",
                "--encrypted",
                "false",
            ]
        )
        import io
        from contextlib import redirect_stdout

        buf = io.StringIO()
        with redirect_stdout(buf):
            code = bs.main(
                [
                    "check",
                    "--backup-dir",
                    str(tmp_path),
                    "--require-encrypted",
                    "--json",
                ]
            )
        payload = json.loads(buf.getvalue())
        assert code == 1
        assert payload["ok"] is False, "JSON이 평문 산출물을 정상으로 보고한다"
        assert payload["reason"] == "plaintext_artifact"

    def test_json_and_exit_code_never_disagree(self, tmp_path: Path) -> None:
        """네 가지 상태 전부에서 payload['ok']와 종료코드가 일치한다."""
        import io
        from contextlib import redirect_stdout

        def run(*argv: str) -> tuple[int, dict]:
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = bs.main(["check", "--backup-dir", str(tmp_path), "--json", *argv])
            return rc, json.loads(buf.getvalue())

        # ⓐ 기록 없음
        rc, pl = run()
        assert (rc == 1) is (pl["ok"] is False)
        # ⓑ 신선 + 암호화
        bs.record_success(
            tmp_path / bs.STATUS_FILENAME, artifact="a.age", size_bytes=1, encrypted=True
        )
        rc, pl = run("--require-encrypted")
        assert rc == 0 and pl["ok"] is True and pl["reason"] == "fresh"
        # ⓒ 신선 + 평문 + 요구 없음 → 통과
        bs.record_success(
            tmp_path / bs.STATUS_FILENAME, artifact="a.dump", size_bytes=1, encrypted=False
        )
        rc, pl = run()
        assert rc == 0 and pl["ok"] is True
        # ⓓ 신선 + 평문 + 요구 있음 → 실패, 양쪽 일치
        rc, pl = run("--require-encrypted")
        assert rc == 1 and pl["ok"] is False and pl["reason"] == "plaintext_artifact"

    def test_staleness_beats_encryption_in_the_reason(self, tmp_path: Path) -> None:
        """오래됐으면 사유는 stale — 암호화 여부는 물을 대상이 없다(우선순위 고정)."""
        now = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)
        path = tmp_path / bs.STATUS_FILENAME
        bs.record_success(
            path,
            artifact="a.dump",
            size_bytes=1,
            encrypted=False,
            moment=now - timedelta(hours=100),
        )
        verdict = bs.evaluate_backup_health(
            bs.load_status(path), max_age_hours=48, require_encrypted=True, now=now
        )
        assert verdict.reason == "stale"
