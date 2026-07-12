r"""오개념 카탈로그 — `docs/prompts/misconception_diagnosis.md` "오개념 카탈로그" 정본.

**스코프 정직**(False-attribute 금기, CLAUDE.md): doc에 *명시되고 상세화된* 항목만 코딩(32종).
슬: doc에 수능 핵심 4영역(미적분·수열·삼각함수·벡터, doc #16-23)을 *먼저 정본화*한 뒤
코드로 인코딩(doc-first). 슬: §5.4 교차검증 후보 8종을 doc에 상세화(stub #15
continuity-implies-differentiability 포함·#24-30 신규)한 뒤 인코딩 — Phase 1 30종 목표 달성.
S2-p: 이차방정식 근 선택·인수 부호 반전 2종(doc #31-32)을 doc-first로 추가(32종) — 동등문제
객관식 distractor의 오개념 역추적 좌석. 여전히 *미상세 항목을 추정 작성하지 않는다*(doc-first 불변).
843 확장 트랜치1(2026-07-12): 기초 계산형 6종(doc #35-40·분수덧셈·음수곱·음수빼기·절댓값·제곱근분배
·합차공식 혼동)을 doc-first로 추가(34→40종) — 843 콘텐츠↔탐지 커버 확장·수치평가 MC로 기계 검증.
843 확장 트랜치2(2026-07-12): 거듭제곱·분배·부호 계산형 6종(doc #41-46·거듭제곱 곱셈/거듭제곱·음수
제곱 우선순위·분배 뒷항 누락·음수 분배 부호·차의 제곱 교차항)을 doc-first로 추가(40→46종).
843 확장 트랜치3(2026-07-12): 중점·비례·부호·동류항·완전제곱·켤레 계산형 6종(doc #47-52)을
doc-first로 추가(46→52종).
843 확장 트랜치4(2026-07-12): 이항·GCD/LCM·소수·대분수·나머지정리·근과계수 계산형 6종(doc
#53-58)을 doc-first로 추가(52→58종).
843 확장 트랜치5(2026-07-12): 비대수 도메인 첫 확장 — 기하 4종(사다리꼴 넓이 ½ 누락·부피비=닮음비·
원뿔 부피 ⅓ 누락·원 넓이↔둘레 혼동)·확률통계 2종(조합 분모 누락·같은 것 순열 중복 나눗셈 누락)을
doc-first(doc #59-64)로 추가(58→64종) — π 계수·개수 값형 수치평가 MC로 기계 검증.

각 `canonical_statement`·`counterexample`은 *자체 생성 기본 수학 사실*(교과서/EBS 본문 복제
금지·CLAUDE.md). 반례는 canonical을 실제로 반증한다(수학적 정합 검증 완료).

각 항목의 `signals`(공출현 substring)는 *전형적인 학생 표기*에서 발견되는 토큰. v1은 규칙 기반
— 임베딩·LLM-judged 매칭은 후속(범위 밖). 토큰은 한국어/ASCII/유니코드(²) 형태를 포괄하기
위해 *공통 분모*(여러 표기 모두에 등장하는 단편)를 선택.

v1.2(슬 102): 일부 항목에 `regex_signals`를 추가해 *거짓 항등식의 수치 대입*을 탐지한다(예:
distribution `(3+4)²=3²+4²`·square-root `√((-3)²)=-3`·fraction `(2+4)/2=4`). 정규식은 *정규화된
텍스트*(`_normalize`: NFKC+공백제거, `²`→`2`)에 `re.search`로 검사하며, 명명그룹 역참조로 피연산자
일치를 강제해 ① 올바른 계산과 ② 기호식(`\d`가 문자 미매치) 모두에 *매치되지 않게*(disjoint)
작성한다 — 따라서 기존 substring `matched_signals`·confidence(1.0/0.5)는 불변이고 정규식은 *추가*
탐지가 된다(분모는 substring `signals` 기준, 정규식 가산분은 상한 1.0). 수치화가 명확한 3종에
시연하고 나머지 확장은 doc(misconception_diagnosis.md §매칭 알고리즘 v1.2) 후속.
"""

from __future__ import annotations

from whymath_backend.l4.misconception.models import Misconception

# 대수 영역 — doc "대수 영역"(#1-7, #24-25, #31-32, #35-58) (35종).
_ALGEBRA: tuple[Misconception, ...] = (
    Misconception(
        id="distribution-over-power",
        name_kr="제곱 분배 오류",
        domain="대수",
        canonical_statement="(a+b)² = a² + b²",
        counterexample="a=1, b=1",
        signals=("(a+b)", "a² + b²"),
        # v1.2 수치 대입 탐지(슬 102): 학생이 *구체 수치로* 거짓 항등식을 계산한 흔적
        # `(3+4)²=3²+4²`을 잡는다. NFKC로 `²`→`2`이므로 정규형 `(d+d)2=d2+d2`를 겨냥하고,
        # 명명그룹 역참조로 좌변 두 피연산자(x,y)가 우변 두 제곱항과 *글자 그대로 일치*할 때만
        # 매치 → 올바른 전개 `(3+4)²=49`나 기호식 `(a+b)²=a²+b²`(\d가 글자 미매치)엔 미스(disjoint).
        # 근거: 데이터셋 [H:12대수01-03] ◎ 정확대응(concept_graph_dataset_v1.md §5.2).
        regex_signals=(r"\((?P<x>\d+)\+(?P<y>\d+)\)2=(?P=x)2\+(?P=y)2",),
        # SymPy 머신 검증 거짓 항등식 — diff=(a+b)²−(a²+b²)=2ab(다항·a=b=1에서 거짓)이라
        # identity_status가 not_identity로 *증명*한다(동치 권위 일원화·무결성 테스트 강제).
        canonical_wrong_form=("(a+b)**2", "a**2 + b**2"),
        # 정정 형태(올바른 완전제곱) — `signals`의 좌변 `(a+b)`만 공유하고 *틀린 RHS* `a²+b²`는
        # 미포함(가운데 `2ab`로 분리)이라 자기 오개념 conf 0.5(게이트 0.65 미만). gate-safe.
        correct_form="(a+b)² = a² + 2ab + b²",
    ),
    Misconception(
        id="sign-flip-in-inequality",
        name_kr="부등식 부호 미반전",
        domain="대수",
        canonical_statement="음수를 곱해도 부등식 부호가 그대로",
        counterexample="-2 < 1에 -1을 곱하면 2 > -1 (부호 반전)",
        signals=("부등식", "음수", "곱"),
    ),
    Misconception(
        id="division-by-zero",
        name_kr="0 나눗셈 가능성 놓침",
        domain="대수",
        canonical_statement="분모에 변수가 와도 항상 정의됨",
        counterexample="분모 = 0이 되는 값에서 식이 무정의",
        signals=("분모", "0"),
    ),
    Misconception(
        id="square-root-positivity",
        name_kr="제곱근 양수 가정",
        domain="대수",
        canonical_statement="√(x²) = x",
        counterexample="x=-3이면 √(x²) = 3 = |x|, x가 아님",
        # 신호 정밀화: LHS식 `√(x²)` + *틀린 RHS* `= x`. 느슨한 `("√","x²")`는 정답 `√(x²)=|x|`까지
        # 1.0 풀매칭해 *정답에 거짓 COUNTEREXAMPLE 개입*을 발화했다(judge 기본 off·#109 동류).
        # 정답엔 `= x` 없음(=`|x|`)→LHS만 0.5(게이트 미만)·틀림 `√(x²)=x`만 1.0. gate-safe.
        signals=("√(x²)", "= x"),
        # v1.2 수치 대입 탐지(슬 102): 음수를 대입해 거짓 항등식을 드러낸 흔적
        # `√((-3)²)=-3`을 잡는다. 정규형 `√((-d)2)=-d`(NFKC `²`→`2`)에서 역참조로 피개수가
        # 좌·우변 동일할 때만 매치 → 올바른 `√((-3)²)=3`이나 기호 `√(x²)=x`엔 미스(disjoint).
        # 근거: 데이터셋 [J0107]·[H:12대수01-01] ◎ 정확대응(§5.2).
        regex_signals=(r"√\(\(-(?P<a>\d+)\)2\)=-(?P=a)",),
        # 정정 형태 — `√(x²)`만 공유·RHS `|x|`는 틀린 RHS `x`와 다름 → 자기 오개념 0.5. gate-safe.
        correct_form="√(x²) = |x|",
    ),
    Misconception(
        id="exponent-zero",
        name_kr="0 지수 0 가정",
        domain="대수",
        canonical_statement="a⁰ = 0",
        counterexample="2⁰ = 1 (a≠0인 모든 a에 대해 a⁰ = 1)",
        signals=("a⁰", "0"),
        # SymPy 머신 검증 — `a**0`은 1로 환원되어 `1 ≠ 0`(상수 차)이라 not_identity로 증명된다.
        canonical_wrong_form=("a**0", "0"),
        # 정정 형태 — `a⁰`만 공유(좌변)하고 RHS `1`은 틀린 RHS `0`과 다름. 정규형 `a0=1`에서
        # signal `0`은 영숫자 경계(앞 `a`)로 미매치 → 자기 오개념 conf 0.5(게이트 미만). gate-safe.
        correct_form="a⁰ = 1",
    ),
    Misconception(
        id="fraction-cancellation",
        name_kr="분자 합 약분 오류",
        domain="대수",
        canonical_statement="(a+b)/a = b",
        counterexample="a=2, b=4: (2+4)/2 = 3 ≠ 4",
        # 신호 정밀화: LHS식 `(a+b)/a` + *틀린 RHS* `= b`. 느슨한 `b`는 정답 `(a+b)/a = 1 + b/a`까지
        # 1.0 풀매칭해 *정답에 거짓 COUNTEREXAMPLE 개입*을 발화했다. 정답엔 `= b` 없음(=`1+`)→
        # LHS만 0.5(게이트 미만)·틀림 `(a+b)/a=b`만 1.0. gate-safe.
        signals=("(a+b)/a", "= b"),
        # v1.2 수치 대입 탐지(슬 102): 분자 합에서 분모와 같은 항을 *통째로 약분*해버린
        # 수치 흔적 `(2+4)/2=4`를 잡는다. 정규형 `(p+q)/p=q`에서 분모가 첫 피연산자(p)와 같고
        # 결과가 둘째 피연산자(q)일 때만 매치 → 올바른 `(2+4)/2=3`이나 기호 `(a+b)/a=b`엔
        # 미스(disjoint). 데이터셋 직접진술 미수록(§5.2 '미대응')이나 canonical로 자명한 기본수학.
        regex_signals=(r"\((?P<p>\d+)\+(?P<q>\d+)\)/(?P=p)=(?P=q)",),
        # 정정 형태 — `(a+b)/a`만 공유·RHS `1 + b/a`는 틀린 RHS `b`와 다름 → 0.5. gate-safe.
        correct_form="(a+b)/a = 1 + b/a",
    ),
    Misconception(
        id="log-distribution",
        name_kr="로그 합 분배",
        domain="대수",
        canonical_statement="log(a+b) = log a + log b",
        counterexample="a=b=1: log 2 ≠ log 1 + log 1 = 0",
        signals=("log(a+b)", "log a + log b"),
        # v1.2 수치 대입 탐지(슬 102 후속·보수적 확장): 로그를 *합에 분배*해 구체 수치로
        # 거짓 항등식을 계산한 흔적 `log(2+3)=log2+log3`을 잡는다. canonical `log(a+b)=log a+log b`
        # 의 정규형(_normalize: NFKC+공백제거)은 `log(a+b)=loga+logb`이므로 정규식은 그 평문
        # 골격에 좌변 두 진수(a,b)를 `\d+`로, 우변 두 로그 항을 *명명그룹 역참조*로 강제한다.
        # disjoint 근거(정상/기호식 매치 0·교차검증 완료):
        #   ① 올바른 곱 법칙 `log(2·3)=log2+log3`은 괄호 안이 `2·3`(곱)이라 `\d+\+\d+`(합)에
        #      미매치 — 로그의 *진짜 분배 대상*은 곱이므로 합(`+`) 강제가 정상 풀이를 가른다.
        #   ② 올바른 값 `log(2+3)=log5`는 우변이 `log5` 단항이라 `log(?P=a)+log(?P=b)`에 미매치.
        #   ③ 기호식 `log(a+b)=log a+log b`는 `\d+`가 문자 `a`·`b`에 미매치(substring 경로가 담당).
        #   ④ 역참조라 진수 불일치(`log(2+3)=log2+log4`)·순서 교환(`=log3+log2`)도 미매치.
        # 근거: canonical_statement에서 정규형 직접 도출(추측 0). 표기 변이 큰 삼각(sin 합 분배·
        # 도/라디안)·기호식만(곱미분)·서술형/개념 오류는 regex 부적합 → semantic/LLM-judge 후속.
        regex_signals=(r"log\((?P<a>\d+)\+(?P<b>\d+)\)=log(?P=a)\+log(?P=b)",),
        # 정정 형태(로그 *곱* 법칙) — 진짜 분배 대상은 곱(`ab`)이다. RHS `log a + log b`만 공유·
        # 좌변 `log(a+b)`(틀린 대상=합)는 미포함(`log(ab)`) → 자기 오개념 conf 0.5(게이트 미만).
        correct_form="log(ab) = log a + log b",
    ),
    Misconception(
        id="discriminant-negative-no-real-root",
        name_kr="판별식 음수 해 부재 단정",
        domain="대수",
        # 학생이 "해가 없다"로 *불능* 단정. 올바른 명제는 "실근이 없다"(복소근 2개 존재).
        canonical_statement="판별식 D<0이면 해가 없다",
        counterexample="x²+1=0은 실근은 없으나 x=±i (복소근 2개)",
        # 신호 정밀화: 단독 "판별식"은 정답에도 흔하므로 *틀린 결론* "해가 없"과 공출현 요구.
        # 올바른 풀이는 "실근이 없"이라 적어 "해가 없"과 구분된다(positive 오류 단편).
        signals=("판별식", "해가 없"),
    ),
    Misconception(
        id="root-loss-by-dividing",
        name_kr="양변 나눗셈 근 손실",
        domain="대수",
        canonical_statement="ax²=bx의 양변을 x로 나누면 x=b/a (x=0 근 손실)",
        counterexample="x²=2x를 x로 나누면 x=2만 — 실제 x(x-2)=0이라 x=0도 근",
        # "양변"+"x로 나누"(변수로 나눔)의 공출현이 근 손실의 양성 단편. 상수로 나누는
        # 올바른 조작("양변을 2로 나누")은 "x로 나누"를 포함하지 않아 구분된다.
        signals=("양변", "x로 나누"),
    ),
    Misconception(
        id="opposite-root-selected",
        name_kr="반대 근 선택",
        domain="대수",
        canonical_statement="두 근 중 어느 근을 답해도 상관없다",
        counterexample="x²-5x+6=0의 두 근 2, 3 중 '큰 근'은 3 — 2를 답하면 요구와 불일치",
        # "어느 근"+"상관없" 공출현 — 발문의 근 선택 지시(큰/작은)를 무시해도 된다는 양성 단편.
        # 올바른 풀이는 "요구한/큰/작은 근을 골라"로 적어 두 토큰이 공출현하지 않는다(gate-safe).
        # S2-p(doc #31): 동등문제 객관식 distractor(반대 근 선지)의 역추적 좌석 —
        # [10공수1-02-02]·HK06(이차방정식의 근).
        signals=("어느 근", "상관없"),
    ),
    Misconception(
        id="factor-sign-flip",
        name_kr="인수 근 부호 반전",
        domain="대수",
        canonical_statement="(x-a)=0이면 x=-a이다",
        counterexample="(x-2)=0의 근은 x=2 — x=-2를 대입하면 -2-2=-4≠0",
        # 기호 일반형 LHS "(x-a)"+틀린 결론 "x=-a"의 공출현(정규화 후). 수치 사례
        # ("(x-2)=0 → x=-2")는 기호 토큰이라 미발화 — disjoint 역참조 수치 정규식은 v1.2
        # 시연 방식대로 후속(doc §매칭 알고리즘·추측 작성 금지). 올바른 진술 "x=a"는
        # "x=-a"를 미포함(gate-safe). S2-p(doc #32) distractor(부호 반전 근 선지) 역추적 좌석.
        signals=("(x-a)", "x=-a"),
    ),
    # ── 843 확장 트랜치1(doc #35-40·기초 계산형 6종·수치평가 MC로 기계 검증) ──
    Misconception(
        id="fraction-addition-naive",
        name_kr="분수 덧셈 통분 누락",
        domain="대수",
        canonical_statement="a/b + c/d = (a+c)/(b+d)",
        counterexample="1/2 + 1/3 = 5/6 — (1+1)/(2+3)=2/5는 통분을 누락한 값",
        # 통분 없이 분자·분모를 각각 더한 흔적. "분수"+"통분" 공출현(doc #35). 수치평가 MC
        # distractor(2/5 선지)의 역추적 좌석. ([9수01-04]·M0004)
        signals=("분수", "통분"),
    ),
    Misconception(
        id="negative-times-negative",
        name_kr="음수 곱 부호",
        domain="대수",
        canonical_statement="음수끼리 곱하면 음수다",
        counterexample="(-2)×(-3)=6>0 — 음×음=양",
        # 부호 규칙(음×음=양) 누락. "음수끼리"+"곱하면" 공출현(doc #36). 수치평가 MC
        # distractor(-ab 선지)의 역추적 좌석. ([9수01-03]·M0001)
        signals=("음수끼리", "곱하면"),
    ),
    Misconception(
        id="subtract-negative-sign",
        name_kr="음수 빼기 부호",
        domain="대수",
        canonical_statement="a-(-b)=a-b",
        counterexample="3-(-5)=8 — 3-5=-2는 부호 반전을 누락한 값",
        # 음수를 빼는 연산에서 부호 반전(−(−b)=+b) 누락. "음수"+"빼기" 공출현(doc #37).
        # 수치평가 MC distractor(a-b 선지)의 역추적 좌석. ([9수01-03]·M0002)
        signals=("음수", "빼기"),
    ),
    Misconception(
        id="absolute-value-keeps-sign",
        name_kr="절댓값 부호 유지",
        domain="대수",
        canonical_statement="|-a|=-a",
        counterexample="|-3|=3 — 절댓값(거리)은 음이 아니다",
        # 절댓값이 음수의 부호를 유지한다는 오개념. "절댓값"+"음수" 공출현(doc #38).
        # 수치평가 MC distractor(-a 선지)의 역추적 좌석. ([9수01-04]·M0010)
        signals=("절댓값", "음수"),
    ),
    Misconception(
        id="sqrt-distributes-over-sum",
        name_kr="제곱근 합 분배",
        domain="대수",
        canonical_statement="√(a+b)=√a+√b",
        counterexample="√(9+16)=√25=5 — √9+√16=7은 분배 오개념 값",
        # 제곱근이 합에 분배된다는 오개념. "제곱근"+"분배" 공출현(doc #39). 수치평가 MC
        # distractor(√a+√b 선지)의 역추적 좌석. ([9수01-07]·M0008)
        signals=("제곱근", "분배"),
    ),
    Misconception(
        id="difference-of-squares-confused",
        name_kr="제곱 차 혼동",
        domain="대수",
        canonical_statement="x²-a² = (x-a)²",
        counterexample="x=5,a=3에서 x²-9=16 — (x-3)²=4 (올바른 인수분해는 (x-a)(x+a))",
        # 제곱의 차를 차의 제곱으로 보는 합차공식 혼동. "제곱"+"차이" 공출현(doc #40).
        # 수치평가 MC distractor((x-a)² 선지)의 역추적 좌석. ([9수01-01]·M0121)
        signals=("제곱", "차이"),
    ),
    # ── 843 확장 트랜치2(doc #41-46·거듭제곱·분배·부호 계산형 6종·수치평가 MC로 기계 검증) ──
    Misconception(
        id="exponent-product-multiplies",
        name_kr="거듭제곱 곱셈 지수",
        domain="대수",
        canonical_statement="aᵐ × aⁿ = aᵐⁿ",
        counterexample="2³×2²=2⁵=32 — 2⁶=64는 지수를 곱한 값",
        # 밑이 같은 거듭제곱의 곱에서 지수를 더하지 않고 곱함. "지수끼리"+"곱하" 공출현(doc #41).
        # 수치평가 MC distractor(2⁶ 선지)의 역추적 좌석. ([9수02-08]·M0006)
        signals=("지수끼리", "곱하"),
    ),
    Misconception(
        id="power-of-power-adds",
        name_kr="거듭제곱의 거듭제곱 지수",
        domain="대수",
        canonical_statement="(aᵐ)ⁿ = aᵐ⁺ⁿ",
        counterexample="(2³)²=2⁶=64 — 2⁵=32는 지수를 더한 값",
        # 거듭제곱의 거듭제곱에서 지수를 곱하지 않고 더함. "거듭제곱의"+"지수를" 공출현(doc #42).
        # 수치평가 MC distractor(2⁵ 선지)의 역추적 좌석. ([9수02-08]·M0135)
        signals=("거듭제곱의", "지수를"),
    ),
    Misconception(
        id="negative-square-precedence",
        name_kr="음수 제곱 우선순위",
        domain="대수",
        canonical_statement="-a² = a²",
        counterexample="-2²=-(2²)=-4 — 4는 (-2)²으로 부호를 먼저 처리한 값",
        # 거듭제곱이 음의 부호보다 우선함을 놓쳐 -a²을 (-a)²로 계산. "음수"+"거듭제곱"(doc #43).
        # 수치평가 MC distractor(4 선지)의 역추적 좌석. ([9수02-08]·M0009)
        signals=("음수", "거듭제곱"),
    ),
    Misconception(
        id="distribute-first-term-only",
        name_kr="분배 뒷항 누락",
        domain="대수",
        canonical_statement="a(x+b) = ax + b",
        counterexample="2(x+3)=2x+6 — 2x+3은 뒷항 분배를 누락한 값",
        # 분배법칙에서 뒷항 분배를 누락. "분배"+"뒷항" 공출현(doc #44).
        # 수치평가 MC distractor(뒷항 미분배 선지)의 역추적 좌석. ([9수02-09]·M0017)
        signals=("분배", "뒷항"),
    ),
    Misconception(
        id="negative-distribute-sign",
        name_kr="음수 분배 부호",
        domain="대수",
        canonical_statement="-(x-b) = -x - b",
        counterexample="-(x-3)=-x+3 — -x-3은 뒷항 부호를 안 바꾼 값",
        # 음의 부호 분배에서 뒷항 부호 반전을 누락. "음수"+"분배" 공출현(doc #45).
        # 수치평가 MC distractor(-x-b 선지)의 역추적 좌석. ([9수02-09]·M0018)
        signals=("음수", "분배"),
    ),
    Misconception(
        id="square-of-difference-no-cross",
        name_kr="차의 제곱 교차항 누락",
        domain="대수",
        canonical_statement="(a-b)² = a² - b²",
        counterexample="(5-3)²=4 — 25-9=16은 교차항 -2ab를 누락한 값",
        # 차의 제곱에서 교차항 -2ab 누락. "차의 제곱"+"교차항" 공출현(doc #46).
        # 수치평가 MC distractor(a²-b² 선지)의 역추적 좌석. ([9수02-19]·M0020)
        signals=("차의 제곱", "교차항"),
    ),
    # ── 843 확장 트랜치3(doc #47-52·중점·비례·부호·동류항·완전제곱·켤레 계산형 6종) ──
    Misconception(
        id="midpoint-sum-only",
        name_kr="중점 2로 안 나눔",
        domain="대수",
        canonical_statement="두 점 a, b의 중점 = a + b",
        counterexample="a=2, b=6의 중점은 (2+6)/2=4 — 8은 2로 나누기를 누락한 값",
        # 중점 좌표에서 2로 나누기 누락. "중점"+"더해" 공출현(doc #47).
        # 수치평가 MC distractor(a+b 선지)의 역추적 좌석. ([9수02-05]·M0066)
        signals=("중점", "더해"),
    ),
    Misconception(
        id="scale-area-linear",
        name_kr="닮음 넓이 선형 오인",
        domain="대수",
        canonical_statement="닮음비 k이면 넓이의 비도 k",
        counterexample="닮음비 2이면 넓이의 비는 2²=4 — 2는 선형으로 오인한 값",
        # 넓이는 길이의 제곱에 비례함을 놓침. "닮음비"+"넓이" 공출현(doc #48).
        # 수치평가 MC distractor(k 선지)의 역추적 좌석. ([9수02-07]·M0013)
        signals=("닮음비", "넓이"),
    ),
    Misconception(
        id="negative-even-power-sign",
        name_kr="음수 짝수 거듭제곱 부호",
        domain="대수",
        canonical_statement="(-a)^짝수 = 음수",
        counterexample="(-2)⁴=16>0 — -16은 짝수 거듭제곱을 음수로 본 값",
        # 음수의 짝수 거듭제곱이 양수임을 놓침. "짝수"+"거듭제곱" 공출현(doc #49).
        # 수치평가 MC distractor(-a^n 선지)의 역추적 좌석. ([9수02-08]·M0201)
        signals=("짝수", "거듭제곱"),
    ),
    Misconception(
        id="combine-unlike-terms",
        name_kr="동류항 차수 무시",
        domain="대수",
        canonical_statement="ax + bx² = (a+b)x³",
        counterexample="2x+3x²은 차수가 달라 결합 불가 — x=2에서 16 ≠ 5·8=40",
        # 차수가 다른 항을 동류항처럼 결합. "차수"+"동류항" 공출현(doc #50).
        # 수치평가 MC distractor((a+b)x³ 값 선지)의 역추적 좌석. ([9수02-09]·M0016)
        signals=("차수", "동류항"),
    ),
    Misconception(
        id="complete-square-naive",
        name_kr="완전제곱식 오인",
        domain="대수",
        canonical_statement="x² + bx = (x+b)²",
        counterexample="x²+6x ≠ (x+6)² — x=2에서 16 ≠ 64 (올바른 완전제곱은 (x+3)²-9)",
        # 완전제곱식에서 일차항 계수를 반으로 나누지 않음. "완전제곱"+"괄호" 공출현(doc #51).
        # 수치평가 MC distractor((x+b)² 값 선지)의 역추적 좌석. ([9수02-19]·M0119)
        signals=("완전제곱", "괄호"),
    ),
    Misconception(
        id="conjugate-product-sum",
        name_kr="켤레 무리수 곱 부호",
        domain="대수",
        canonical_statement="(√a+1)(√a-1) = a + 1",
        counterexample="(√3+1)(√3-1)=3-1=2 — 4는 합차공식 부호를 오용한 값",
        # 켤레 무리수의 곱에서 합차공식 부호 오용. "켤레"+"무리수" 공출현(doc #52).
        # 수치평가 MC distractor(a+1 선지)의 역추적 좌석. ([9수01-07]·M0206)
        signals=("켤레", "무리수"),
    ),
    # ── 843 확장 트랜치4(doc #53-58·이항·GCD/LCM·소수·대분수·나머지정리·근과계수 계산형 6종) ──
    Misconception(
        id="transpose-no-sign-change",
        name_kr="이항 부호 미변경",
        domain="대수",
        canonical_statement="x + b = c 이면 x = c + b",
        counterexample="x+3=7이면 x=7-3=4 — 10은 이항 시 부호를 안 바꾼 값",
        # 이항할 때 부호 반전 누락. "이항"+"부호" 공출현(doc #53).
        # 수치평가 MC distractor(c+b 선지)의 역추적 좌석. ([9수02-13]·M0021)
        signals=("이항", "부호"),
    ),
    Misconception(
        id="gcd-lcm-confused",
        name_kr="최대공약수 최소공배수 혼동",
        domain="대수",
        canonical_statement="두 수의 최대공약수 = 최소공배수",
        counterexample="12와 18: 최대공약수 6, 최소공배수 36으로 다름",
        # 최대공약수와 최소공배수를 혼동. "최대공약수"+"최소공배수" 공출현(doc #54).
        # 수치평가 MC distractor(반대 값 선지)의 역추적 좌석. ([9수01-02]·M0014)
        signals=("최대공약수", "최소공배수"),
    ),
    Misconception(
        id="decimal-mult-place",
        name_kr="소수 곱 자릿수 무시",
        domain="대수",
        canonical_statement="0.a × 0.b = 0.(ab)",
        counterexample="0.3×0.2=0.06 — 0.6은 소수점 자릿수를 무시한 값",
        # 소수의 곱에서 소수점 자릿수 무시. "소수"+"자릿수" 공출현(doc #55).
        # 수치평가 MC distractor(0.(ab) 선지)의 역추적 좌석. ([9수01-06]·M0103)
        signals=("소수", "자릿수"),
    ),
    Misconception(
        id="mixed-number-mult-whole",
        name_kr="대분수 곱 정수만",
        domain="대수",
        canonical_statement="(a + p/q) × n = an + p/q",
        counterexample="1½×2=3 — 2½은 정수부만 곱한 값(분수부도 곱해야 함)",
        # 대분수의 곱에서 정수부만 곱함. "대분수"+"정수" 공출현(doc #56).
        # 수치평가 MC distractor(an+p/q 선지)의 역추적 좌석. ([9수01-04]·M0102)
        signals=("대분수", "정수"),
    ),
    Misconception(
        id="remainder-theorem-sign",
        name_kr="나머지정리 부호",
        domain="대수",
        canonical_statement="f(x)를 (x-a)로 나눈 나머지 = f(-a)",
        counterexample="f(x)=x²+2x+1을 (x-1)로 나눈 나머지는 f(1)=4 — f(-1)=0이 아님",
        # 나머지정리에서 부호를 반대로 대입. "나머지정리"+"대입" 공출현(doc #57).
        # 수치평가 MC distractor(f(-a) 선지)의 역추적 좌석. ([10공수1-01-01]·M0133)
        signals=("나머지정리", "대입"),
    ),
    Misconception(
        id="vieta-sign-error",
        name_kr="근과 계수 부호",
        domain="대수",
        canonical_statement="x²+bx+c=0 의 두 근의 합 = b",
        counterexample="x²+5x+6=0의 두 근 -2, -3의 합은 -5 — b=5가 아님",
        # 근과 계수 관계에서 부호를 놓침(합은 -b). "근과 계수"+"부호" 공출현(doc #58).
        # 수치평가 MC distractor(b 선지)의 역추적 좌석. ([10공수1-02-08]·M0123)
        signals=("근과 계수", "부호"),
    ),
)

# 기하 영역 — doc "기하 영역"(#8-10, #26, #59-62) (8종·843 트랜치5 비대수 확장 4).
_GEOMETRY: tuple[Misconception, ...] = (
    Misconception(
        id="angle-sum-non-triangle",
        name_kr="비삼각형 각 합 혼동",
        domain="기하",
        canonical_statement="모든 다각형의 내각의 합은 180°",
        counterexample="사각형의 내각의 합은 360° (n각형은 (n-2)×180°)",
        signals=("내각", "180"),
    ),
    Misconception(
        id="similarity-vs-congruence",
        name_kr="닮음·합동 혼동",
        domain="기하",
        canonical_statement="닮은 두 도형은 합동이다",
        counterexample="배율 2인 닮음 삼각형은 합동 아님",
        signals=("닮음", "합동"),
    ),
    Misconception(
        id="area-perimeter-confusion",
        name_kr="둘레 늘면 넓이 늘 가정",
        domain="기하",
        canonical_statement="둘레가 크면 넓이도 크다",
        counterexample="가늘고 긴 직사각형은 둘레 大, 넓이 小 가능",
        signals=("둘레", "넓이"),
    ),
    Misconception(
        id="circle-radius-squared",
        name_kr="원 반지름 제곱 혼동",
        domain="기하",
        canonical_statement="x²+y²=r²의 반지름은 r²",
        counterexample="x²+y²=9는 반지름 3 (=√9), 9가 아님",
        # "반지름"+"r²"(NFKC로 'r2') 공출현 — 반지름을 r²로 표기한 양성 단편. 한계(§5.3):
        # 일반형 정답("x²+y²=r², r²=9, 반지름 3")도 두 토큰 공출현→오탐 가능
        # (substring은 반지름·r²의 *등치*를 못 가림). 두 토큰 AND라 무관 풀이엔 미발화.
        # 정본 해법(등치 판별)은 임베딩/LLM-judged 후속 — 개입은 비난 없는 소크라테스형.
        signals=("반지름", "r²"),
    ),
    # ── 843 트랜치5(비대수 도메인 확장) 기하 4종 ──
    Misconception(
        id="trapezoid-area-no-half",
        name_kr="사다리꼴 넓이 ½ 누락",
        domain="기하",
        canonical_statement="사다리꼴의 넓이는 (윗변+아랫변)에 높이를 곱한 값이다",
        counterexample="윗변2·아랫변4·높이3이면 넓이는 (2+4)×3÷2 = 9 (÷2 필요), 18 아님",
        # "사다리꼴"+"높이를 곱" 공출현 — ÷2 누락 양성 단편(M0161). 정본("높이를 곱한 뒤 2로
        # 나눈다")도 두 토큰 공출현 가능(FP 한계·§5.3) — substring은 후행 ÷2를 못 가림. 임베딩 후속.
        signals=("사다리꼴", "높이를 곱"),
    ),
    Misconception(
        id="scale-volume-linear",
        name_kr="부피비=닮음비 오인",
        domain="기하",
        canonical_statement="닮음비가 k이면 부피비도 k이다",
        counterexample="닮음비가 2이면 부피비는 2³ = 8 (닮음비의 세제곱), 2 아님",
        # "닮음비"+"부피비" 공출현 — 둘을 동일시한 양성 단편(M0056·차원혼동). 정본("부피비는
        # 닮음비의 세제곱")도 두 토큰 공출현 가능(FP 한계·§5.3) — 등치 판별은 임베딩/LLM 후속.
        signals=("닮음비", "부피비"),
    ),
    Misconception(
        id="cone-volume-no-third",
        name_kr="원뿔 부피 ⅓ 누락",
        domain="기하",
        canonical_statement="원뿔의 부피는 밑넓이×높이이다(원기둥과 같다)",
        counterexample="원뿔의 부피는 ⅓×밑넓이×높이 (원기둥의 1/3), 원기둥과 같지 않음",
        # "원뿔"+"원기둥" 공출현 — 둘을 동일시한 양성 단편(M0063). 정본("원뿔은 원기둥의 ⅓")도
        # 두 토큰 공출현 가능(FP 한계·§5.3) — ⅓ 관계 판별은 임베딩/LLM 후속.
        signals=("원뿔", "원기둥"),
    ),
    Misconception(
        id="circle-area-circumference",
        name_kr="원 넓이·둘레 공식 혼동",
        domain="기하",
        canonical_statement="원의 넓이는 2πr이다",
        counterexample="원의 넓이는 πr² (2πr은 둘레 공식)",
        # "원의 넓이"+"2πr" 공출현 — 넓이를 둘레 공식으로 오인한 양성 단편(M0053). 넓이·둘레를
        # 함께 서술한 정본도 두 토큰 공출현 가능(FP 한계·§5.3) — 임베딩/LLM 후속.
        signals=("원의 넓이", "2πr"),
    ),
)

# 확률·통계 — doc "확률·통계"(#11-13, #27, #63-64) (6종·843 트랜치5 비대수 확장 2).
_PROBSTAT: tuple[Misconception, ...] = (
    Misconception(
        id="gambler-fallacy",
        name_kr="도박사의 오류",
        domain="확률통계",
        canonical_statement="앞면 5번 연속이면 다음은 뒷면이 더 잘 나온다",
        counterexample="독립시행은 과거 결과와 무관 (P=1/2 유지)",
        signals=("동전", "다음"),
    ),
    Misconception(
        id="prosecutor-fallacy",
        name_kr="검사의 오류",
        domain="확률통계",
        canonical_statement="P(A|B) = P(B|A)",
        counterexample="P(증거|무죄) ≠ P(무죄|증거) (베이즈 정리)",
        signals=("P(A|B)", "P(B|A)"),
    ),
    Misconception(
        id="mean-vs-median",
        name_kr="평균·중앙값 혼동",
        domain="확률통계",
        canonical_statement="평균과 중앙값은 항상 같다",
        counterexample="치우친 분포(소득)에서 평균 ≠ 중앙값",
        signals=("평균", "중앙값"),
    ),
    Misconception(
        id="mutually-exclusive-implies-independent",
        name_kr="배반·독립 혼동",
        domain="확률통계",
        canonical_statement="배반사건이면 독립이다",
        counterexample="주사위 A={1}, B={2}: P(A∩B)=0 ≠ P(A)P(B)=1/36 (배반은 오히려 종속)",
        # "배반"+"독립" 공출현 — 둘을 동일시한 양성 단편. 올바른 진술("배반이면 종속")은
        # "독립"을 포함하지 않아 구분된다.
        signals=("배반", "독립"),
    ),
    # ── 843 트랜치5(비대수 도메인 확장) 확률·통계 2종 ──
    Misconception(
        id="combination-no-denominator",
        name_kr="조합 분모 누락(순열화)",
        domain="확률통계",
        canonical_statement="조합의 수 nCr을 순열의 수 nPr로 계산한다(분모 r! 누락)",
        counterexample="5C2 = 10인데 5P2 = 20으로 답하면 분모 2!을 빠뜨린 것",
        # "조합"+"nPr" 공출현 — 조합을 순열값으로 오인한 양성 단편(M0087). 정본(nCr=nPr/r!)도
        # 두 토큰 공출현 가능(FP 한계·§5.3) — r! 분모 유무 판별은 임베딩/LLM 후속.
        signals=("조합", "nPr"),
    ),
    Misconception(
        id="same-item-permutation-no-divide",
        name_kr="같은 것 순열 중복 나눗셈 누락",
        domain="확률통계",
        canonical_statement="같은 것이 있는 순열에서 같은 것을 서로 다른 것으로 보고 n!로 센다",
        counterexample="AAB의 배열은 3!/2! = 3 (같은 A 중복 나눔), 3! = 6 아님",
        # "같은 것"+"서로 다른" 공출현 — 중복을 나누지 않은 양성 단편(M0190·분배누락). 정본은
        # "같은 것은 그 개수의 계승으로 나눈다"라 "서로 다른"을 포함하지 않아 구분된다.
        signals=("같은 것", "서로 다른"),
    ),
)

# 함수 — doc "함수"(#14, #28-29) (3종).
_FUNCTION: tuple[Misconception, ...] = (
    Misconception(
        id="invertibility-without-1-1",
        name_kr="역함수 무조건 존재",
        domain="함수",
        canonical_statement="모든 함수는 역함수를 갖는다",
        counterexample="f(x) = x²는 일대일 아님(전 정의역에서) → 역함수 없음",
        # 슬 101 정밀화: 바른 "모든"(거짓양성·예: "모든 x에서") → canonical 그대로 "모든 함수"로
        # 좁힘. concept_graph_dataset_v1.md §5.3 신호 정밀도 평가.
        signals=("역함수", "모든 함수"),
    ),
    Misconception(
        id="composite-function-commutes",
        name_kr="합성함수 교환 가정",
        domain="함수",
        canonical_statement="f∘g = g∘f (합성은 교환법칙 성립)",
        counterexample="f=x+1, g=x²: f∘g=x²+1 ≠ (x+1)²=g∘f",
        # "f∘g"+"g∘f" 공출현 — 둘을 등치한 양성 단편(∘는 NFKC 불변). 한계(§5.3): substring은
        # *부정*("f∘g≠g∘f")을 못 가려 두 합성을 대조한 올바른 진술에도 공출현→오탐 가능.
        # 그러나 두 토큰 AND라 *무관 풀이*엔 미발화하고, 공출현은 학생이 두 합성을 직접
        # 견준 맥락(오개념 개연 높음)이라 비난 없는 소크라테스 확인이 적절. 부정 판별은 임베딩 후속.
        signals=("f∘g", "g∘f"),
    ),
    Misconception(
        id="translation-sign-flip",
        name_kr="평행이동 부호 혼동",
        domain="함수",
        canonical_statement="y=f(x−a)는 왼쪽으로 a만큼 평행이동",
        counterexample="y=(x−2)²의 꼭짓점은 x=2 (오른쪽으로 +2 이동)",
        # "x-a"(인수의 음부호)+"왼쪽"의 공출현 — x−a를 왼쪽 이동이라 단정한 양성 단편.
        # 올바른 풀이는 "x-a"를 "오른쪽"과 잇거나 "x+a"를 "왼쪽"과 이어 구분된다.
        signals=("x-a", "왼쪽"),
    ),
)


# 미적분 — doc "미적분 영역"(#16-18, #15 재참조·#30, 극값 MC #33-34) (7종·수능 핵심).
# 주: continuity-implies-differentiability는 doc 함수 슬롯 #15에 상세하나 domain=미적분
# ([H:12미적Ⅰ02-02] 정착)이라 본 튜플에 둔다(doc 미적분 영역에서 재참조).
_CALCULUS: tuple[Misconception, ...] = (
    Misconception(
        id="chain-rule-inner-derivative-omitted",
        name_kr="연쇄법칙 내부도함수 누락",
        domain="미적분",
        canonical_statement="d/dx[sin(2x)] = cos(2x)",
        counterexample="정답은 2cos(2x) — 내부함수 2x의 도함수 2가 곱해져야 함",
        # 신호 정밀화: LHS식 `d/dx[sin(2x)]` + *틀린 RHS* `= cos(2x)`. 느슨한 `("d/dx","cos(2x)")`는
        # 정답 `d/dx[sin(2x)] = 2cos(2x)`까지 1.0 풀매칭(`cos(2x)`⊂`2cos(2x)`)해 *정답에 거짓
        # COUNTEREXAMPLE 개입*을 발화했다. 정답엔 `= cos(2x)` 없음(=`2cos`)→LHS만 0.5(게이트 미만)·
        # 틀림 `d/dx[sin(2x)]=cos(2x)`만 1.0. gate-safe.
        signals=("d/dx[sin(2x)]", "= cos(2x)"),
        # 정정 형태 — LHS만 공유·RHS `2cos(2x)`는 틀린 `cos(2x)`(계수 누락)와 다름 → 0.5. gate-safe.
        correct_form="d/dx[sin(2x)] = 2cos(2x)",
    ),
    Misconception(
        id="product-rule-naive",
        name_kr="곱의 미분 오류",
        domain="미적분",
        canonical_statement="(f·g)′ = f′·g′",
        counterexample="f=g=x: (x²)′ = 2x ≠ 1·1 = 1",
        signals=("(f·g)′", "f′·g′"),
        # 정정 형태(곱의 미분 법칙) — 좌변 `(f·g)′`만 공유하고 *틀린 RHS* `f′·g′`는 미포함
        # (`f′·g + f·g′`로 두 항 합) → 자기 오개념 conf 0.5(게이트 미만). gate-safe.
        correct_form="(f·g)′ = f′·g + f·g′",
    ),
    Misconception(
        id="limit-equals-function-value",
        name_kr="극한=함숫값 가정",
        domain="미적분",
        canonical_statement="lim_{x→a} f(x) = f(a) (항상)",
        counterexample="f(x)=(x²-1)/(x-1)는 x→1 극한 2지만 f(1) 무정의 (불연속점)",
        signals=("극한", "함숫값"),
    ),
    Misconception(
        id="continuity-implies-differentiability",
        name_kr="연속·미분가능 함의 혼동",
        domain="미적분",
        canonical_statement="연속이면 미분가능하다",
        counterexample="f(x)=|x|는 x=0에서 연속이나 미분불가 (뾰족점)",
        # "연속"+"미분가능"의 공출현 — 함의를 단정한 양성 단편. 한계(§5.3): 올바른 역방향
        # 진술("미분가능하면 연속")에도 두 토큰이 공출현→오탐 가능(substring은 방향·부정 무판별).
        # 두 토큰 AND로 무관 풀이엔 미발화하며, 정본 해법(방향성 판별)은 임베딩/LLM-judged 후속.
        signals=("연속", "미분가능"),
    ),
    Misconception(
        id="critical-point-implies-extremum",
        name_kr="임계점 극값 단정",
        domain="미적분",
        canonical_statement="f′(a)=0이면 그 점에서 극값을 갖는다",
        counterexample="f(x)=x³는 f′(0)=0이나 극값 아님 (변곡점)",
        # "f′=0"(인수 표기 없는 일반 진술형·NFKC 불변)+"극값"의 공출현 — f′=0에서 극값을
        # *단정*한 양성 단편. 한계(§5.3): 부호변화를 함께 본 올바른 진술("f′=0이고 부호변화→극값")
        # 에도 공출현→오탐 가능. 필요조건/충분조건 구별은 임베딩/LLM-judged 후속.
        signals=("f′=0", "극값"),
    ),
    Misconception(
        id="extremum-max-min-confused",
        name_kr="극대·극소 혼동",
        domain="미적분",
        # x³ 계수 양수 삼차함수는 극대가 *작은* 임계점, 극소가 *큰* 임계점에서 나오는데, 학생이
        # 이 순서를 구별하지 못하고 극댓값·극솟값을 서로 바꿔 답한다.
        canonical_statement="극댓값과 극솟값 중 어느 것이 어느 임계점에서 나오는지 상관없다",
        counterexample=(
            "이 예에서는 f(x)=x^3-3x가 x=-1(작은 임계점)에서 극대(2)·x=1에서 극소(-2)"
            " — 계수 양수라 순서 고정"
        ),
        # "극댓값"+"극솟값" 공출현 — 둘의 순서를 구별 못한 양성 단편. §5.3 한계: 둘을 올바로 병기한
        # 정답(극댓값 2·극솟값 -2)에도 공출현→오탐 가능(substring은 방향·정오 무판별). 두 토큰 AND라
        # 무관 풀이엔 미발화하고, 정본 해법(계수 부호→극대극소 순서 판정)은 임베딩/LLM-judged 후속.
        # 극값 동등문제 객관식 distractor(극솟값 선지) 역추적 좌석([H:12미적Ⅰ02-07]).
        signals=("극댓값", "극솟값"),
    ),
    Misconception(
        id="extremum-value-vs-point-confused",
        name_kr="극값·극점 혼동",
        domain="미적분",
        # 극값의 *값*(f의 함숫값)과 극점의 *x좌표*를 혼동 — "극댓값"을 극대가 되는 점의 x좌표로 답.
        canonical_statement="극댓값은 극대가 되는 점의 x좌표이다",
        counterexample=(
            "f(x)=x^3-3x의 극대는 x=-1에서지만 극댓값은 f(-1)=2 — x좌표 -1이 아님."
            " 극대점(극대가 되는 점)·그 x좌표(-1)·극댓값(함숫값 2)은 각각 다른 대상이다"
        ),
        # "극댓값"+"x좌표" 공출현 — 값을 x좌표로 답한 양성 단편. §5.3 한계: "극댓값을 구하려 극점의
        # x좌표를 먼저 찾는다"류 올바른 풀이에도 공출현→오탐 가능(두 토큰 AND·무관 풀이 미발화).
        # 값/좌표 구별의 정본 판정은 임베딩/LLM-judged 후속. 극값 동등문제 객관식 distractor(극점
        # x좌표 선지) 역추적 좌석([H:12미적Ⅰ02-07]).
        signals=("극댓값", "x좌표"),
    ),
)

# 수열 — doc L62-64 (2종·수능 빈출). 슬 추가.
_SEQUENCE: tuple[Misconception, ...] = (
    Misconception(
        id="geometric-series-always-converges",
        name_kr="등비급수 무조건 수렴",
        domain="수열",
        canonical_statement="무한등비급수는 항상 수렴한다",
        counterexample="공비 r=2면 1+2+4+⋯ 발산 — |r|<1일 때만 수렴",
        signals=("등비급수", "수렴"),
    ),
    Misconception(
        id="term-to-zero-implies-convergence",
        name_kr="항→0이면 수렴 가정",
        domain="수열",
        canonical_statement="일반항이 0에 수렴하면 급수도 수렴한다",
        counterexample="조화급수 Σ1/n은 일반항→0이지만 발산",
        signals=("급수", "수렴"),
    ),
)

# 삼각함수 — doc L67-69 (2종·수능 핵심). 슬 추가.
_TRIG: tuple[Misconception, ...] = (
    Misconception(
        id="sine-distributes-over-sum",
        name_kr="사인 합 분배",
        domain="삼각함수",
        canonical_statement="sin(a+b) = sin a + sin b",
        counterexample="a=b=90°: sin180° = 0 ≠ sin90° + sin90° = 2",
        signals=("sin(a+b)", "sin a + sin b"),
        # 정정 형태(사인 덧셈정리) — 좌변 `sin(a+b)`만 공유하고 *틀린 RHS* `sin a + sin b`는 미포함
        # (`sin a cos b + cos a sin b`) → 자기 오개념 conf 0.5(게이트 미만). gate-safe.
        correct_form="sin(a+b) = sin a cos b + cos a sin b",
    ),
    Misconception(
        id="period-of-scaled-sine",
        name_kr="주기 변환 무시",
        domain="삼각함수",
        canonical_statement="y=sin(2x)의 주기는 2π",
        counterexample="주기는 π — 계수 2가 주기를 2π/2로 줄임",
        signals=("주기", "2π"),
    ),
)

# 벡터 — doc L72-73 (1종·수능 기하). 슬 추가.
_VECTOR: tuple[Misconception, ...] = (
    Misconception(
        id="dot-product-is-vector",
        name_kr="내적 결과를 벡터로",
        domain="벡터",
        canonical_statement="두 벡터의 내적 a·b는 벡터이다",
        counterexample="내적은 스칼라(실수): a·b = |a||b|cosθ",
        signals=("내적", "벡터"),
    ),
)


CATALOG: tuple[Misconception, ...] = (
    _ALGEBRA + _GEOMETRY + _PROBSTAT + _FUNCTION + _CALCULUS + _SEQUENCE + _TRIG + _VECTOR
)
"""정본 카탈로그(34종 = Phase 1 30종 + S2-p 2종 + 극값 MC 2종) — doc 명시·상세화 항목만.

슬: §5.4 교차검증 고가치 후보 8종 추가(대수+2·기하+1·확률통계+1·함수+2·미적분+2).
S2-p: 이차방정식 근 선택 지시 무시·인수 부호 반전 2종 추가(대수 11종) — 동등문제 객관식
distractor 역추적 좌석(doc #31-32). 극값 MC: 극대·극소 혼동·극값의 값↔극점 x좌표 혼동 2종
추가(미적분 7종·doc #33-34) — 삼차 극값 동등문제 객관식 distractor 역추적 좌석.
positive-signal형(학생이 *틀린 주장을 직접 적는* 유형)만 채택 — omission형(적분상수 누락·
정의역 끝점)은 substring이 *오류 부재*를 못 잡으므로(§5.3 한계) 의도적 회피(임베딩 후속).

순서 안정성: 신규 항목은 각 도메인 *기존 항목 뒤에* 붙인다(진단 동률 정렬이 대수
distribution-over-power를 첫째로 유지 — 회귀 가드). 도메인 튜플 합성 순서도 불변
(_ALGEBRA 먼저)."""


CATALOG_BY_ID: dict[str, Misconception] = {m.id: m for m in CATALOG}
"""ID로 O(1) 조회 — 진단 결과·텔레메트리에서 misconception_id로 역참조 시."""
