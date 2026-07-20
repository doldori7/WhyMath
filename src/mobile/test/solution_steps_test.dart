// mergeStepTexts 단위 테스트 (MOB-07) — MathLive 입력을 풀이 단계 필드에 배치하는 순수 규칙 동결.
//
// 규칙: 빈 필드부터 채우고, 남은 줄은 새 필드로 덧붙인다. 기존 비어있지 않은 필드는 보존.
// 이 규칙 덕에 학생은 숨은 줄바꿈(⊕) 없이 눈에 보이는 단계 필드로 다단계를 쌓을 수 있다.
import 'package:flutter_test/flutter_test.dart';
import 'package:korean_math_app/features/chat/domain/solution_steps.dart';

void main() {
  group('mergeStepTexts', () {
    test('빈 2필드에 2줄 → 순서대로 채운다(⊕ 여러 줄 한 번에 입력 케이스)', () {
      expect(
        mergeStepTexts(<String>['', ''], <String>['2x+3=7', 'x=2']),
        <String>['2x+3=7', 'x=2'],
      );
    });

    test('1필드 찬 상태 + 1줄 → 다음 빈칸을 채운다(한 단계씩 입력 케이스)', () {
      expect(
        mergeStepTexts(<String>['2x+3=7', ''], <String>['x=2']),
        <String>['2x+3=7', 'x=2'],
      );
    });

    test('빈칸이 없으면 새 필드로 덧붙인다(기존 값 보존)', () {
      expect(
        mergeStepTexts(<String>['a', 'b'], <String>['c', 'd']),
        <String>['a', 'b', 'c', 'd'],
      );
    });

    test('빈칸 채우고 남은 줄은 덧붙인다(혼합)', () {
      expect(
        mergeStepTexts(<String>['a', ''], <String>['b', 'c']),
        <String>['a', 'b', 'c'],
      );
    });

    test('중간 빈칸도 순서대로 채운다', () {
      expect(
        mergeStepTexts(<String>['a', '', 'c', ''], <String>['b', 'd']),
        <String>['a', 'b', 'c', 'd'],
      );
    });

    test('공백/빈 줄은 무시한다', () {
      expect(
        mergeStepTexts(<String>['', ''], <String>['  ', 'x=2', '']),
        <String>['x=2', ''],
      );
    });

    test('단일 줄 → 첫 빈칸을 채운다', () {
      expect(
        mergeStepTexts(<String>['', ''], <String>['2x+3=7']),
        <String>['2x+3=7', ''],
      );
    });

    test('채울 줄이 없으면 원본을 그대로 돌려준다(길이·값 불변)', () {
      expect(
        mergeStepTexts(<String>['a', ''], <String>['  ', '']),
        <String>['a', ''],
      );
    });

    test('입력을 변형하지 않는다(새 리스트 반환·기존 필드 보존)', () {
      final current = <String>['a', ''];
      final result = mergeStepTexts(current, <String>['b']);
      expect(result, <String>['a', 'b']);
      expect(current, <String>['a', ''], reason: 'current는 변형되지 않아야 한다');
    });
  });
}
