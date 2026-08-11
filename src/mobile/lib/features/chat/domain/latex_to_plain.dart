// LaTeX→평문 수식 변환 (MOB-06) — MathLive가 낸 LaTeX 직렬화를 백엔드 verify 계약이 받는
// *평문 수식 표기*로 되돌린다. 여러 줄 수식은 `'\n'`으로 조인된 여러 스텝이 된다.
//
// 경계(CLAUDE.md 표현≠의미): 이 변환은 **표기(notation) 매핑이지 수학 의미(semantic) 판정이
// 아니다.** 동치·약분·정오 판정은 100% 백엔드(L3 `verify_solution`)가 한다. 클라가 이미 하는
// 표현 수준 세그먼트(`chat_controller._splitSteps` 줄 분해)와 같은 범주 — LaTeX 직렬화를 계약이
// 받는 평문 표기로 되돌릴 뿐이다.
//
// 왜 필요한가(2026-07-20 실기기 실측): MathLive는 여러 줄을 `\displaylines{... \\ ...}`로
// 직렬화한다. 그 원문을 그대로 보내면 (1) 학생 버블에 LaTeX가 노출되고 (2) 행 구분자 `\\`는
// `'\n'` 분해에 걸리지 않아 단일 0-전이 스텝이 되어 verify가 아무 것도 결정하지 못한다.
//
// 드리프트 방지(MATH-01, 2026-08-11): 백엔드 `l3/symbolic_equivalence.latex_to_plain`과 **같은
// 규칙집합**이며, 그 일치를 `data/notation_contract.json`의 `latex_cases`가 골든으로 동결한다
// (`test/latex_to_plain_test.dart` ↔ `tests/backend/l3/test_notation_contract.py`가 같은 파일을
// 읽는다). 규칙을 한쪽만 바꾸면 계약을 고치지 않는 한 반대편이 red가 된다.
//
// 이 주석은 이전에 "백엔드 `_latex_to_sympifiable`를 그대로 미러"라고 적었으나 **부분 거짓**이었다 —
// 실제로는 `\leq`·간격 매크로·`\displaylines`가 Dart 고유 확장이었고 백엔드에 없었다. MATH-01이
// 백엔드를 이 규칙집합에 정렬하면서 그 자인을 참으로 만들었고(py의 경계 검사 부재·`\leq` 미처리
// 결함 2건이 함께 해소), 이제는 계약이 그 사실을 기계로 지킨다.
//
// 타깃 표기 권위는 백엔드 `l3/symbolic_equivalence`다 — `latex_to_plain`(LaTeX 계층) +
// `to_sympy_source`(유니코드·전각·그리스 계층)를 합친 것이 "입력 정규화 단일 권위"다.
// 이 파일은 그 권위의 *미러*이지 권위가 아니다(수학 판정 0 — `no_math_logic_governance_test.dart`).
//
// caret-less 지수 금지(백엔드 실측): `x²`·`x^2`는 verify가 받지만 `x2`는 수열 표기(`a1`)와
// 모호해 백엔드가 보수적으로 unverifiable 처리한다. 그래서 중괄호는 괄호로 바꿔 `x^{2}`→`x^(2)`
// (캐럿·그룹 보존)로 두고, 캐럿 없는 지수를 절대 만들지 않는다.

/// `\frac(a)(b)` → `((a)/(b))` — 중괄호를 괄호로 바꾼 *뒤* 매칭한다(백엔드 `_FRAC_RE` 미러).
/// 인자에 중첩 괄호는 다루지 않는다(`[^()]*`) — 백엔드와 동일 한계(중첩 분수는 드물고, 걸리면
/// 백엔드가 unverifiable로 보수 처리하므로 거짓 판정 위험 없음).
final RegExp _fracRe = RegExp(r'\\frac\s*\(([^()]*)\)\s*\(([^()]*)\)');

/// `\sqrt(x)` → `sqrt((x))` (백엔드 `_SQRT_RE` 미러).
final RegExp _sqrtRe = RegExp(r'\\sqrt\s*\(([^()]*)\)');

/// 명시 연산자·구획 명령 — 값이 명시 기호(`*`·`/`·`(`·`)`)라 뒤따르는 공백 1개를 함께 삼켜도
/// 안전하다(`2\times x`→`2*x`). LaTeX 제어어의 공백 삼킴 관례와도 일치한다.
const Map<String, String> _operatorCommands = <String, String>{
  r'\left': '',
  r'\right': '',
  r'\cdot': '*',
  r'\times': '*',
  r'\div': '/',
};

/// 식별자·관계로 바뀌는 명령 — 뒤 공백을 삼키면 토큰이 병합돼(`\pi r`→`pir`=단일 심볼) 의미가
/// 깨지므로 공백을 보존한다. 관계 연산자는 등식 스텝에선 대개 undecidable이지만 버블 가독성을 위해
/// 자연 기호로 바꾼다(백엔드가 안전 처리).
const Map<String, String> _symbolCommands = <String, String>{
  r'\displaystyle': '',
  r'\pi': 'pi',
  r'\leq': '<=',
  r'\le': '<=',
  r'\geq': '>=',
  r'\ge': '>=',
  r'\neq': '!=',
  r'\ne': '!=',
};

/// 간격 매크로·정렬 기호 — 표기에 의미 없음(제거 또는 공백).
const Map<String, String> _spacingReplacements = <String, String>{
  r'\quad': ' ',
  r'\qquad': ' ',
  r'\,': '',
  r'\;': '',
  r'\:': '',
  r'\!': '',
  r'\ ': ' ',
  '~': ' ',
  '&': '',
};

/// LaTeX 제어어(`\`+알파벳)를 매칭할 정규식 조각 — 앞 백슬래시만 이스케이프한다(SDK 무관·
/// `RegExp.escape` 비의존). 키는 전부 `\`+알파벳이라 다른 메타문자는 없다.
String _commandPattern(String cmd) => '\\\\${cmd.substring(1)}';

/// MathLive LaTeX를 백엔드 verify 계약이 받는 평문 수식 줄(`'\n'` 조인)로 변환한다(순수).
///
/// 여러 줄(`\displaylines{... \\ ...}`)은 여러 스텝으로 분해돼 `'\n'`으로 조인된다 — 컨트롤러
/// `_splitSteps`가 다시 줄로 나눠 `solution_steps`(인접 전이 검증 가능)로 보낸다. 빈/공백뿐이면
/// 빈 문자열을 돌려준다(전송 판정은 호출자). 수학 판정은 하지 않는다(표기 변환만).
String latexToPlainSolution(String latex) {
  final rows = _splitLatexRows(latex)
      .map(_latexRowToPlain)
      .map((String row) => row.trim())
      .where((String row) => row.isNotEmpty)
      .toList();
  return rows.join('\n');
}

/// `\displaylines{...}`·`\begin{env}...\end{env}` 껍데기를 벗기고 행 구분자 `\\`로 분해한다.
List<String> _splitLatexRows(String latex) {
  String s = latex.trim();
  s = _unwrapDisplaylines(s);
  s = _stripEnvironments(s);
  // 행 구분자 `\\`(백슬래시 2개)로 분해 — `\displaylines`·`\frac`의 단일 백슬래시와 구분된다.
  return s.split(RegExp(r'\\\\'));
}

/// `\displaylines{...}` 래퍼를 벗겨 안쪽 내용만 돌려준다(중첩 중괄호 균형 스캔). 없으면 원문 유지.
String _unwrapDisplaylines(String s) {
  const String marker = r'\displaylines';
  final int idx = s.indexOf(marker);
  if (idx < 0) {
    return s;
  }
  final int braceStart = s.indexOf('{', idx);
  if (braceStart < 0) {
    return s;
  }
  final String? inner = _extractBalancedBraces(s, braceStart);
  // 래퍼 밖 텍스트는 버린다 — displaylines 전체가 곧 풀이다(MathLive 여러 줄 직렬화).
  return inner ?? s;
}

/// [open](여는 `{`)부터 짝이 맞는 `}`까지의 안쪽 내용을 돌려준다(불균형이면 null·원문 보존).
String? _extractBalancedBraces(String s, int open) {
  int depth = 0;
  for (int i = open; i < s.length; i++) {
    final String c = s[i];
    if (c == '{') {
      depth++;
    } else if (c == '}') {
      depth--;
      if (depth == 0) {
        return s.substring(open + 1, i);
      }
    }
  }
  return null;
}

/// `\begin{env}`(및 `array`의 열 스펙 인자)·`\end{env}` 환경 껍데기를 제거한다(정렬 행렬 등).
String _stripEnvironments(String s) {
  return s
      .replaceAll(RegExp(r'\\begin\{[a-zA-Z*]+\}(\{[^{}]*\})?'), '')
      .replaceAll(RegExp(r'\\end\{[a-zA-Z*]+\}'), '');
}

/// 한 행의 LaTeX 토큰을 평문 수식으로 치환한다(순수·백엔드 `_latex_to_sympifiable` 미러 + 확장).
String _latexRowToPlain(String row) {
  // 1) 중괄호 → 괄호 (백엔드 순서 미러) — `x^{2}`→`x^(2)`(caret 보존), `\frac`/`\sqrt` 인자 매칭 준비.
  String s = row.replaceAll('{', '(').replaceAll('}', ')');
  // 2) 분수·근호 환원(중괄호 치환 후).
  s = s.replaceAllMapped(_fracRe, (Match m) => '((${m[1]})/(${m[2]}))');
  s = s.replaceAllMapped(_sqrtRe, (Match m) => 'sqrt((${m[1]}))');
  // 3) 연산자·구획 명령 — 제어어 경계 `(?![A-Za-z])` + 뒤 공백 1개 삼킴(값이 명시 기호라 안전).
  //    경계 덕에 `\le`가 `\left` 안에서 오탐되지 않는다(별도 순서 의존 없음).
  _operatorCommands.forEach((String cmd, String repl) {
    s = s.replaceAll(RegExp('${_commandPattern(cmd)}(?![A-Za-z]) ?'), repl);
  });
  // 4) 식별자·관계 명령 — 경계만(뒤 공백 보존 — `\pi r`→`pir` 병합 방지).
  _symbolCommands.forEach((String cmd, String repl) {
    s = s.replaceAll(RegExp('${_commandPattern(cmd)}(?![A-Za-z])'), repl);
  });
  // 5) 간격 매크로·정렬 기호 제거.
  _spacingReplacements.forEach((String token, String repl) {
    s = s.replaceAll(token, repl);
  });
  // 6) 다중 공백 접기(단일 공백은 보존 — 식별자 병합 방지).
  return s.replaceAll(RegExp(r' +'), ' ');
}
