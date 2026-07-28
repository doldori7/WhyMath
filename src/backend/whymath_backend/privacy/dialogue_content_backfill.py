"""미성년 대화 봉투 암호화 *백필* ops CLI — 평문 저장된 `dialogue_turn` 세 축 전환.

감사상환 #2 — 대화 본문 봉투 암호화(`_crypto`·coach.py 결선)는 *신규* 턴만 암호화하고 기존
평문 행은 잔존한다. 마스터 키 도입 후 기존 행을 점진 전환하는 *백필* 표면이 여기다
(device `PgDeviceStore.reencrypt_plaintext_secrets` 선례·retention_purge_cli ops 컨벤션 미러:
전역 배치는 HTTP 미노출·스크립트가 직접 돈다).

**SEC-01: 세 축을 함께 처리한다** — `content`(본문)·`image_uri`(손글씨 URI)·`image_analysis`
(Qwen3-VL 분석). 본문만 백필하면 운영자가 `{"reencrypted": N}`을 보고 "평문 전환 완료"로
읽는데 이미지 평문은 그대로 남는다 — **부분 처리를 완전 처리로 위장**하는 정확히 그 함정이다.

동작: 세 축 중 *하나라도* 평문(`<축>_encrypted IS NULL AND <축> IS NOT NULL`)인 행을
batch_size개까지 골라, **평문인 축만** 암호화해 `<축>_encrypted`/`<축>_nonce`를 채우고 평문
컬럼을 NULL로 비운다. 이미 암호화된 축은 건드리지 않는다(idempotent). 키 미설정(cipher None)
이면 no-op(0). CLI는 0 반환까지 반복해 전체 백필(대형 테이블 메모리/락 보호).

사용법:
    python -m whymath_backend.privacy.dialogue_content_backfill [--batch-size N]

`WHYMATH_DIALOGUE_CONTENT_ENCRYPTION_KEY` 미설정이면 즉시 0(암호화 비활성). 종료 코드 0.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from typing import Any

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.api._crypto import SupportsEnvelope, build_dialogue_content_cipher

__all__ = ["main", "reencrypt_plaintext_dialogue_content"]


def _serialize_analysis(value: Any) -> str:
    """JSONB 축은 구조라 바이트로 못 바꾼다 — 저장 좌석과 **동일한 결정론 직렬화**를 쓴다.

    `api/_crypto.encrypt_dialogue_image_analysis`와 규칙이 어긋나면 백필한 행만 복호 결과가
    달라지므로(재현성 붕괴) 규칙을 여기서 다시 쓰지 않고 동일 인자로 맞춘다.
    """
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


async def reencrypt_plaintext_dialogue_content(
    session: AsyncSession,
    cipher: SupportsEnvelope | None,
    *,
    batch_size: int = 100,
) -> int:
    """평문 저장된 대화 세 축을 봉투 암호화로 전환(백필) — 재암호화한 *행* 수 반환.

    세 축(`content`·`image_uri`·`image_analysis`) 중 하나라도 평문(`<축>_encrypted IS NULL AND
    <축> IS NOT NULL`)인 행을 batch_size개까지 골라, **평문인 축만** 암호화해 ciphertext/nonce를
    채우고 평문 컬럼을 NULL로 비운다. 이미 암호화된 축·값이 없는 축은 건드리지 않는다
    (idempotent). cipher 미설정이면 0(no-op). 호출자가 0 반환까지 반복해 전체 백필.
    `session.commit`은 여기서(device 배치 선례 — 1 배치 = 1 커밋).

    반환값이 *행* 수인 점에 유의 — 한 행에서 세 축을 동시에 전환해도 1이다(진행 종료 조건이
    "더 이상 평문 행이 없음"이라 행 단위가 맞다).
    """
    if cipher is None:
        return 0
    from whymath_backend.db.models.dialogue import DialogueTurn

    plaintext_content = DialogueTurn.content_encrypted.is_(None) & DialogueTurn.content.is_not(None)
    plaintext_uri = DialogueTurn.image_uri_encrypted.is_(None) & DialogueTurn.image_uri.is_not(None)
    # SEC-04: `IS NOT NULL`만으로는 부족하다 — 이미 저장된 **JSONB 스칼라 `null`** 행이 여기
    # 걸린다(모델 `none_as_null=True` 이전에 쓰인 행). 그 행은 암호화할 값이 없어 `values`가
    # 비고 count가 안 오르는데, LIMIT 창은 차지한다 → 진짜 평문 행이 뒤로 밀려 **영영 처리되지
    # 않고** CLI는 "0행 처리"를 완료로 보고한다(2026-07-28 실 PG 재현). `jsonb_typeof`로 실제
    # 값이 있는 행만 대상에 넣어 굶주림을 없앤다.
    plaintext_analysis = (
        DialogueTurn.image_analysis_encrypted.is_(None)
        & DialogueTurn.image_analysis.is_not(None)
        & (func.jsonb_typeof(DialogueTurn.image_analysis) != "null")
    )
    sel = (
        select(
            DialogueTurn.turn_id,
            DialogueTurn.content,
            DialogueTurn.content_encrypted,
            DialogueTurn.image_uri,
            DialogueTurn.image_uri_encrypted,
            DialogueTurn.image_analysis,
            DialogueTurn.image_analysis_encrypted,
        )
        .where(or_(plaintext_content, plaintext_uri, plaintext_analysis))
        .limit(batch_size)
    )
    result = await session.execute(sel)
    count = 0
    for row in result.all():
        turn_id, content, content_enc, uri, uri_enc, analysis, analysis_enc = row
        values: dict[str, Any] = {}
        if content is not None and content_enc is None:
            ciphertext, nonce = cipher.encrypt(content)
            values |= {"content": None, "content_encrypted": ciphertext, "content_nonce": nonce}
        if uri is not None and uri_enc is None:
            ciphertext, nonce = cipher.encrypt(uri)
            values |= {
                "image_uri": None,
                "image_uri_encrypted": ciphertext,
                "image_uri_nonce": nonce,
            }
        if analysis is not None and analysis_enc is None:
            ciphertext, nonce = cipher.encrypt(_serialize_analysis(analysis))
            values |= {
                "image_analysis": None,
                "image_analysis_encrypted": ciphertext,
                "image_analysis_nonce": nonce,
            }
        if not values:  # 방어적 — WHERE로 이미 배제되나 명시(무한 루프 방지)
            continue
        await session.execute(
            update(DialogueTurn).where(DialogueTurn.turn_id == turn_id).values(**values)
        )
        count += 1
    await session.commit()
    return count


async def _run_backfill(batch_size: int) -> int:  # pragma: no cover — 실 DB(integration)
    """전체 백필 — cipher 조립 후 0 반환까지 배치 반복. 총 재암호화 행수 반환."""
    from whymath_backend.config import get_settings
    from whymath_backend.db.session import get_sessionmaker

    settings = get_settings()
    cipher = build_dialogue_content_cipher(settings)
    if cipher is None:
        return 0
    total = 0
    sessionmaker = get_sessionmaker(settings)
    while True:
        async with sessionmaker() as session:
            n = await reencrypt_plaintext_dialogue_content(session, cipher, batch_size=batch_size)
        total += n
        if n == 0:
            break
    return total


def main(argv: list[str] | None = None) -> int:
    """CLI 엔트리 — 평문 대화 본문을 봉투 암호화로 전환하고 `{reencrypted: N}` JSON을 stdout에 낸다.

    `--batch-size`(기본 100)로 1 배치 크기 조절. 키 미설정이면 0(암호화 비활성·정상). 종료 코드 0.
    """
    parser = argparse.ArgumentParser(
        prog="python -m whymath_backend.privacy.dialogue_content_backfill",
        description=(
            "미성년 대화 평문 행(dialogue_turn의 content·image_uri·image_analysis)을 봉투 "
            "암호화로 백필 전환 (감사상환 #2·SEC-01·CLAUDE.md '미성년 채팅 평문 저장 금지')."
        ),
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="1 배치당 재암호화 행 수(기본 100·메모리/락 보호).",
    )
    args = parser.parse_args(argv)
    total = asyncio.run(_run_backfill(args.batch_size))
    print(json.dumps({"reencrypted": total}))
    return 0


if __name__ == "__main__":  # pragma: no cover — 엔트리포인트, main이 테스트 대상
    sys.exit(main())
