"""rephrase 발문 위생 게이트 — LLM 발문 텍스트 결함의 결정론 검출(S3-12·순수·LLM 0).

S3-09 AI 검수(720문)가 rephrased 코퍼스에서 확정한 **발문 텍스트 결함 축**을 결정론 검사로
차단한다. rephrase의 기존 불변 봉인(`rephrase.classify_invariance_failure`)은 수치·정답·선지만
검사하고 발문 텍스트 품질 게이트가 없었다 — 그 공백으로 새어 들어온 결함류가 이 모듈의 표적:

  ① 비한글 스크립트 주입 — CJK 한자("두解")·가나("となる") 유니코드 범위. 수식·라틴 문자·통용
     기호는 수학 표기라 허용한다(따라서 "greater" 같은 라틴 영단어 주입은 이 축이 못 잡는다 —
     정직 한계·감사 폴백).
  ② 재서술 메타 라벨 누출 — 전부 폐쇄 문자열("원 발문:"·"원판"·"재서술" + rotation-1 실사례
     4건 "(원래와 같은 표현으로)"·"(대입과 계산을 통해)"·"(더 작은)"·"(주어진 방정식)"). 애초
     "괄호 안 한글+공백"을 구조 규칙으로 일반화했으나, misconception_eval_mc_generator의
     정당한 설명 문구("(일차항 계수)"·"(최대공약수는 1)"·"(단위: 도)")에서 오탐이 실측돼
     폐쇄 목록으로 후퇴(2026-07-29 rotation-1 사후 검증 — 아래 "정직 한계" 참조).
  ③ 비표준 용어·오용어 — 두 아군(모두 폐쇄 목록·경험적 실사례 기반):
     - 방정식 오명명: "원시방정식"·"다차방정식"·"원시적"('원시함수'는 정상 용어라 다치지 않음)
     - 차원/도형 오기술: "두 차원"·"두차원"·"공간에서"(1변수 방정식·수 계산 문항에 기하학적
       차원/공간 개념을 허위로 부여 — rotation-1 실사례 3건: "두 차원의 이차방정식"·"두 차원의
       원에 해당하는"·"두차원 공간에서")
     - 개념 오치환: "큰/작은 극"(이차방정식 근 문항에 미적분 극값 어휘 오적용 — "극값"·"극대"·
       "극소"는 제외해 계산형 극값 문항은 다치지 않음). "중점"(중근의 오치환)은 애초 여기
       있었으나 midpoint-sum-only 밴드의 좌표 중점 정상 용법이 실측돼 제외(아래 참조).
  ④ 요구-정답 정합 — 발문이 '방법/어떨까요'를 묻는데 정답은 값인 부정합(statement_mismatch).
     스켈레톤 원 발문은 값을 물으므로 '방법'·'어떨까요'의 등장 자체가 요구 이탈 신호다.
  ⑤ 조사 오류 — S3-12 josa 판별기(`tail_reading`)가 **결정 가능한** 토큰(수·수식 꼬리)에 한해
     조사(을/를·와/과·은/는·이/가·(으)로)의 받침 정합을 검사한다. 판별 불가 토큰은 침묵
     (오탐 0 우선 — 비문·어미 파손 등 비결정 축은 사람/감사 폴백).
  ⑥ 지수 서술구 허상 삽입(S3-12 2차 감사 발견) — "N의 제곱"·"N의 세제곱"·"N의 거듭제곱근"·
     "N의 제곱근" 같은 구는 스켈레톤 원 발문(등식만 직접 진술)에는 없는, rephrase가 만들어낸
     구문이다. rotation-1 재검수에서 잔존 확인된 실사례 3건(`wm-log-d026609848a9` "5의 제곱"인데
     실제 5**3=125, `wm-log-14bd3014b6b9` "5의 거듭제곱근"인데 실제 5**1=5, `wm-exp-e4029725f5e0`
     "625의 제곱근이면" — 문장에서 참조되지 않는 허상 절)가 전건 verify 계약과 불일치하는
     허위·무의미 주장이었다(3/3 결함 — 정상 용법이 관찰되지 않아 발견 즉시 차단). sqrt_sum
     밴드의 "N의 제곱이므로 그 제곱근은"(참으로 연결된 서술 — 오탐 24건 실측)은 부정
     lookahead로 제외(아래 참조).
  ⑦ 무변화(원본과 동일, QUAL-03 2026-08-10) — `original_text`(선택 인자·기본 None)를 넘겼을
     때만 활성화되는 축. `question_text`가 원 발문과 정규화(NFC+공백축약) 후 완전 일치하면
     위반이다. 다른 6축과 달리 "발문 자체의 문법 결함"이 아니라 "발문이 원본에서 실질적으로
     안 바뀜"을 검사한다 — rephrase 수용 게이트(`rephrase.classify_invariance_failure`)가
     rephrase 직후 원문을 넘겨줄 때만 의미가 있다(상세는 아래 함수 정의 앞 주석).

  ②③⑥은 "이 문구가 나오면 반드시 결함"이 아니라 "이 문구는 이 코퍼스 맥락에서 관찰된 적
  없는 정상 용법이 없다"는 경험적 근거로 차단한다(정직 한계 — 향후 정상 용법 발견 시 재검토).
  **2026-07-29 재검토 실측(정직 기록)**: 이 게이트는 rephrase 전용이 아니라
  `TestTextHygieneS312`(misconception_eval_mc_generator 단위테스트)를 통해 **다른 결정론
  생성기의 설명 문구에도 공유 적용**된다 — "관찰된 적 없다"는 rephrased_v0/generated_v0
  대조만으로는 불충분했다. ②의 일반 정규식(괄호+한글+공백)과 ③의 "중점"이 그 코퍼스에서
  정당한 용법과 충돌해 폐쇄 목록/제외로 후퇴했고, ⑥은 "이므로"로 이어지는 참인 서술을
  부정 lookahead로 배제했다. 향후 새 축을 추가할 때는 **rephrased_v0 단독이 아니라
  전 문제코퍼스(공유 생성기 포함) 대조가 재검증 범위다**.
  **잔존 한계(정직 기록)**: 어형 자체가 붕괴된 비문("크다음 근"·"크다 가르키는" 같은 존재하지
  않는 활용형)은 이 결정론 게이트가 못 잡는다 — 형태소 분석·맞춤법 검사기 없이는 일반화된
  탐지가 불가능하다(과공학 방지). 이런 결함은 사람/AI 감사 표본 폴백으로 남는다.

발문 텍스트 결함(①~⑥)은 결정론 교정이 불가하므로(LLM 재생성 없이는 고칠 수 없다) **탈락(제거)이
정본**이다 — 적용 CLI는 `harness.rephrased_corpus_hygiene`, rephrase 수용 게이트 배선은
`rephrase.classify_invariance_failure`의 ⑤축(REASON_QUESTION_HYGIENE). ⑦(무변화·QUAL-03)은 같은
함수 안에서 별도 게이트 축(REASON_NO_CHANGE 재사용)으로 분리 매핑된다 — 상세는 그 함수 docstring.

7계층: L3 지역(동일 패키지 josa만 import·표준 라이브러리 외 의존 0·순수 함수).
"""

from __future__ import annotations

import re
import unicodedata

from whymath_backend.l3.equivalent.josa import TailReading, tail_reading

__all__ = [
    "REASON_DANGLING_EXPONENT_PHRASE",
    "REASON_FOREIGN_SCRIPT",
    "REASON_JOSA_ERROR",
    "REASON_META_LABEL_LEAK",
    "REASON_NONSTANDARD_TERM",
    "REASON_REQUEST_ANSWER_MISMATCH",
    "REASON_UNCHANGED_FROM_ORIGINAL",
    "question_hygiene_violations",
]

# 위반 사유 코드 — rephrase 실패 taxonomy(REASON_*)와 같은 어휘 체계(진단 온톨로지).
REASON_FOREIGN_SCRIPT = "FOREIGN_SCRIPT"
REASON_META_LABEL_LEAK = "META_LABEL_LEAK"
REASON_NONSTANDARD_TERM = "NONSTANDARD_TERM"
REASON_REQUEST_ANSWER_MISMATCH = "REQUEST_ANSWER_MISMATCH"
REASON_JOSA_ERROR = "JOSA_ERROR"
REASON_DANGLING_EXPONENT_PHRASE = "DANGLING_EXPONENT_PHRASE"
REASON_UNCHANGED_FROM_ORIGINAL = "UNCHANGED_FROM_ORIGINAL"

# ① 비한글 스크립트 — CJK 한자(기본·확장A·호환)·가나(히라가나·가타카나). 한글·라틴·수식 기호는
# 검사하지 않는다(허용 목록이 아니라 금지 범위 검사 — 오탐 0 지향).
_FOREIGN_SCRIPT_RE = re.compile(
    "["
    "一-鿿"  # CJK 통합 한자
    "㐀-䶿"  # CJK 확장 A
    "豈-﫿"  # CJK 호환 한자
    "぀-ゟ"  # 히라가나
    "゠-ヿ"  # 가타카나
    "]"
)

# ② 메타 라벨 — 재서술 과정 어휘의 발문 누출(감사 확정 실사례: '원 발문:'·'원판'·'재서술' +
# rotation-1 괄호 삽입구 4건). 애초 "괄호+한글+공백" 구조 규칙으로 일반화했으나
# misconception_eval_mc_generator의 정당한 설명("(일차항 계수)" 등)과 충돌해 폐쇄 목록으로
# 후퇴(2026-07-29 — 모듈 docstring "2026-07-29 재검토 실측" 참조). 향후 정상 용법 없이
# 반복되는 신규 패턴이 확인되면 여기 추가한다.
_META_LABELS: tuple[str, ...] = (
    "원 발문",
    "원판",
    "재서술",
    "(원래와 같은 표현으로)",
    "(대입과 계산을 통해)",
    "(더 작은)",
    "(주어진 방정식)",
)

# ③ 비표준 용어·오용어 — 감사 확정 폐쇄 목록 3아군.
# (a) 방정식 오명명: '원시방정식'·'다차방정식'으로 오명명, '원시적으로' 무의미 수식,
#     '원시 방정식' 띄어쓰기 변형 실측. '원시함수'(부정적분 정상 용어)는 다치지 않는 정확
#     문자열만 검사.
_NONSTANDARD_TERMS: tuple[str, ...] = ("원시방정식", "원시 방정식", "다차방정식", "원시적")

# (b) 차원/도형 오기술 — 1변수 방정식·수 계산 문항에 기하학적 차원·공간 개념을 허위 부여
# (rotation-1 실사례: "두 차원의 이차방정식"·"두 차원의 원에 해당하는"·"두차원 공간에서").
_DIMENSION_MISLABEL_RE = re.compile(r"두\s*차원|공간에서")

# (c) 개념 오치환 — '큰/작은 극'(이차방정식 근 문항에 미적분 극값 어휘 오적용 — '극값'·'극대'·
# '극소'는 부정 lookahead로 제외해 계산형 극값 문항은 다치지 않음). '중점'(중근의 오치환)은
# 애초 여기 있었으나 misconception_eval_mc_generator의 midpoint-sum-only 밴드가 좌표 중점을
# *정상 용법으로* 쓰는 것이 실측돼 제외(2026-07-29 — 폐쇄 목록도 아니고 패턴 자체를 뺐다).
_CONCEPT_SUBSTITUTION_RE = re.compile(r"(?:큰|작은)\s*극(?!값|대|소)")

# ④ 요구-정답 부정합 — 값을 묻는 스켈레톤 발문에 '방법'·'어떨까요'가 등장하면 요구가 값에서
# 절차/의견으로 이탈한 것(감사 확정: '구하는 방법'·'방법은 어떨까요' — 정답은 값이라 부정합).
_REQUEST_MISMATCH_RE = re.compile(r"방법|어떨까요")

# ⑤ 조사 검사 — 수·수식 토큰(라틴·숫자·수식 기호) 뒤의 조사만 본다. 한글 낱말 뒤 조사는
# 토큰 클래스가 배제한다(한국어 일반 문장 검사가 아니라 수식-조사 정합 검사 — 오탐 0 우선).
# 경계 규칙 둘: ① 토큰 시작은 문두·공백·한글 뒤여야 한다 — √·± 등 클래스 밖 기호에 이어지는
# 부분 토큰('√3/2'의 '3/2')을 잘라 읽으면 독법이 달라질 수 있어 침묵한다(부분 캡처 금지).
# ② lookahead로 조사 뒤가 공백·문장부호·끝일 때만 매치('이다'의 이, '는데'의 는 등 오인 차단).
_JOSA_TOKEN_RE = re.compile(
    r"(?:^|(?<=[\s가-힣]))([0-9A-Za-z½²³^*/().+\-|]+)\s*"
    r"(으로|로|과|와|을|를|은|는|이|가)(?=[\s.,!?)]|$)"
)

# ⑥ 지수 서술구 허상 삽입 — "숫자의 (제곱|세제곱|N제곱|거듭제곱근|제곱근)". 실사례 3/3 결함
# (감사 확정 — 도크스트링 ⑥ 참조). 부정 lookahead로 "…이므로"(참인 서술 연결)는 제외한다 —
# sqrt_sum 밴드의 "91의 제곱이므로 그 제곱근은 91"류 24건이 정상 용법으로 실측됐다
# (2026-07-29). 허상 실사례 3건은 전부 '이면'(가정)·'구하시오'(명령)로 이어져 이 제외에
# 걸리지 않는다(정상 용법 미관찰 폐쇄 목록이 아니라 이 한 지점만 정밀 제외).
_DANGLING_EXPONENT_RE = re.compile(r"\d+\s*의\s*(?:\d*제곱근|거듭제곱근|제곱|세제곱)(?!이므로)")

# ⑦ 무변화(원본과 동일) — QUAL-03(2026-08-10). `original_text`(선택 인자·기본 None)가 주어지고
# `question_text`가 그것과 **정규화 후** 완전 일치하면 "다양화가 실질적으로 일어나지 않았다"는
# 신호다. 기본 None이면 이 축은 계산조차 되지 않는다(additive 확장 — 기존 호출부 회귀 0).
#
# 배선 지점은 `rephrase.classify_invariance_failure`뿐이다(그 함수가 rephrase 직후 `raw` 출력을
# 검사할 때 `original_text=`원 발문을 넘긴다 — 그 함수 docstring 참고). `harness.
# rephrased_corpus_hygiene`(커밋 코퍼스 일괄 스캔)는 **의도적으로 넘기지 않는다** — 그 도구는
# 라인 단위 순회라 원본을 조인하려면 코퍼스 전체를 미리 인덱싱해야 하고(구조 부적합), 무엇보다
# write=True가 기본값이라 이 축을 켠 채로 잘못 돌리면 기존 무변화 레코드 전부가 조용히
# 삭제된다(그 모듈 docstring 참고 — 소급 삭제는 이 함수가 아니라 사람/오케스트레이터의 판단
# 몫이다).
#
# 정규화 기준은 `harness.problem_duplication_audit.normalize_question_text`(NFC + 공백 연속
# 축약 + 양끝 trim)와 **동등**해야 한다(QUAL-01 간접 측정·QUAL-03 직접 측정이 같은 정의를 써야
# 두 수치가 어긋나지 않는다 — CLAUDE.md 정직 회계). 다만 그 함수는 harness(조성/ops) 계층이라
# 여기서 import하면 "L3 지역·표준 라이브러리 외 의존 0"(모듈 docstring)이 깨진다 — 같은 로직을
# 로컬로 재구현한다(`_normalize_for_comparison`). 표류(drift) 방지는 `test_rephrase_hygiene.py`의
# 교차검증 테스트가 두 함수가 같은 표본 집합에서 항상 같은 출력을 내는지 고정한다.
_WHITESPACE_RUN = re.compile(r"\s+")


def _normalize_for_comparison(text: str) -> str:
    """비교용 정규화 — NFC + 공백 연속 축약 + 양끝 trim(순수 함수).

    `harness.problem_duplication_audit.normalize_question_text`와 동등 로직의 L3 지역
    재구현이다(위 ⑦ 주석 — import 방향 때문에 공유 불가). 그 함수와 달리 입력이 항상 `str`
    (Optional 아님)이라 None 분기가 없다 — 호출부(`question_hygiene_violations`)가 이미
    `original_text is not None`을 보장한 뒤에만 부른다.
    """
    return _WHITESPACE_RUN.sub(" ", unicodedata.normalize("NFC", text)).strip()


def _expected_josa(reading: TailReading, particle: str) -> str | None:
    """받침 사실(reading)에 맞는 올바른 조사 — particle이 속한 쌍 기준. 미지원 조사면 None."""
    batchim = reading.batchim
    if particle in ("을", "를"):
        return "을" if batchim else "를"
    if particle in ("과", "와"):
        return "과" if batchim else "와"
    if particle in ("은", "는"):
        return "은" if batchim else "는"
    if particle in ("이", "가"):
        return "이" if batchim else "가"
    if particle in ("으로", "로"):
        # ㄹ 받침 예외 — 받침 없음 또는 ㄹ 받침이면 '로', 그 외 받침이면 '으로'.
        return "로" if (not batchim or reading.rieul) else "으로"
    return None


def _josa_mismatches(text: str) -> list[str]:
    """수·수식 토큰 뒤 조사의 받침 부정합 목록 — 판별 가능(tail_reading≠None) 토큰만 판정."""
    found: list[str] = []
    for match in _JOSA_TOKEN_RE.finditer(text):
        token, particle = match.group(1), match.group(2)
        reading = tail_reading(token)
        if reading is None:
            continue  # 판별 불가 — 침묵(오탐 0 우선·정직 한계)
        expected = _expected_josa(reading, particle)
        if expected is not None and expected != particle:
            found.append(f"{token} {particle}→{expected}")
    return found


def question_hygiene_violations(
    question_text: str, *, original_text: str | None = None
) -> tuple[str, ...]:
    """발문 1건의 위생 위반 사유 코드 튜플 — 비면 통과(순수·결정론).

    사유 코드는 검사 순서대로 담기며 중복 없이 한 축당 최대 1개다. 상세(어느 토큰/용어인지)는
    사유 코드 뒤에 `:` 구분으로 병기해 사람이 탈락 근거를 재검증할 수 있게 한다(정직 산출).

    `original_text`(선택 인자·기본 None) — rephrase 이전 원 발문을 넘기면 ⑦ 무변화 축이 추가로
    활성화된다(QUAL-03, 위 ⑦ 주석 참고). 넘기지 않으면(기존 호출부 전부) 이 축은 계산되지 않아
    회귀가 없다(additive 확장).
    """
    violations: list[str] = []
    foreign = _FOREIGN_SCRIPT_RE.findall(question_text)
    if foreign:
        violations.append(f"{REASON_FOREIGN_SCRIPT}:{''.join(sorted(set(foreign)))}")
    leaked = [label for label in _META_LABELS if label in question_text]
    if leaked:
        violations.append(f"{REASON_META_LABEL_LEAK}:{'·'.join(leaked)}")
    terms = [term for term in _NONSTANDARD_TERMS if term in question_text]
    terms += _DIMENSION_MISLABEL_RE.findall(question_text)
    terms += _CONCEPT_SUBSTITUTION_RE.findall(question_text)
    if terms:
        violations.append(f"{REASON_NONSTANDARD_TERM}:{'·'.join(terms)}")
    mismatch = _REQUEST_MISMATCH_RE.search(question_text)
    if mismatch is not None:
        violations.append(f"{REASON_REQUEST_ANSWER_MISMATCH}:{mismatch.group(0)}")
    josa_errors = _josa_mismatches(question_text)
    if josa_errors:
        violations.append(f"{REASON_JOSA_ERROR}:{'·'.join(josa_errors)}")
    dangling = _DANGLING_EXPONENT_RE.findall(question_text)
    if dangling:
        violations.append(f"{REASON_DANGLING_EXPONENT_PHRASE}:{'·'.join(dangling)}")
    if original_text is not None:
        normalized_current = _normalize_for_comparison(question_text)
        normalized_original = _normalize_for_comparison(original_text)
        if normalized_current and normalized_original and normalized_current == normalized_original:
            violations.append(f"{REASON_UNCHANGED_FROM_ORIGINAL}:{len(normalized_current)}자")
    return tuple(violations)
