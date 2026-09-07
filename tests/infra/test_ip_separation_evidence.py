"""[IP-SEP] 겸직 IP 귀속 증빙 생성기의 계약 동결 — **양방향** 변별력.

왜 이 테스트가 있는가
--------------------
이 도구의 산출물은 **투자 실사에 제출되는 사실 자료**다. 그래서 여기서 가장
비싼 실패는 "틀린 숫자"가 아니라 **"괜찮아 보이는 실패"**다:

  · shallow 클론에서 나온 "혼입 0건"은 잘린 이력에 대한 참일 뿐인데, 리포트에
    실리면 그대로 거짓 진술이 된다.
  · author만 검사하는 신원 검사는 재직사 계정이 committer로만 찍힌 커밋을
    **조용히 통과**시킨다.
  · 오프셋이 섞인 이력에서 현지시각을 그대로 세면 서로 다른 벽시계를 한
    히스토그램에 합치는 셈인데, 그래도 그럴듯한 표가 나온다.

CLAUDE.md "보호 장치를 실패 주입 없이 '보호 있음'으로 선언 금지"에 따라, 모든
축을 **정상 입력에서 침묵 · 결함 입력에서 발화**하는 쌍으로 동결한다. 결함
주입만 확인하면 *모든* 입력에서 발화하는 검사도 절반은 통과하기 때문이다.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import threading
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location(
    "ip_separation_evidence",
    Path(__file__).resolve().parents[2] / "scripts" / "ops" / "ip_separation_evidence.py",
)
assert _spec and _spec.loader
_mod = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _mod  # @dataclass 조회 대비 — exec 전 등록
_spec.loader.exec_module(_mod)

Commit = _mod.Commit
classify_identities = _mod.classify_identities
environment_profile = _mod.environment_profile
time_profile = _mod.time_profile
ai_profile = _mod.ai_profile
evaluate_thresholds = _mod.evaluate_thresholds
collect = _mod.collect
parse_coauthors = _mod.parse_coauthors
person_authored = _mod.person_authored
build_scope = _mod.build_scope
looks_like_signed_binary = _mod.looks_like_signed_binary
stream_commits = _mod.stream_commits
EvidenceError = _mod.EvidenceError
DEFAULT_REVS = _mod.DEFAULT_REVS
marker_of = _mod.marker_of
scan_tracked_documents = _mod.scan_tracked_documents
SIGNED_MARKER = _mod.SIGNED_MARKER
TEMPLATE_MARKER = _mod.TEMPLATE_MARKER
render = _mod.render
main = _mod.main
LIMITS = _mod.LIMITS
DEFAULT_TOOL_IDENTITIES = _mod.DEFAULT_TOOL_IDENTITIES

PERSONAL = {"kiki@example.com"}
TOOL = set(DEFAULT_TOOL_IDENTITIES)


def commit(
    sha: str = "a" * 40,
    *,
    an: str = "kiki",
    ae: str = "kiki@example.com",
    cn: str = "GitHub",
    ce: str = "noreply@github.com",
    ad: str = "2026-03-07T22:10:00+09:00",
    subject: str = "feat: 무언가",
    coauthors=None,
) -> Commit:
    """정상 커밋 — 어떤 신호도 내면 안 되는 기준점."""
    return Commit(sha, an, ae, cn, ce, ad, ad, subject, coauthors or [])


# ── IDENT-01 신원 혼입 ─────────────────────────────────────────────────────
def test_clean_history_is_silent() -> None:
    """정상 침묵 — 개인·도구 신원만 있는 이력에서는 신호가 없어야 한다."""
    _, findings = classify_identities([commit(), commit("b" * 40)], PERSONAL, TOOL)
    assert findings == []


def test_employer_author_fires() -> None:
    """결함 발화 — 재직사 도메인이 author면 IDENT-01."""
    dirty = commit("c" * 40, ae="kiki@employer.co.kr")
    _, findings = classify_identities([commit(), dirty], PERSONAL, TOOL)
    assert [f.code for f in findings] == ["IDENT-01"]
    assert "employer.co.kr" in findings[0].subject
    assert "cccccccccccc" in findings[0].detail


def test_employer_committer_only_fires() -> None:
    """**author만 보는 검사는 이 커밋을 놓친다** — committer 축의 결함 주입.

    이 테스트가 뮤테이션 표적이다: `classify_identities`에서 committer 순회를
    지우면 위 test_employer_author_fires는 여전히 GREEN이고 이것만 RED가 된다.
    """
    dirty = commit("d" * 40, ce="build@employer.co.kr", cn="사내빌드")
    _, findings = classify_identities([dirty], PERSONAL, TOOL)
    assert [f.code for f in findings] == ["IDENT-01"]
    assert findings[0].subject.startswith("committer:")


def test_tool_identity_is_not_foreign() -> None:
    """도구 신원(GitHub 웹 머지 서명 등)은 혼입이 아니다 — 오탐 방어."""
    _, findings = classify_identities([commit()], PERSONAL, TOOL)
    assert findings == []
    _, findings2 = classify_identities([commit()], PERSONAL, set())
    assert [f.code for f in findings2] == ["IDENT-01"]  # 도구 선언을 빼면 잡힌다


def test_identity_matching_is_case_insensitive() -> None:
    """이메일 대소문자 변형으로 검사를 우회할 수 없다."""
    _, findings = classify_identities([commit(ae="KiKi@Example.COM")], PERSONAL, TOOL)
    assert findings == []


def test_findings_carry_a_prescription() -> None:
    """신호에는 사람이 다음에 할 일이 붙는다 — 코드만 던지지 않는다."""
    _, findings = classify_identities([commit(ae="x@employer.co.kr")], PERSONAL, TOOL)
    assert findings[0].prescription


# ── ENV-01 환경 분포 ───────────────────────────────────────────────────────
def test_environment_profile_separates_offsets() -> None:
    """오프셋별로 나뉘어 세어진다 — KST와 그 외가 한 칸에 합쳐지면 안 된다."""
    env = environment_profile(
        [
            commit(ad="2026-03-07T22:10:00+09:00"),
            commit(ad="2026-03-07T09:10:00-04:00"),
            commit(ad="2026-03-07T13:10:00+00:00"),
        ]
    )
    assert env["by_author_utc_offset"] == {"+09:00": 1, "-04:00": 1, "+00:00": 1}
    assert env["local_kst_commits"] == 1
    assert env["non_kst_commits"] == 2


# ── TIME-01 시각 분포 ──────────────────────────────────────────────────────
def test_time_profile_converts_everything_to_kst() -> None:
    """**모든 커밋을 KST로 환산**한다 — 현지시각을 그대로 세면 안 된다.

    결함 주입 표적: `.astimezone(KST)`를 빼면 아래 -04:00 커밋이 09시로 세어져
    업무시간 1건이 된다(정답은 22시·업무시간 0건).
    """
    tp = time_profile([commit(ad="2026-03-07T09:10:00-04:00")])  # = 2026-03-07 22:10 KST
    assert tp["by_hour_kst"]["22"] == 1
    assert tp["work_hours_commits"] == 0


def test_work_hours_counts_weekday_business_hours() -> None:
    """정상 발화 — 평일 낮 커밋은 업무시간으로 센다."""
    tp = time_profile([commit(ad="2026-03-05T14:00:00+09:00")])  # 목요일
    assert tp["work_hours_commits"] == 1
    assert tp["work_hours_ratio"] == 1.0


def test_weekend_daytime_is_not_work_hours() -> None:
    """주말 낮은 업무시간이 아니다 — 요일 조건의 결함 주입 표적."""
    tp = time_profile([commit(ad="2026-03-07T14:00:00+09:00")])  # 토요일
    assert tp["work_hours_commits"] == 0
    assert tp["off_hours_commits"] == 1


def test_work_hours_boundaries_are_half_open() -> None:
    """09:00은 포함, 18:00은 제외 — 경계 정의를 못박는다."""
    tp = time_profile(
        [
            commit(ad="2026-03-05T09:00:00+09:00"),
            commit(ad="2026-03-05T18:00:00+09:00"),
        ]
    )
    assert tp["work_hours_commits"] == 1


def test_threshold_absent_is_silent() -> None:
    """임계를 주지 않으면 판정하지 않는다 — 임의의 기본 임계를 두지 않는다."""
    tp = time_profile([commit(ad="2026-03-05T14:00:00+09:00")])
    assert evaluate_thresholds(tp, work_hours_threshold=None) == []


def test_threshold_given_fires_above_and_stays_silent_below() -> None:
    """임계를 준 사람에게만, 그리고 **넘었을 때만** 신호가 간다 — 양방향."""
    tp = time_profile([commit(ad="2026-03-05T14:00:00+09:00")])  # 비율 1.0
    assert [f.code for f in evaluate_thresholds(tp, work_hours_threshold=0.5)] == ["TIME-01"]
    assert evaluate_thresholds(tp, work_hours_threshold=1.0) == []


# ── AI-01 ─────────────────────────────────────────────────────────────────
def test_ai_profile_counts_tool_authored_commits() -> None:
    """AI 저작 커밋은 별도로 센다 — 판정이 아니라 실사 대비 사실 자료다."""
    prof = ai_profile([commit(), commit("e" * 40, an="Claude", ae="noreply@anthropic.com")], TOOL)
    assert prof["tool_authored_commits"] == 1
    assert prof["tool_involved_ratio"] == 0.5


# ── 렌더 계약 ──────────────────────────────────────────────────────────────
def test_limits_are_always_rendered() -> None:
    """증명 한계는 **옵션이 아니다** — 정상 리포트에도 항상 실린다.

    이 도구의 산출물을 읽는 사람은 git 메타데이터의 증명력을 과대평가하기 쉽다.
    한계 문단이 조건부가 되면 가장 좋은 리포트에서 가장 먼저 사라진다.
    """
    report = _mod.Report(
        status="ok",
        total_commits=1,
        identities={
            "declared_personal": ["kiki@example.com"],
            "declared_tool": [],
            "by_author": {"kiki <kiki@example.com>": 1},
            "by_committer": {"kiki <kiki@example.com>": 1},
            "foreign_identities": {},
        },
        environments=environment_profile([commit()]),
        time_profile=time_profile([commit()]),
        ai_profile=ai_profile([commit()], TOOL),
    )
    text = render(report)
    assert "증명하지 **못하는** 것" in text
    for limit in LIMITS:
        assert limit.split("—")[0].strip()[:20] in text


def test_failed_report_refuses_to_look_like_evidence() -> None:
    """수집 실패 리포트는 표를 그리지 않고 사용 금지를 명시한다."""
    text = render(_mod.Report(status="shallow", message="shallow 클론"))
    assert "수집 실패" in text
    assert "증빙으로 쓰지 말" in text
    assert "혼입" not in text  # 판정처럼 읽히는 문구가 새어 나오면 안 된다


# ── 수집 실패 경로 (실제 git 저장소) ────────────────────────────────────────
def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """커밋 2건짜리 실 저장소 — 개인 신원 1건 + 도구 신원 1건."""
    root = tmp_path / "origin"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.name", "kiki")
    _git(root, "config", "user.email", "kiki@example.com")
    # 개발자 머신의 전역 설정이 이 fixture를 깨지 않게 한다 — 서명 키가 없는 곳에서
    # commit.gpgsign=true면 커밋 자체가 실패하고, 그 실패는 이 도구와 무관하다.
    _git(root, "config", "commit.gpgsign", "false")
    for i in (1, 2):
        (root / f"f{i}.txt").write_text(str(i), encoding="utf-8")
        _git(root, "add", ".")
        _git(
            root,
            "-c",
            f"user.date=2026-03-0{i}T22:00:00+09:00",
            "commit",
            "-q",
            "--date",
            f"2026-03-0{i}T22:00:00+09:00",
            "-m",
            f"커밋 {i}",
        )
    return root


def test_shallow_clone_is_not_ok(repo: Path, tmp_path: Path) -> None:
    """**측정 실패 ≠ 통과** — 잘린 이력의 '혼입 0건'을 증빙으로 내보내지 않는다.

    이 계약이 이 파일에서 가장 중요하다. shallow에서 status=ok가 나오면 리포트는
    사실과 무관하게 깨끗해 보이고, 그 리포트가 실사에 제출된다.
    """
    shallow = tmp_path / "shallow"
    subprocess.run(
        ["git", "clone", "--depth", "1", "-q", repo.as_uri(), str(shallow)],
        check=True,
        capture_output=True,
    )
    report = collect(shallow, personal=PERSONAL, tool=TOOL)
    assert report.status == "shallow"
    assert report.total_commits == 0
    assert "unshallow" in report.message
    assert main(["--root", str(shallow), "--identity", "kiki@example.com"]) == 2


def test_missing_identity_declaration_is_not_ok(repo: Path) -> None:
    """개인 신원을 선언하지 않으면 혼입 판정이 성립하지 않는다 — exit 2.

    빈 allowlist로 돌리면 **모든 신원이 혼입**으로 잡혀 리포트가 무의미해진다.
    그 상태를 exit 1(신호 있음)로 내면 '검사했다'처럼 읽힌다.
    """
    report = collect(repo, personal=set(), tool=TOOL)
    assert report.status == "error"
    assert "--identity" in report.message
    assert main(["--root", str(repo)]) == 2


def test_zero_commits_is_failure_not_pass(repo: Path) -> None:
    """스캔 0건은 성공이 아니다 — 공허하게 통과하는 전수 가드 방지."""
    report = collect(repo, personal=PERSONAL, tool=TOOL, since="2030-01-01")
    assert report.status == "error"
    assert "0건" in report.message
    assert (
        main(["--root", str(repo), "--identity", "kiki@example.com", "--since", "2030-01-01"]) == 2
    )


def test_not_a_git_repo_names_the_exception_type(tmp_path: Path) -> None:
    """침묵 실패 금지 — 실패 메시지에 **예외 타입명**이 들어간다."""
    plain = tmp_path / "plain"
    plain.mkdir()
    report = collect(plain, personal=PERSONAL, tool=TOOL)
    assert report.status == "error"
    assert "GitExitError" in report.message or "Error" in report.message


# ── 증거 보존 (③ 실패해도 증거가 남는다) ────────────────────────────────────
def test_jsonl_records_every_commit(repo: Path, tmp_path: Path) -> None:
    """커밋 1건마다 즉시 flush — 도중에 죽어도 그 시점까지가 남는다."""
    sink = tmp_path / "nested" / "commits.jsonl"  # 부모 디렉터리도 만들어야 한다
    report = collect(repo, personal=PERSONAL, tool=TOOL, jsonl=sink)
    assert report.status == "ok"
    lines = sink.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == report.total_commits == 2
    assert json.loads(lines[0])["author_email"] == "kiki@example.com"


def test_jsonl_is_flushed_before_the_run_finishes(repo: Path, tmp_path: Path) -> None:
    """**즉시** flush인지 확인한다 — 파일을 닫을 때 한꺼번에 쓰는 것과 구별한다.

    `sink.flush()`만 지우면 파일은 결국 close 시점에 채워지므로, 끝난 뒤에 줄 수만
    세는 검사는 정상/결함 양쪽에서 같은 값을 낸다("변별력 없는 검증 스텝 금지").
    그래서 제너레이터를 **1건에서 멈춘 채** 파일을 읽는다.
    """
    sink = tmp_path / "partial.jsonl"
    gen = _mod.stream_commits(repo, jsonl=sink)
    try:
        next(gen)  # 커밋 1건만 소비하고 멈춘다
        assert len(sink.read_text(encoding="utf-8").splitlines()) == 1
    finally:
        gen.close()


def test_out_dir_writes_both_formats(repo: Path, tmp_path: Path) -> None:
    """실사 제출용 JSON + Markdown 한 쌍을 남긴다."""
    out = tmp_path / "out"
    assert main(["--root", str(repo), "--identity", "kiki@example.com", "--out", str(out)]) == 0
    payload = json.loads((out / "ip_separation_evidence.json").read_text(encoding="utf-8"))
    assert payload["status"] == "ok"
    assert payload["limits"] == LIMITS  # 한계는 기계 판독 산출물에도 실린다
    assert "IP 귀속 분리 증빙" in (out / "ip_separation_evidence.md").read_text(encoding="utf-8")


def test_exit_code_separates_clean_from_foreign(repo: Path) -> None:
    """판정은 exit code로 한다 — 출력 문자열 매칭이 아니다(양방향)."""
    assert main(["--root", str(repo), "--identity", "kiki@example.com"]) == 0
    # 개인 신원 선언을 다른 사람으로 바꾸면 같은 이력이 전부 혼입이 된다
    assert main(["--root", str(repo), "--identity", "other@example.com"]) == 1


# ── 서명 실물 유출 가드 ────────────────────────────────────────────────────
_REPO = Path(__file__).resolve().parents[2]


def test_marker_is_the_whole_first_line() -> None:
    """마커는 **첫 줄 전체**다 — 본문에 인용한 문서가 위반으로 잡히면 안 된다.

    이 가드를 "이 문자열이 어디든 있으면 위반"으로 만들면 마커를 *설명하는*
    런북·템플릿 주의문이 전부 걸리고, 그 오탐을 피하려 예외를 넣는 순간 가드가
    스스로 구멍이 된다. 그래서 위치를 계약으로 삼는다(양방향).
    """
    assert marker_of(SIGNED_MARKER) == "signed"
    assert marker_of(f"  {SIGNED_MARKER}  \n") == "signed"  # 공백은 허용
    assert marker_of(TEMPLATE_MARKER) == "template"
    assert marker_of(f"이 문서의 실물은 `{SIGNED_MARKER}` 로 표시한다") is None
    assert marker_of("# 제목") is None


def test_no_signed_document_is_tracked() -> None:
    """**기입·서명된 실물이 저장소에 커밋되지 않았다.**

    `.gitignore`는 `git add -f` 한 번이면 뚫린다 — 이 검사가 2차 방어다.
    """
    found = scan_tracked_documents(_REPO)
    assert found["signed"] == [], f"서명 실물이 추적되고 있다: {found['signed']}"
    assert found.get("unreadable", []) == []


def test_marker_scan_actually_walks_the_tree() -> None:
    """**스캔 0건은 실패다** — 대상을 못 찾은 전수 가드는 공허하게 통과한다.

    위 검사가 초록인 이유가 "서명 실물이 없어서"인지 "아무것도 안 훑어서"인지
    구별하는 유일한 축이다. 템플릿 2건이 잡히면 스캐너가 실제로 돈 것이다.
    """
    found = scan_tracked_documents(_REPO)
    assert len(found["template"]) >= 2, f"템플릿을 못 찾았다 — 스캐너 무효: {found}"
    assert all(f.startswith("docs/legal/templates/") for f in found["template"])


def test_evidence_outputs_are_gitignored() -> None:
    """산출물 경로가 **실제로** 무시되는지 git에게 직접 묻는다.

    `.gitignore`에 줄이 있는지 문자열로 확인하지 않는다 — 규칙은 순서·부정
    패턴·상위 규칙에 따라 뒤집힐 수 있고, 그 결과는 git만 안다(산출물 검사).
    """

    def ignored(rel: str) -> bool:
        return (
            subprocess.run(
                ["git", "check-ignore", "-q", rel], cwd=_REPO, capture_output=True
            ).returncode
            == 0
        )

    assert ignored(".ip_evidence/ip_separation_evidence.json")
    assert ignored("docs/private/ip/declaration.md")
    # 반대 방향 — 정본 템플릿까지 무시되면 가드가 아니라 사고다
    assert not ignored("docs/legal/templates/no_employer_assets_declaration_ko.md")


# ── Co-Authored-By 트레일러 (2026-09-07 리뷰 P2) ────────────────────────────
def test_parse_coauthors_reads_trailers() -> None:
    """본문의 `Co-Authored-By`를 (이름, 이메일)로 뽑는다 — 대소문자 무관."""
    body = (
        "본문 한 줄\n\n"
        "Co-Authored-By: Claude <noreply@anthropic.com>\n"
        "co-authored-by: 동료 <peer@example.com>\n"
    )
    assert parse_coauthors(body) == [
        ["Claude", "noreply@anthropic.com"],
        ["동료", "peer@example.com"],
    ]


def test_parse_coauthors_is_silent_without_trailers() -> None:
    """정상 침묵 — 트레일러가 없으면 빈 목록."""
    assert parse_coauthors("그냥 본문\nSigned-off-by: x <x@y.z>\n") == []


def test_coauthor_identity_is_scanned() -> None:
    """**공동저작자도 신원 검사를 받는다** — 잠재적 공동 권리자이기 때문이다.

    결함 주입 표적: `classify_identities`에서 coauthor 순회를 지우면 이 테스트만
    RED가 되고 author/committer 테스트는 그대로 GREEN이다.
    """
    c = commit(coauthors=[["사내동료", "peer@employer.co.kr"]])
    _, findings = classify_identities([c], PERSONAL, TOOL)
    assert [f.code for f in findings] == ["IDENT-01"]
    assert findings[0].subject.startswith("coauthor:")


def test_ai_profile_counts_coauthored_not_only_authored() -> None:
    """AI 관여는 author만 세면 크게 빗나간다 (실측 25 vs 998).

    이 저장소의 관례는 사람이 author이고 AI가 트레일러로 들어가는 형태다.
    """
    human_with_ai = commit(coauthors=[["Claude", "noreply@anthropic.com"]])
    ai_authored = commit("f" * 40, an="Claude", ae="noreply@anthropic.com")
    prof = ai_profile([human_with_ai, ai_authored, commit("0" * 40)], TOOL)
    assert prof["tool_authored_commits"] == 1
    assert prof["tool_coauthored_commits"] == 1
    assert prof["tool_involved_commits"] == 2  # 합집합


# ── 시각 분포의 모집단 (사람 저작) ──────────────────────────────────────────
def test_person_authored_excludes_tool_commits() -> None:
    """봇이 커밋한 시각은 사람이 일한 시각이 아니다 — 모집단에서 뺀다."""
    bot = commit("1" * 40, an="whymath-harness", ae="harness@whymath.invalid")
    people = person_authored([commit(), bot], TOOL)
    assert [c.sha for c in people] == ["a" * 40]


def test_harness_bot_is_a_tool_not_a_foreign_identity() -> None:
    """하네스 봇은 사람이 아니다 — 기본 도구 신원에 들어 있다.

    실측 근거: 이 신원의 932건은 전부 `harness-claims`(claim 대장 orphan 브랜치)에만
    있고 트리는 `claims/` 하나뿐이다. 다만 **숨기지는 않는다** — 신원 표에 실린다.
    """
    assert "harness@whymath.invalid" in DEFAULT_TOOL_IDENTITIES
    bot = commit("2" * 40, an="whymath-harness", ae="harness@whymath.invalid")
    profile, findings = classify_identities([bot], PERSONAL, TOOL)
    assert findings == []
    assert "whymath-harness <harness@whymath.invalid>" in profile["by_author"]


# ── 스캔 범위 (2026-09-07 리뷰 P1·P2) ──────────────────────────────────────
def test_default_scope_is_all_refs() -> None:
    """기본 범위는 HEAD가 아니라 모든 ref다 — HEAD만 보면 44%만 본다(실측)."""
    assert tuple(DEFAULT_REVS) == ("--all",)


def test_scope_marks_full_history_only_when_unfiltered() -> None:
    """전수/부분을 양방향으로 구분한다 — 부분인데 전수로 표시되면 거짓 진술이다."""
    assert build_scope(["--all"], None, refs=3, scanned=9)["is_full_history"] is True
    assert build_scope(["HEAD"], None, refs=3, scanned=9)["is_full_history"] is False
    assert build_scope(["--all"], "2026-01-01", refs=3, scanned=9)["is_full_history"] is False


def test_unreachable_commit_is_scanned(repo: Path) -> None:
    """**HEAD에서 도달할 수 없는 커밋도 검사한다.**

    이 파일에서 `test_shallow_clone_is_not_ok` 다음으로 중요한 계약이다. 초판은
    `git log HEAD`만 순회해 미머지 브랜치의 커밋을 통째로 놓쳤고, 이 저장소
    실측으로 2297건 중 1279건(56%)이 그 사각에 있었다 — 그 커밋에 재직사 신원이
    있어도 리포트는 "혼입 0건"이라고 선언했을 것이다.
    """
    _git(repo, "checkout", "-q", "-b", "side")
    (repo / "side.txt").write_text("x", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "-c", "user.email=stranger@employer.co.kr", "commit", "-q", "-m", "곁가지")
    _git(repo, "checkout", "-q", "main")

    # HEAD만 보면 침묵한다 — 이것이 초판의 상태다
    head_only = collect(repo, personal=PERSONAL, tool=TOOL, revs=("HEAD",))
    assert head_only.findings == []
    assert head_only.scope["is_full_history"] is False
    assert head_only.unmeasured  # 부분 측정임을 스스로 말한다

    # 기본(모든 ref)이면 잡는다
    full = collect(repo, personal=PERSONAL, tool=TOOL)
    # `-c user.email`은 author·committer 둘 다 바꾸므로 역할별로 2건이 정상이다.
    assert {f.code for f in full.findings} == {"IDENT-01"}
    roles = sorted(f.subject.split(":", 1)[0] for f in full.findings)
    assert roles == ["author", "committer"]
    assert all("employer.co.kr" in f.subject for f in full.findings)
    assert full.scope["is_full_history"] is True
    assert full.unmeasured == []


def test_partial_scope_report_refuses_full_history_wording(repo: Path) -> None:
    """부분 범위 리포트는 '이력 전체'라고 말하지 않는다."""
    partial = collect(repo, personal=PERSONAL, tool=TOOL, revs=("HEAD",))
    text = render(partial)
    assert "부분 측정" in text
    assert "스캔한" in text


# ── 타임아웃 집행 (2026-09-07 리뷰 P2) ─────────────────────────────────────
def test_timeout_fires_even_when_read_blocks(repo: Path, monkeypatch) -> None:
    """**블로킹 read 안에서 멈춰도** 타임아웃이 걸린다.

    초판은 `proc.stdout.read()`가 반환된 **뒤에만** deadline을 봤다. git이 출력
    없이 정지하면 그 검사 지점에 영영 도달하지 못해, 선언한 300초가 장식이 된다.
    watchdog 스레드가 프로세스를 죽여야 read가 풀린다.
    """
    released = threading.Event()

    class _BlockingStdout:
        def read(self, _n):
            released.wait(10)  # kill()이 풀어 준다 — 안 풀리면 테스트가 실패한다
            return ""

    class _FakeProc:
        stdout = _BlockingStdout()
        returncode = -9

        def kill(self):
            released.set()

        def wait(self, timeout=None):
            return self.returncode

        def poll(self):
            return self.returncode

    monkeypatch.setattr(_mod.subprocess, "Popen", lambda *a, **k: _FakeProc())
    with pytest.raises(EvidenceError) as excinfo:
        list(stream_commits(repo, timeout=0.05))
    assert "TimeoutExpired" in str(excinfo.value)
    assert released.is_set()  # watchdog이 실제로 kill했다


# ── 서명 스캔본 가드 (2026-09-07 리뷰 P2) ──────────────────────────────────
def test_signed_scan_is_detected_by_name_and_location() -> None:
    """서명 **스캔본**(PDF·이미지)은 첫 줄을 읽을 수 없다 — 이름과 위치로 본다."""
    assert looks_like_signed_binary("docs/legal/재직사자산무사용확인서.pdf")
    assert looks_like_signed_binary("anywhere/IP양도예정기록.jpg")
    assert looks_like_signed_binary("docs/legal/scan001.pdf")


def test_signed_scan_guard_does_not_overfire() -> None:
    """정상 침묵 — 정본 템플릿·일반 문서·다른 경로의 자산은 잡지 않는다."""
    assert (
        looks_like_signed_binary("docs/legal/templates/no_employer_assets_declaration_ko.md")
        is None
    )
    assert looks_like_signed_binary("docs/legal/copyright_guide_v2.md") is None
    assert looks_like_signed_binary("assets/logo.png") is None  # 법무 경로가 아니다


def test_no_signed_scan_is_tracked() -> None:
    """서명 스캔본이 저장소에 커밋되지 않았다 — 마커 스캔의 바이너리 축."""
    found = scan_tracked_documents(_REPO)
    assert found["signed_binary"] == [], f"서명 스캔본 의심: {found['signed_binary']}"
