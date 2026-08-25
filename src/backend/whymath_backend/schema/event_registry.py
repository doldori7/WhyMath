"""Education Event Registry — EventType별 계약 단일 진실원.

`data/education_event_registry.json`을 런타임에 로드하여 event_type별
schema_version, domain, required_fields, PII classification, retention,
producer, consumer, status를 관리한다. 신규 이벤트 추가 시 이 registry와
`event_taxonomy.py` enum을 동시에 갱신한다.

거버넌스:
- `tests/backend/schema/test_event_registry.py`가 ① 모든 EducationEventType이
  registry에 등록되어 있거나 명시적 exemption ② required_fields가 봉투/페이로드에
  존재 ③ deprecated event의 replacement_event 연결을 검증.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field

from whymath_backend.schema.event_taxonomy import (
    EducationEventDomain,
    EducationEventType,
    EventPrivacyClassification,
    EventStatus,
)


class EventRegistryEntry(BaseModel):
    """개별 이벤트 타입의 registry 항목."""

    model_config = ConfigDict(extra="forbid", use_enum_values=True, str_strip_whitespace=True)

    event_type: EducationEventType = Field(..., description="이벤트 유형")
    schema_version: str = Field(..., description="이벤트 스키마 버전")
    domain: EducationEventDomain = Field(..., description="도메인")
    description: str = Field(..., description="설명")

    producer: list[str] = Field(default_factory=list, description="생산 서비스 목록")
    consumer: list[str] = Field(default_factory=list, description="소비 서비스 목록")

    required_fields: list[str] = Field(default_factory=list, description="봉투/페이로드 필수 필드")
    optional_fields: list[str] = Field(default_factory=list, description="선택 필드")

    pii_classification: EventPrivacyClassification = Field(
        default=EventPrivacyClassification.PSEUDONYMOUS, description="PII 등급"
    )
    retention_policy_id: str | None = Field(default=None, description="보존 정책 ID")
    analytics_allowed: bool = Field(default=True, description="분석 사용 허용")
    ai_training_allowed: bool = Field(default=False, description="AI 학습 사용 허용")

    status: EventStatus = Field(default=EventStatus.ACTIVE, description="상태")
    deprecated_at: str | None = Field(default=None, description="deprecated 일자")
    replacement_event: EducationEventType | None = Field(default=None, description="대체 이벤트")


@dataclass(frozen=True)
class EventRegistry:
    """로드된 registry. event_type으로 조회."""

    entries: dict[EducationEventType, EventRegistryEntry]
    exemptions: frozenset[EducationEventType]

    def get(self, event_type: EducationEventType) -> EventRegistryEntry | None:
        """event_type의 registry 항목을 반환. 미등록이면 None."""
        return self.entries.get(event_type)

    def requires(self, event_type: EducationEventType, field: str) -> bool:
        """event_type이 field를 required로 요구하는가."""
        entry = self.entries.get(event_type)
        if entry is None:
            return False
        return field in entry.required_fields

    def is_active(self, event_type: EducationEventType) -> bool:
        """event_type이 active 상태인가."""
        entry = self.entries.get(event_type)
        if entry is None:
            return event_type in self.exemptions
        return entry.status == EventStatus.ACTIVE


class EventRegistryLoader:
    """Registry JSON을 로드하는 정적/런타임 로더."""

    _REGISTRY_FILENAME: ClassVar[str] = "education_event_registry.json"

    @classmethod
    def default_path(cls) -> Path:
        """레포 루트 기준 기본 registry 경로."""
        # whymath_backend 패키지가 설치된 위치에서 레포 루트를 유추.
        backend_root = Path(__file__).resolve().parent.parent.parent.parent.parent
        return backend_root / "data" / cls._REGISTRY_FILENAME

    @classmethod
    def load(cls, path: Path | None = None) -> EventRegistry:
        """JSON registry를 로드한다."""
        registry_path = path or cls.default_path()
        if not registry_path.exists():
            # registry 파일이 없으면 빈 registry + enum 전체 exemption 반환
            return EventRegistry(entries={}, exemptions=frozenset(EducationEventType))

        raw = json.loads(registry_path.read_text(encoding="utf-8"))
        entries: dict[EducationEventType, EventRegistryEntry] = {}
        exemptions: set[EducationEventType] = set()

        for item in raw.get("entries", []):
            entry = EventRegistryEntry.model_validate(item)
            entries[entry.event_type] = entry

        for etype_name in raw.get("exemptions", []):
            try:
                exemptions.add(EducationEventType(etype_name))
            except ValueError:
                # 잘못된 exemption은 무시 — 거버넌스 테스트가 잡음
                continue

        return EventRegistry(entries=entries, exemptions=frozenset(exemptions))


def _build_default_registry() -> EventRegistry:
    """registry 파일이 없을 때 사용하는 최소 fallback registry.

    운영/CI에서는 `data/education_event_registry.json` 파일을 강제해야 한다.
    """
    return EventRegistry(entries={}, exemptions=frozenset(EducationEventType))


# 런타임 singleton registry. 레포 루트 기준 JSON 파일을 로드한다.
# 파일이 없으면 모든 enum을 exemption으로 처리(개발 중 임시).
_DEFAULT_PATH = (
    Path(__file__).resolve().parent.parent.parent.parent.parent
    / "data"
    / "education_event_registry.json"
)
try:
    DEFAULT_REGISTRY: EventRegistry = EventRegistryLoader.load(_DEFAULT_PATH)
except Exception:  # pragma: no cover - 파일 누락 시 fallback
    DEFAULT_REGISTRY = _build_default_registry()
