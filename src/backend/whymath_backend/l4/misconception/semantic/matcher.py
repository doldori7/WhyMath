"""오개념 의미(임베딩) 매처 — substring 거짓음성 보완 (slice 104).

각 카탈로그 항목의 *표현*(틀린 믿음의 자연어, `f"{name_kr}. {canonical_statement}"`)을
사전 임베딩해 벡터 인덱스에 적재하고, 학생 텍스트를 임베딩해 코사인 유사도 상위 후보 중
임계값 이상만 `MisconceptionMatch`로 돌려준다. `diagnose()`(substring+regex)와 *독립된
추가 API*다 — `diagnose`의 시그니처·동작은 건드리지 않는다(하위호환).

────────────────────────────────────────────────────────────────────────────
가치와 정직 스코프 (CLAUDE.md "확실하지 않을 때 자신 있게 말함 금지")
────────────────────────────────────────────────────────────────────────────
가치(O): substring AND가 못 잡던 *패러프레이즈·동의어*를 잡는다(의미 recall). 예: 카탈로그
표현과 어휘가 다른데 같은 오개념을 말한 학생 풀이를 코사인으로 매칭.

한계(X·과장 금지): 임베딩은 *방향·부정·등치*를 못 가린다 — "연속이면 미분가능"과 올바른
역방향 "미분가능하면 연속"은 의미상 가까워 둘 다 높은 유사도가 나온다(substring과 동일한
방향맹). "f∘g≠g∘f"(올바른 비가환 진술)도 카탈로그 "f∘g=g∘f"와 가깝다. 따라서 의미 매처는
*후보를 넓힐* 뿐 방향을 판별하지 못하며, 그 판별은 LLM-judged/NLI = **후속 슬라이스**다.
이 한계는 테스트(test_misconception_semantic.py)에서 *방향맹 정직 테스트*로 못 박혀 있다.

confidence 매핑: `confidence = min(1.0, max(0.0, cosine))`. 코사인을 [0,1]로 클램프한다(음수·
직교는 0; 부동소수로 평행 시 1.0을 미세 초과하는 경우는 1.0 상한). (cos+1)/2 대신 이 매핑을
택한 이유: ① 임계값(코사인)과 confidence가 *같은 축*이라 "임계값 미만은 미매칭"이 confidence
로도 일관되고, ② 무관 텍스트가 0.5 confidence로 부풀지 않는다(보수적). 표면 근접도 원본은
`semantic_similarity`에 *클램프 없이* 보존한다(원 코사인 [-1,1] — 디버그·랭킹 분석용).

CI hermetic: 매처는 EmbeddingProvider·VectorIndex 좌석에만 의존한다 — 단위테스트는
FakeEmbeddingProvider를 주입해 라이브 모델 없이 배선·임계값·랭킹·하위호환을 검증한다.
"""

from __future__ import annotations

from whymath_backend.config import Settings, get_settings
from whymath_backend.l4.misconception.catalog import CATALOG
from whymath_backend.l4.misconception.models import Misconception, MisconceptionMatch
from whymath_backend.l4.misconception.semantic.index import (
    InMemoryVectorIndex,
    VectorIndex,
)
from whymath_backend.l4.misconception.semantic.provider import EmbeddingProvider

_DEFAULT_TOP_K = 3


def catalog_text(m: Misconception) -> str:
    """카탈로그 항목을 임베딩할 자연어 표현으로 직렬화 — `"{name_kr}. {canonical_statement}"`.

    *틀린 믿음의 자연어*를 임베딩해 학생의 (패러프레이즈된) 틀린 진술과 가까워지게 한다.
    name_kr(짧은 라벨)와 canonical_statement(잘못된 진술)를 합쳐 신호를 키운다. signals/
    regex_signals(토큰·정규식)는 *표면 매칭*용이라 의미 임베딩엔 넣지 않는다.
    """
    return f"{m.name_kr}. {m.canonical_statement}"


class SemanticMatcher:
    """카탈로그 의미 매처 — 항목 표현을 사전 임베딩(인덱스 구축)하고 학생 텍스트와 코사인 비교.

    구성 시(또는 첫 매칭 시) 카탈로그 *각 항목 표현*을 한 번 임베딩해 VectorIndex에 적재하고
    캐시한다(카탈로그는 프로세스 수명 동안 고정). 이후 매칭은 학생 텍스트 1건만 임베딩해
    인덱스를 질의한다 → 항목당 임베딩 재계산 없음.

    provider는 주입 필수(좌석) — 테스트는 FakeEmbeddingProvider, 프로덕션은 provider.
    build_provider(local/openai)를 넣는다. index는 선택(미주입 시 InMemoryVectorIndex 자체
    생성)·영속은 PgVectorIndex 주입.

    **prebuilt_index 모드(영속 사전 임베딩 재사용)**: `prebuilt_index=True`면 카탈로그를 *재임베딩
    하지 않고*(자체 적재 단락) 주입된 인덱스를 *그대로 질의*한다 — `populate_pgvector`로 한 번
    채워둔 PgVectorIndex를 매 프로세스/매 호출이 재임베딩 없이 공유한다(라이브 진단 경로의 항목당
    재임베딩 비용 0·프로세스 간 공유). 이 모드는 *채워진* 인덱스 주입을 요구한다(index=None이면
    ValueError — 빈 인덱스 질의는 무의미). 기본(False)은 종전대로 첫 매칭 시 1회 자체 적재.

    적재 순서는 *카탈로그 순서*(=doc 명시 순서)로 맞춘다 → 인덱스 동률 정렬이 카탈로그
    순서를 안정 유지(diagnose의 동률 안정성과 같은 규약). prebuilt 모드에선 적재 순서를
    populate_pgvector가 카탈로그 순서로 보장한다(같은 규약).
    """

    def __init__(
        self,
        *,
        provider: EmbeddingProvider,
        index: VectorIndex | None = None,
        catalog: tuple[Misconception, ...] = CATALOG,
        prebuilt_index: bool = False,
    ) -> None:
        if prebuilt_index and index is None:
            raise ValueError(
                "prebuilt_index=True는 *사전적재된* 인덱스 주입을 요구합니다 — index=None은 빈 "
                "InMemoryVectorIndex라 질의가 비어 무의미합니다. populate_pgvector로 채운 "
                "PgVectorIndex(또는 사전적재된 InMemoryVectorIndex)를 넘기세요."
            )
        self._provider = provider
        self._index: VectorIndex = index if index is not None else InMemoryVectorIndex()
        self._catalog = catalog
        # 인덱스 키(misconception.id) → 항목 역참조. *주입된 카탈로그* 기준으로 만든다
        # (전역 CATALOG_BY_ID가 아님 — 커스텀 카탈로그 주입 시에도 해석되도록).
        self._by_id: dict[str, Misconception] = {m.id: m for m in catalog}
        # prebuilt_index면 카탈로그 *재임베딩*을 건너뛴다(_ensure_built 단락) — 인덱스가 이미
        # populate_pgvector 등으로 채워졌다고 신뢰한다(라이브 진단 경로의 항목당 재임베딩 0).
        # _by_id 역참조는 *임베딩 없이* 카탈로그에서 만든다(hit.key→Misconception 해석에 필요).
        self._built = prebuilt_index

    def _ensure_built(self) -> None:
        """카탈로그 표현을 *1회* 임베딩해 인덱스에 적재(지연·캐시).

        provider.embed를 *배치 1회* 호출해 전 항목을 임베딩한다(라이브 모델 왕복 최소화).
        카탈로그 순서대로 add → 동률 유사도 시 카탈로그 순서 안정 유지.
        """
        if self._built:
            return
        texts = [catalog_text(m) for m in self._catalog]
        vectors = self._provider.embed(texts)
        if len(vectors) != len(self._catalog):
            raise RuntimeError(
                f"임베딩 개수({len(vectors)})가 카탈로그 개수({len(self._catalog)})와 다릅니다 "
                "— provider.embed가 입력 순서·길이를 보존해야 합니다."
            )
        for m, vec in zip(self._catalog, vectors, strict=True):
            self._index.add(m.id, vec)
        self._built = True

    def match(
        self,
        student_solution: str,
        *,
        top_k: int = _DEFAULT_TOP_K,
        threshold: float,
    ) -> list[MisconceptionMatch]:
        """학생 텍스트 → 의미 유사 오개념 후보(코사인 임계값 이상만, 유사도 내림차순).

        빈 텍스트·top_k<=0은 빈 리스트. 인덱스를 *threshold 통과 후보 수만큼 넉넉히* 질의해
        (top_k가 임계값 필터 이전 컷이 되지 않게) 임계값으로 거른 뒤 top_k로 자른다.
        confidence=min(1.0, max(0.0, cosine))(클램프), semantic_similarity=원 코사인.
        """
        if not student_solution or top_k <= 0:
            return []
        self._ensure_built()
        # 임계값 필터가 top_k보다 *먼저* 후보를 잘라내지 않도록 전 항목을 질의한다(N=30,
        # 선형 스캔이라 저렴). 그 뒤 임계값 통과분만 남기고 top_k로 컷.
        query_vec = self._provider.embed([student_solution])[0]
        hits = self._index.search(query_vec, top_k=len(self._catalog))
        results: list[MisconceptionMatch] = []
        for hit in hits:
            if hit.similarity < threshold:
                # search는 유사도 내림차순이므로 첫 미달에서 끊어도 되지만, 명시적으로
                # continue하지 않고 break해 의도를 분명히 한다(이후는 전부 미달).
                break
            misconception = self._by_id.get(hit.key)
            if misconception is None:  # pragma: no cover — 인덱스 키는 항상 카탈로그 id
                continue
            # confidence는 [0,1] 클램프(MisconceptionMatch 제약). 코사인은 부동소수로
            # 평행 시 1.0을 *미세 초과*(1.0000000000000002)할 수 있어 1.0으로 상한 — 음수는
            # 0으로 하한(무관·반대 의미). semantic_similarity는 원 코사인을 그대로 보존.
            confidence = min(1.0, max(0.0, hit.similarity))
            results.append(
                MisconceptionMatch(
                    misconception=misconception,
                    confidence=confidence,
                    # substring/regex 경로가 아니므로 표면 신호는 비움(빈 튜플 기본).
                    semantic_similarity=hit.similarity,
                )
            )
            if len(results) >= top_k:
                break
        return results


def semantic_matches(
    student_solution: str,
    *,
    provider: EmbeddingProvider,
    index: VectorIndex | None = None,
    top_k: int = _DEFAULT_TOP_K,
    threshold: float | None = None,
) -> list[MisconceptionMatch]:
    """학생 풀이에서 *의미 유사* 오개념 후보를 반환한다(substring `diagnose`와 독립·추가 API).

    `diagnose()`는 *불변*이고, 이 함수는 임베딩 기반 *recall 보완* 경로다. provider는 필수
    좌석(테스트는 Fake, 프로덕션은 build_provider). threshold 미지정 시 Settings.
    misconception_semantic_threshold(기본 0.55 보수적)를 쓴다.

    **정직 스코프**(모듈 docstring): 패러프레이즈·동의어 recall은 개선하나 방향·부정·등치는
    못 가린다(임베딩 방향맹). 방향 판별은 LLM-judged/NLI 후속. 반환 매치의
    `semantic_similarity`는 표면 근접도(진단 신뢰 ≠).

    매 호출이 SemanticMatcher를 새로 만들어 카탈로그를 재임베딩한다 — 라이브 모델에선 비싸다.
    호출자(오케스트레이터)는 SemanticMatcher 인스턴스를 *재사용*해 사전 임베딩을 캐시하는
    것이 정석이다(이 함수는 일회성·테스트·간편 진입점). 영속(pgvector) 사전 임베딩은 후속.
    """
    resolved_threshold = threshold if threshold is not None else _resolved_threshold_from_settings()
    matcher = SemanticMatcher(provider=provider, index=index)
    return matcher.match(student_solution, top_k=top_k, threshold=resolved_threshold)


def _resolved_threshold_from_settings(settings: Settings | None = None) -> float:
    """기본 임계값 해석 — 주입 우선, 없으면 전역 Settings(보수적 0.55)."""
    resolved = settings if settings is not None else get_settings()
    return resolved.misconception_semantic_threshold
