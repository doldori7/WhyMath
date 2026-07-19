// MathLive 입력 자산(index.html) 설정 정적 동결 테스트 (MOB-03)
//
// WebView 내부 렌더는 헤드리스 flutter test에서 검증 불가(플랫폼 뷰) — 여기서는 실기기
// 실측으로 확정한 설정·호출 순서를 *소스 텍스트 수준*에서 동결한다(governance 테스트의
// 파일 스캔 방식 답습, cwd = src/mobile).
//
// 동결 근거(번들 v0.110.0 실측 — 2026-07-19 MOB-03):
// ① MathfieldElement.menuItems setter는 마운트 전 호출 시 "Mathfield not mounted"를
//    throw한다 → index.html의 try/catch가 삼켜 textarea 폴백으로 *침묵 강등*된다.
//    따라서 menuItems=[]는 반드시 appendChild(mf) 이후여야 한다(순서 동결).
// ② menuItems=[]는 빈 배열이면 햄버거 토글 display:none + Menu.visible=false(show no-op).
// ③ 번들 교체(버전 업) 시 아래 표면 검사들이 의도적으로 실패한다 — CLAUDE.md "외부 SDK
//    표면 실측" 규칙에 따라 새 번들에서 setter·part·throw 문자열을 재실측한 뒤 갱신하라.

import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

void main() {
  // 테스트 실행 cwd = src/mobile (flutter test 규약 — no_math_logic_governance_test 선례)
  final String indexHtml =
      File('assets/mathlive_input/index.html').readAsStringSync();
  final String iifeBundle =
      File('assets/mathlive_input/mathlive.iife.js').readAsStringSync();
  final String moduleBundle =
      File('assets/mathlive_input/mathlive.min.js').readAsStringSync();

  group('index.html 초기화 설정 (MOB-03 실기기 증상 재발 방지)', () {
    test('컨텍스트 메뉴 비활성: mf.menuItems = [] 설정이 존재한다', () {
      expect(
        indexHtml.contains('mf.menuItems = [];'),
        isTrue,
        reason: '고3 UX 소음(행렬 삽입·Insert·모드·글꼴 메뉴) 제거 설정이 사라짐 — '
            'menuItems=[]가 햄버거 토글 숨김 + 메뉴 show no-op의 단일 스위치다',
      );
    });

    test('호출 순서: menuItems 설정은 appendChild(mf) *이후*다 (마운트 전 throw 방지)', () {
      final int appendAt = indexHtml.indexOf('host.appendChild(mf);');
      final int menuAt = indexHtml.indexOf('mf.menuItems = [];');
      expect(appendAt, greaterThanOrEqualTo(0),
          reason: 'host.appendChild(mf) 호출이 index.html에 있어야 한다');
      expect(menuAt, greaterThan(appendAt),
          reason: 'menuItems setter는 마운트 전 "Mathfield not mounted" throw → '
              'try/catch가 삼켜 textarea 폴백으로 침묵 강등된다(번들 v0.110.0 실측). '
              '순서를 바꾸지 말 것');
    });

    test('가상 키보드 정책: manual(토글 진입) 유지', () {
      expect(
        indexHtml.contains('mf.mathVirtualKeyboardPolicy = "manual";'),
        isTrue,
        reason: '키보드 토글(part=virtual-keyboard-toggle)이 유일한 진입점 — '
            'manual 정책이 사라지면 진입 UX가 바뀐다',
      );
    });

    test('햄버거 토글 CSS 이중 가드: ::part(menu-toggle) display:none', () {
      expect(
        RegExp(r'math-field::part\(menu-toggle\)\s*\{[^}]*display:\s*none',
                dotAll: true)
            .hasMatch(indexHtml),
        isTrue,
        reason: 'JS 순서가 바뀌어도 햄버거가 노출되지 않게 하는 정적 CSS 가드',
      );
    });

    test('브라우저 기본 컨텍스트 메뉴 억제 폴백이 존재한다', () {
      expect(
        indexHtml.contains('mf.addEventListener("contextmenu"'),
        isTrue,
        reason: 'MathLive 메뉴가 꺼진 상태에서 네이티브 메뉴가 새지 않게 하는 폴백',
      );
    });

    test('가상 키보드 컨테이너를 커스텀 지정하지 않는다 (기본 body = 뷰포트 하단 도킹)', () {
      // container를 바꾸면 position:relative 모드로 전환돼 배치를 직접 관리해야 한다
      // (번들 실측: body 컨테이너일 때만 body > .ML__keyboard{position:fixed} 도킹).
      expect(
        indexHtml.contains('mathVirtualKeyboard.container'),
        isFalse,
        reason: '하단 도킹은 기본(body) 컨테이너 + Flutter Expanded 배치로 달성한다 — '
            '커스텀 컨테이너 도입 시 이 테스트와 배치 설계를 함께 재검토하라',
      );
    });
  });

  group('번들 API 표면 실측 동결 (침묵 실패 방지 — CLAUDE.md SDK 표면 규칙)', () {
    test('번들 버전 핀: v0.110.0 (교체 시 표면 재실측 후 갱신)', () {
      expect(iifeBundle.contains('version="0.110.0"'), isTrue,
          reason: '번들이 교체됨 — menuItems setter·part 속성·도킹 CSS를 새 번들에서 '
              '재실측(grep)한 뒤 이 테스트의 기대 문자열을 갱신하라');
    });

    test('menuItems setter가 실물 번들에 존재한다 (IIFE·모듈 양쪽)', () {
      // 우리가 호출하는 표면이 번들에 실재함을 동결 — 미지원 API 호출은 침묵 실패 위험.
      expect(iifeBundle.contains('set menuItems('), isTrue);
      expect(moduleBundle.contains('set menuItems('), isTrue);
    });

    test('마운트 전 throw 메시지가 번들에 존재한다 (순서 동결의 근거)', () {
      expect(iifeBundle.contains('Mathfield not mounted'), isTrue,
          reason: '이 throw가 사라진 번들이면 호출 순서 제약을 재실측하라');
    });

    test('part=menu-toggle 렌더가 번들에 존재한다 (CSS 가드의 근거)', () {
      expect(iifeBundle.contains('part=menu-toggle'), isTrue);
    });

    test('하단 도킹 CSS 메커니즘이 번들에 존재한다 (body 컨테이너 fixed 도킹)', () {
      expect(iifeBundle.contains('body > .ML__keyboard'), isTrue,
          reason: '키보드가 WebView 뷰포트 하단에 도킹하는 근거 CSS — 사라지면 '
              'Expanded 배치 설계를 재검토하라');
    });
  });
}
