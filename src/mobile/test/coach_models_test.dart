// coach_models 역직렬화·라운드트립 테스트.
//
// 백엔드 `CoachResponse` 샘플 JSON(이 세션 WH-1 1단계 신호 전부 포함)을 `fromJson`으로
// 파싱해 필드를 단언하고, `toJson` 라운드트립으로 키·값 보존을 검증한다. 백엔드 계약과
// 클라 모델이 *비트 정합*하는지(필드명·nullable·중첩) 확인하는 게이트다.
//
// 로컬 SDK 부재로 이 테스트는 CI Flutter 잡에서만 실행된다(build_runner codegen 후).
import 'package:flutter_test/flutter_test.dart';
import 'package:korean_math_app/features/chat/data/coach_models.dart';

void main() {
  group('CoachResponse.fromJson — WH-1 1단계 신호 포함 샘플', () {
    // 백엔드 coach.py CoachResponse 직렬화 형태를 모사한 샘플.
    // solution_coaching.trigger.focus_step_index·solution_verification·
    // verification_ocr_gated·match_low_quality·no_confident_match 포함.
    Map<String, dynamic> sampleJson() => <String, dynamic>{
          'decision': <String, dynamic>{
            'polya_stage_to_advance': 'stay',
            'hint_level': 2,
            'socratic_category': 'evidence',
            'prompt': '그 줄이 바로 윗줄과 같은 값인지 다시 확인해볼까?',
            'system': '너는 답을 미루고 사고를 유도하는 수학 코치다.',
            'recommended_cost_tier': 'local',
            'suggested_actions': <String>['highlight_step'],
            'reveals': 'step_flow',
          },
          'misconceptions': <Map<String, dynamic>>[
            <String, dynamic>{
              'misconception': <String, dynamic>{
                'id': 'distribution-over-power',
                'name_kr': '제곱 분배',
                'domain': '대수',
                'canonical_statement': '(a+b)^2 = a^2+b^2',
                'counterexample': 'a=1, b=1',
                'signals': <String>['(a+b)^2', 'a^2+b^2'],
                'regex_signals': <String>[],
              },
              'confidence': 0.92,
              'matched_signals': <String>['(a+b)^2'],
              'matched_regex_signals': <String>[],
              'semantic_similarity': null,
            },
          ],
          'intervention': <String, dynamic>{
            'pattern': 'counterexample',
            'prompt': 'a=1, b=1을 직접 넣어보면 어떻게 될까?',
            'misconception_id': 'distribution-over-power',
          },
          'lthc': <String, dynamic>{
            'mastery_level': '발전 중',
            'entry_suggestions': <String>['작은 수로 먼저 해볼까?'],
            'extensions': <String>['일반화해볼 수 있을까?'],
            'scaffolds': <String>['지난 비슷한 문제를 떠올려볼까?'],
          },
          'entry_socratic_category': 'evidence',
          'solution_coaching': <String, dynamic>{
            'trigger': <String, dynamic>{
              'focus': 'verify',
              'rationale': '단계 검증에서 어긋난 전이가 발견됨.',
              'prompt': '처음 2줄까지는 잘 따라왔어. 3번째 줄을 다시 확인해볼까?',
              'socratic_category': 'evidence',
              'focus_step_index': 1,
            },
            'arithmetic_error': true,
            'validation_signal': "arithmetic error: '2 + 3 = 6' (sympy: 5 != 6)",
            'error_kind': 'arithmetic',
            'error_span': <int>[4, 13],
            'solution_verification': <String, dynamic>{
              'n_correct': 1,
              'n_incorrect': 1,
              'n_unverifiable': 0,
              'n_transitions': 2,
              'unverified_ratio': 0.0,
              'first_incorrect_index': 1,
              'has_incorrect': true,
            },
            'verification_ocr_gated': false,
          },
          'prerequisite_coaching': null,
          'match_low_quality': true,
          'no_confident_match': false,
        };

    test('핵심 결정·신호 필드를 정확히 파싱한다', () {
      final res = CoachResponse.fromJson(sampleJson());

      // 핵심 결정.
      expect(res.decision.polyaStageToAdvance, 'stay');
      expect(res.decision.hintLevel, 2);
      expect(res.decision.reveals, 'step_flow');
      expect(res.decision.suggestedActions, contains('highlight_step'));

      // 오개념 매칭(중첩).
      expect(res.misconceptions, hasLength(1));
      expect(res.misconceptions.first.confidence, closeTo(0.92, 1e-9));
      expect(res.misconceptions.first.misconception.nameKr, '제곱 분배');
      expect(res.misconceptions.first.semanticSimilarity, isNull);

      // 개입·LTHC.
      expect(res.intervention, isNotNull);
      expect(res.intervention!.pattern, 'counterexample');
      expect(res.lthc, isNotNull);
      expect(res.lthc!.masteryLevel, '발전 중');
      expect(res.lthc!.scaffolds, isNotEmpty);

      // WH-1 1단계 — solution_coaching 신호.
      final sc = res.solutionCoaching;
      expect(sc, isNotNull);
      expect(sc!.arithmeticError, isTrue);
      expect(sc.errorKind, 'arithmetic');
      expect(sc.errorSpan, <int>[4, 13]);
      expect(sc.verificationOcrGated, isFalse);

      // trigger.focus_step_index(구조화 위치 메타데이터).
      expect(sc.trigger.focus, 'verify');
      expect(sc.trigger.focusStepIndex, 1);

      // solution_verification(단계별 검증 카운트·위치).
      final sv = sc.solutionVerification;
      expect(sv, isNotNull);
      expect(sv!.nTransitions, 2);
      expect(sv.hasIncorrect, isTrue);
      expect(sv.firstIncorrectIndex, 1);

      // §3.3 게이트 플래그.
      expect(res.matchLowQuality, isTrue);
      expect(res.noConfidentMatch, isFalse);
      expect(res.prerequisiteCoaching, isNull);
    });

    test('toJson 라운드트립 — fromJson∘toJson 동치', () {
      final res = CoachResponse.fromJson(sampleJson());
      final roundTripped = CoachResponse.fromJson(res.toJson());
      // freezed 값 동치(==)로 라운드트립 보존을 단언한다.
      expect(roundTripped, equals(res));
    });
  });

  group('CoachResponse.fromJson — 최소(조건부 필드 누락) 응답', () {
    test('decision만 있고 나머지는 기본값/null로 채워진다', () {
      // 백엔드가 조건부 필드를 생략하면 default_factory/None에 대응.
      // 스테이트리스 /v1/coach의 최소 응답을 모사(misconceptions 빈 리스트 등).
      final res = CoachResponse.fromJson(<String, dynamic>{
        'decision': <String, dynamic>{
          'polya_stage_to_advance': 'next',
          'prompt': '문제를 네 말로 다시 설명해볼래?',
          'system': '코치 시스템 프롬프트.',
        },
        'misconceptions': <Map<String, dynamic>>[],
        'match_low_quality': false,
        'no_confident_match': false,
      });

      expect(res.decision.hintLevel, 1); // 기본값.
      expect(res.decision.socraticCategory, ''); // 기본 빈 문자열.
      expect(res.misconceptions, isEmpty);
      expect(res.intervention, isNull);
      expect(res.lthc, isNull);
      expect(res.solutionCoaching, isNull);
      expect(res.matchLowQuality, isFalse);
    });
  });

  group('CoachRequest.toJson — 키 매핑·null 생략', () {
    test('snake_case 키로 직렬화하고 null 필드는 생략', () {
      const req = CoachRequest(
        studentInput: '판별식이 뭐였죠?',
        ocrConfidence: 0.5,
      );
      final json = req.toJson();
      expect(json['student_input'], '판별식이 뭐였죠?');
      expect(json['ocr_confidence'], 0.5);
      // 미설정 옵셔널은 null(백엔드 default 적용) — 키 존재해도 값은 null.
      expect(json['student_solution'], isNull);
    });
  });
}
