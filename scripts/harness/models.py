"""빌드 하네스 데이터 모델 — 태스크·게이트·트랙.

전부 '빌드 관리 메타데이터'다. 제품 런타임(src/backend)의 Subject enum·
개념 그래프·문항 스키마를 일절 참조하지 않는다(subject_pack_spec_v1.md의
"Subject enum ADD VALUE 금지"와 무충돌 — 비침투 원칙).

의존성: 표준 라이브러리만 사용(dataclasses). 루트에 파이썬 프로젝트가 없어
어떤 환경에서도 python3 단독으로 임포트 가능해야 한다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# ── enum (튜플 = 순서 있는 폐쇄 집합) ────────────────────────────────────────

# worktree 도메인 화이트리스트(scripts/new-session-worktree.sh)와 동일 7종.
# 계층 경계를 넘는 작업은 계층별 태스크로 분할해야 한다(1세션=1도메인 규칙 정합).
LAYERS: tuple[str, ...] = (
    "backend",
    "data-pipeline",
    "ml-models",
    "mobile",
    "web",
    "docs",
    "infra",
)

# 도메인 소유 지도 — docs/standards/parallel_sessions.md §1의 코드화.
# 태스크 paths가 이 프리픽스를 벗어나면 '경고'만 한다(횡단 태스크가 실재하므로 error 금지).
LAYER_PATH_HINTS: dict[str, tuple[str, ...]] = {
    "backend": ("src/backend/",),
    "data-pipeline": ("src/data-pipeline/", "data/", "docs/data/"),
    "ml-models": ("src/ml-models/",),
    "mobile": ("src/mobile/",),
    "web": ("src/web/",),
    "docs": ("docs/",),
    "infra": ("infra/", ".github/"),
}

# ad-hoc 편집 감지 대상 — claim 없이 이 폴더를 편집하면 adhoc_edit 정책 적용.
# (MEMORY.md·docs·backlog 등 메타 파일은 제외 — 코드 도메인만)
CODE_DOMAIN_PREFIXES: tuple[str, ...] = (
    "src/",
    "infra/",
)

# 과목 축 — 개방 확장: 새 과목은 이 튜플에 1줄 추가로 끝난다.
# (문명 전체를 교육적으로 다루는 E축 로드맵 수용 — subject_expansion_e_axis_v1.md)
SUBJECTS: tuple[str, ...] = (
    "math",           # 수학 (중·고·대학)
    "physics",        # E1 물리
    "chemistry",      # E2 화학
    "biology",        # E3 생물
    "earth-science",  # 지구과학 (E축 배치 미정 — 결정 태스크로 추적)
    "social",         # E4 역사·사회 (경제·역사·세계사 포함)
    "economics",      # 경제학 (E4 세분)
    "history",        # 역사 (E4 세분)
    "world-history",  # 세계사 (E4 세분)
    "korean",         # E5 국어
    "english",        # E6 영어
    "cross",          # 과목 횡단 (인프라·아키텍처 등)
)

STATUSES: tuple[str, ...] = (
    "todo",
    "in_progress",
    "blocked",
    "review",
    "done",
    "cancelled",
)

# 상태 전이표 — CLI가 강제한다 (임의 점프 금지)
STATUS_TRANSITIONS: dict[str, tuple[str, ...]] = {
    "todo": ("in_progress", "blocked", "cancelled"),
    "in_progress": ("review", "done", "blocked", "todo"),
    "blocked": ("todo", "cancelled"),
    "review": ("done", "in_progress"),
    "done": (),        # 종결 상태
    "cancelled": (),   # 종결 상태
}

OWNERS: tuple[str, ...] = ("claude", "kiki", "partner")

GATE_KINDS: tuple[str, ...] = ("human", "external", "decision")
GATE_STATUSES: tuple[str, ...] = ("pending", "cleared", "waived")

# 정책 강제 수준 — 단계적 도입(warn 관측 → 측정 → block 승격)의 폐쇄 집합
POLICY_MODES: tuple[str, ...] = ("off", "warn", "block")

# 태스크 ID 규칙: <스테이지 또는 접두>-<번호>-<슬러그> (파일명 stem과 동일해야 함)
TASK_ID_RE = re.compile(r"^[A-Z][A-Z0-9]{0,7}-\d{2}(-[a-z0-9]+(-[a-z0-9]+)*)?$")
GATE_ID_RE = re.compile(r"^G-[a-z0-9]+(-[a-z0-9]+)*$")

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@dataclass
class Task:
    """백로그 태스크 1건 = backlog/tasks/<id>.yaml 1파일."""

    id: str
    title: str
    track: str
    stage: str
    subject: str = "math"
    layer: str = "backend"
    status: str = "todo"
    priority: int = 3                       # 1(최고)~5
    owner: str = "claude"
    depends_on: list[str] = field(default_factory=list)
    requires_gates: list[str] = field(default_factory=list)
    acceptance: list[str] = field(default_factory=list)
    artifacts: list[str] = field(default_factory=list)   # done 시 PR/커밋 필수
    paths: list[str] = field(default_factory=list)       # 이 태스크가 만질 파일 glob (레포 상대 — 겹침 검사용)
    session: str | None = None              # claim한 브랜치 (병렬 세션 소유권)
    notes: str = ""
    updated: str = ""                       # YYYY-MM-DD, 상태 변경 시 CLI가 갱신

    def validate(self) -> list[str]:
        """스키마 위반 목록 반환 (빈 리스트 = 정상)."""
        errors: list[str] = []
        if not TASK_ID_RE.match(self.id):
            errors.append(f"{self.id}: 태스크 ID 형식 위반 (예: S1-06-phaiakes9-live)")
        if not self.title.strip():
            errors.append(f"{self.id}: title 누락")
        if not self.track.strip():
            errors.append(f"{self.id}: track 누락")
        if self.subject not in SUBJECTS:
            errors.append(f"{self.id}: subject '{self.subject}' 미등록 (models.SUBJECTS)")
        if self.layer not in LAYERS:
            errors.append(f"{self.id}: layer '{self.layer}' 미등록 (worktree 7종만 허용)")
        if self.status not in STATUSES:
            errors.append(f"{self.id}: status '{self.status}' 미등록")
        if not isinstance(self.priority, int) or not 1 <= self.priority <= 5:
            errors.append(f"{self.id}: priority는 1~5 정수여야 함 (현재 {self.priority!r})")
        if self.owner not in OWNERS:
            errors.append(f"{self.id}: owner '{self.owner}' 미등록")
        if self.status == "done" and not self.artifacts:
            errors.append(f"{self.id}: done인데 artifacts 비어 있음 (PR/커밋 링크 필수)")
        if self.status == "in_progress" and not self.session:
            errors.append(f"{self.id}: in_progress인데 session(claim 브랜치) 없음")
        if self.updated and not DATE_RE.match(self.updated):
            errors.append(f"{self.id}: updated 는 YYYY-MM-DD 형식이어야 함")
        for gid in self.requires_gates:
            if not GATE_ID_RE.match(gid):
                errors.append(f"{self.id}: 게이트 ID 형식 위반 '{gid}' (G-... 소문자 kebab)")
        # paths는 레포 상대 POSIX 경로만 — 비어있음은 위반 아님(기존 태스크 소급 오염 방지)
        for pattern in self.paths:
            if pattern.startswith("/"):
                errors.append(f"{self.id}: paths '{pattern}' 절대경로 금지 (레포 상대만)")
            elif ".." in pattern.split("/"):
                errors.append(f"{self.id}: paths '{pattern}' 상위 참조(..) 금지")
            elif "\\" in pattern:
                errors.append(f"{self.id}: paths '{pattern}' 백슬래시 금지 (POSIX 구분자만)")
            elif not pattern.strip():
                errors.append(f"{self.id}: paths에 빈 패턴 포함")
        return errors

    def layer_drift_warnings(self) -> list[str]:
        """paths가 layer 도메인 지도 밖을 가리키면 경고 목록 반환 (error 아님 — 횡단 태스크 허용)."""
        hints = LAYER_PATH_HINTS.get(self.layer)
        if not hints or not self.paths:
            return []
        warnings: list[str] = []
        for pattern in self.paths:
            if not any(pattern.startswith(h) for h in hints):
                warnings.append(
                    f"{self.id}: paths '{pattern}' 이 layer '{self.layer}' 도메인({', '.join(hints)}) 밖"
                )
        return warnings


@dataclass
class Gate:
    """사람/외부 게이트 — Kiki 수동 대기 항목의 추적·리마인드 단위."""

    id: str
    title: str
    kind: str = "human"                     # human|external|decision
    assignee: str = "kiki"
    status: str = "pending"                 # pending|cleared|waived
    requested: str = ""                     # YYYY-MM-DD
    remind_after_days: int | None = None    # 경과 시 SessionStart 브리핑에 리마인드
    evidence: str | None = None             # cleared 시 근거(커밋/문서) 필수
    notes: str = ""

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not GATE_ID_RE.match(self.id):
            errors.append(f"{self.id}: 게이트 ID 형식 위반 (예: G-phaiakes9-key)")
        if not self.title.strip():
            errors.append(f"{self.id}: title 누락")
        if self.kind not in GATE_KINDS:
            errors.append(f"{self.id}: kind '{self.kind}' 미등록")
        if self.status not in GATE_STATUSES:
            errors.append(f"{self.id}: status '{self.status}' 미등록")
        if self.status == "cleared" and not self.evidence:
            errors.append(f"{self.id}: cleared인데 evidence 없음 (근거 필수)")
        if self.requested and not DATE_RE.match(self.requested):
            errors.append(f"{self.id}: requested 는 YYYY-MM-DD 형식이어야 함")
        return errors

    @property
    def passed(self) -> bool:
        """태스크 착수를 허용하는 상태인가."""
        return self.status in ("cleared", "waived")


@dataclass
class Track:
    """트랙 = 로드맵의 큰 줄기 (수학 완성 / 다과목 확장 / 인프라 상환)."""

    id: str
    title: str
    roadmap_ref: str = ""
    entry_gate: str | None = None           # 미통과 시 트랙 전체가 next 후보 제외

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.title.strip():
            errors.append(f"{self.id}: 트랙 title 누락")
        if self.entry_gate and not GATE_ID_RE.match(self.entry_gate):
            errors.append(f"{self.id}: entry_gate ID 형식 위반 '{self.entry_gate}'")
        return errors


@dataclass
class Policy:
    """조율 정책 — 중복·겹침 감지의 강제 수준 (backlog/policy.yaml).

    단계적 도입: 전 rule warn으로 시작 → events.ndjson의 policy_warn 측정 →
    승격 기준 충족 시 rule별 block 승격 (측정 없는 도입 없음).
    파일 부재 시 전부 기본값 = 하위호환 (기존 저장소 동작 불변).
    """

    version: int = 1
    path_overlap: str = "warn"      # 태스크 paths 교차 (start 프리플라이트·check-edit ②)
    scope_drift: str = "warn"       # 내 claim 태스크의 paths 밖 편집 (check-edit ①)
    adhoc_edit: str = "warn"        # claim 없이 코드 도메인 편집 (check-edit ③)
    claim_ttl_hours: int = 72       # 원격 claim stale 판정 TTL
    remote_claims: bool = True      # 원격 claim(refs/claims/*) 사용 여부

    def validate(self) -> list[str]:
        errors: list[str] = []
        for rule in ("path_overlap", "scope_drift", "adhoc_edit"):
            mode = getattr(self, rule)
            if mode not in POLICY_MODES:
                errors.append(f"policy.{rule}: '{mode}' 미등록 (허용: {list(POLICY_MODES)})")
        if not isinstance(self.claim_ttl_hours, int) or self.claim_ttl_hours < 1:
            errors.append(f"policy.claim_ttl_hours: 1 이상 정수여야 함 (현재 {self.claim_ttl_hours!r})")
        if not isinstance(self.remote_claims, bool):
            errors.append(f"policy.remote_claims: bool이어야 함 (현재 {self.remote_claims!r})")
        return errors


@dataclass
class Backlog:
    """backlog/ 전체의 메모리 표현."""

    stage_order: list[str] = field(default_factory=list)
    tracks: dict[str, Track] = field(default_factory=dict)
    gates: dict[str, Gate] = field(default_factory=dict)
    tasks: dict[str, Task] = field(default_factory=dict)

    def stage_index(self, stage: str) -> int:
        """stage_order 상의 위치 (미등록 stage는 맨 뒤)."""
        try:
            return self.stage_order.index(stage)
        except ValueError:
            return len(self.stage_order)
