// 풀이 단계 필드 병합 규칙 (MOB-07) — MathLive "완료"로 받은 평문 수식 줄들을 기존 단계
// 필드에 어떻게 배치할지 결정하는 *순수* 함수.
//
// 왜(2026-07-20 실기기 실측): MathLive 0.110.0에서 여러 줄(`\displaylines`)을 만드는 줄바꿈은
// Enter 키의 Shift 변형(⊕ `addRowAfter`)에만 숨어 있어(기본 Enter=commit·`menuItems=[]`로 메뉴
// 비활성·라벨 없음) 학생이 발견하기 어렵다. 그래서 "수식으로 입력" 완료가 수식을 눈에 보이는
// 풀이 단계 필드(`_SolutionStepsEditor`)에 채워, 학생이 숨은 제스처 없이 다단계를 쌓게 한다.
//
// 경계(CLAUDE.md 표현≠의미): 표기 배치만 한다 — 수학 판정·검증은 없다(백엔드 verify 몫).

/// 기존 단계 필드 텍스트 [current]에 새 평문 줄 [incoming]을 병합한 결과 리스트를 돌려준다(순수).
///
/// 규칙: **빈 필드부터 채우고, 남은 줄은 새 필드로 덧붙인다.** 기존 비어있지 않은 필드는 보존한다
/// (덮어쓰지 않음). [incoming]의 공백/빈 줄은 무시한다. 채울 게 없으면 [current] 사본을 그대로
/// 돌려준다(길이·값 불변). 필드를 줄이지는 않는다(학생이 지운 게 아니므로).
List<String> mergeStepTexts(List<String> current, List<String> incoming) {
  final lines = incoming
      .map((line) => line.trim())
      .where((line) => line.isNotEmpty)
      .toList();
  final result = List<String>.of(current);
  if (lines.isEmpty) {
    return result; // 채울 게 없다 — 원본 유지.
  }
  var next = 0;
  // 1) 빈 필드부터 순서대로 채운다.
  for (var i = 0; i < result.length && next < lines.length; i++) {
    if (result[i].trim().isEmpty) {
      result[i] = lines[next];
      next++;
    }
  }
  // 2) 남은 줄은 새 필드로 덧붙인다.
  while (next < lines.length) {
    result.add(lines[next]);
    next++;
  }
  return result;
}
