"""개념 표시이름(name_ko) locale 재소싱 — `graph.json`의 형제 `locales/ko.json` 조인 헬퍼.

Part 9 STRICT 재-ID(P2d)로 `name_ko`/`name_en`/`name_ja`가 identity 노드(`graph.json`)에서
**제거**됐다(Concept Purity — 표시이름은 개념이 아니라 *투영*). 표시이름은 이제 `graph.json`의
형제 파일 `locales/{lang}.json`(`{canonical_id: name}`)이 단일 진실이다.

이 모듈은 세 backend 로더(`node_projection`·`backend_concept`·`embedding`)가 공유하는 **단일
헬퍼**를 둔다 — 각 로더가 개별로 파일을 읽지 않고 여기서 `{concept_id: name_ko}` 맵을 만든다
(drift 차단·단일 진실 경로). 값은 재-ID 전 노드 내장 `name_ko`와 **바이트 동일**이라 임베딩
표현·text_hash가 불변이다(재임베딩 0).

역호환: 옛 `graph.json`(name_ko가 아직 노드에 내장돼 있고 `locales/`가 없는 경우)은 `{}`를
돌려주고, 로더는 노드 내장 `name_ko`를 우선한다(`record.get("name_ko") or locale_ko.get(id)`).
따라서 옛/새 `graph.json` 둘 다 graceful.

7계층: L1 데이터 기반의 *표시이름 투영 소싱*. 순수 파일 IO(json·pathlib)·의존 0.
"""

from __future__ import annotations

import json
from pathlib import Path

# graph.json 형제 위치의 locale 디렉토리·한국어 파일명(data-pipeline `transform-v1` co-generate).
_LOCALES_DIRNAME: str = "locales"
_KO_FILENAME: str = "ko.json"


def load_locale_ko(graph_path: Path) -> dict[str, str]:
    """`graph.json` 경로 → 형제 `locales/ko.json`의 `{canonical_id: name_ko}` 맵.

    `graph_path.parent / "locales" / "ko.json"`를 읽어 canonical concept_id → 한국어 표시이름
    맵을 돌려준다. 파일이 없으면(옛 graph.json·locale 미분리) `{}`(로더가 노드 내장 name_ko로
    fallback). 값이 str이 아니거나 빈 문자열인 항목은 제외한다(오염 방어 — 조용한 빈 이름 금지).

    JSON 최상위가 dict가 아니면(오염) `{}`로 안전 처리한다.
    """
    ko_path = graph_path.parent / _LOCALES_DIRNAME / _KO_FILENAME
    if not ko_path.exists():
        return {}
    payload = json.loads(ko_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return {}
    out: dict[str, str] = {}
    for key, value in payload.items():
        if not isinstance(value, str):
            continue
        name = value.strip()
        if name:
            out[str(key)] = name
    return out


__all__ = ["load_locale_ko"]
