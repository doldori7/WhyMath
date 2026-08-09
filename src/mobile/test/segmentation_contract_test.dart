// 풀이 세그멘테이션 골든 계약 테스트 (NLP-03·D3) — 순수 테스트 신설, 프로덕션 코드 미변경.
//
// 정본: `docs/architecture/nlp_module_gap_review.md` §3 D3. 계약 파일은
// `data/segmentation_contract.json`(리포 루트, `notation_contract.json` 선례와 동형) — 백엔드
// `l5/ocr/text_segmentation.py segment_solution_text`가 authority, 이 파일은 그 계약이
// 모바일 미러(`chat_controller._splitSteps` 줄 분해 + `latex_to_plain.dart` displaylines 언랩)
// *기존 동작*과 일치함을 기계로 동결한다 — 알고리즘 변경 없음, 회귀 방지용 골든 테스트다.
//
// 접근 방법: `_splitSteps`는 `ChatController`의 private static 멤버라 이 테스트 파일(별도
// 라이브러리)에서 직접 호출할 수 없다(Dart 프라이버시=파일 스코프). 기존
// `chat_controller_test.dart`가 이미 확립한 관례 — fake `CoachApi`로 `coachApiProvider`를
// override해 `sendSolution`/`sendMathLiveSolution`(공개 API)을 호출하고, fake가 캡처한
// `CoachRequest.solutionSteps`(서버로 나간 실제 페이로드)를 단언 — 를 그대로 따른다. 이 경로가
// `_splitSteps`(+ displaylines 케이스는 `latexToPlainSolution`)를 정확히 거치므로 사실상 private
// 함수를 공개 경로로 우회 관찰하는 것과 동일하다.
//
// `ambiguous` 필드는 검증하지 않는다(현재 Dart 코드는 이 신호를 계산하지 않음 — 백엔드 전용
// 관측 신호, CLAUDE.md 표현≠의미 경계).
import 'dart:convert';
import 'dart:io';

import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:korean_math_app/features/chat/application/chat_controller.dart';
import 'package:korean_math_app/features/chat/data/coach_api.dart';
import 'package:korean_math_app/features/chat/data/coach_models.dart';

/// 미리 짠 응답을 돌려주며 보낸 요청을 캡처하는 fake(chat_controller_test.dart 답습·최소화).
///
/// 이 테스트는 세그멘테이션(줄 분해)만 검증하므로 코치 결정 내용 자체는 관심사가 아니다 —
/// 고정된 최소 결정을 반환하고 [lastRequest]로 실제 전송된 solution_steps만 캡처한다.
class _FakeCoachApi extends CoachApi {
  _FakeCoachApi() : super(Dio());

  CoachRequest? lastRequest;

  static const CoachResponse _fixedResponse = CoachResponse(
    decision: PedagogyDecision(
      polyaStageToAdvance: 'stay',
      prompt: '(세그멘테이션 계약 테스트용 고정 응답)',
      system: '(테스트)',
    ),
  );

  @override
  Future<CoachTurnResult> createSession(
    CoachRequest request, {
    String? problemId,
  }) async {
    lastRequest = request;
    return const CoachTurnResult(
      dialogueId: 'segmentation-contract-test',
      response: _fixedResponse,
      wh1TurnIndex: 1,
    );
  }

  @override
  Future<CoachTurnResult> addTurn(
    String dialogueId,
    CoachRequest request,
  ) async {
    lastRequest = request;
    // `dialogueId`가 런타임 인자라 const 불가(고립본은 const로 적혀 있었다 — 그 브랜치는
    // 열린 PR이 없어 flutter analyze를 통과한 적이 없다. NLP-04 회수 시 정정).
    return CoachTurnResult(
      dialogueId: dialogueId,
      response: _fixedResponse,
      wh1TurnIndex: 2,
    );
  }
}

/// 케이스마다 격리된 신선한 컨테이너 + 노티파이어 + fake(요청 캡처용)를 만든다.
({ProviderContainer container, ChatController notifier, _FakeCoachApi fake})
    _fresh() {
  final _FakeCoachApi fake = _FakeCoachApi();
  final ProviderContainer container = ProviderContainer(
    overrides: [coachApiProvider.overrideWithValue(fake)],
  );
  addTearDown(container.dispose);
  return (
    container: container,
    notifier: container.read(chatControllerProvider.notifier),
    fake: fake,
  );
}

/// 계약 JSON을 리포 루트 기준(`data/segmentation_contract.json`)으로 로드한다.
///
/// `flutter test`는 cwd=`src/mobile`로 실행되므로(governance 테스트 선례) 상대경로는
/// `../../data/segmentation_contract.json`이다. 조용한 skip 대신 명확한 에러로 실패시킨다
/// (CLAUDE.md "검증 없는 실행 안내 금지"의 테스트판 — 파일을 못 찾으면 왜 못 찾았는지 즉시 드러나야 한다).
Map<String, dynamic> _loadContract() {
  const String relPath = '../../data/segmentation_contract.json';
  final File file = File(relPath);
  if (!file.existsSync()) {
    fail(
      '세그멘테이션 계약 파일을 찾지 못했습니다: ${file.absolute.path}\n'
      '(flutter test의 cwd는 src/mobile이어야 합니다 — 리포 루트에서 '
      '`cd src/mobile && flutter test test/segmentation_contract_test.dart`로 실행하세요.)',
    );
  }
  return jsonDecode(file.readAsStringSync()) as Map<String, dynamic>;
}

void main() {
  final Map<String, dynamic> contract = _loadContract();
  final List<dynamic> cases = contract['cases'] as List<dynamic>;

  group('세그멘테이션 골든 계약 (data/segmentation_contract.json ↔ 모바일 미러)', () {
    for (final dynamic raw in cases) {
      final Map<String, dynamic> testCase = raw as Map<String, dynamic>;
      final String id = testCase['id'] as String;
      final String input = testCase['input'] as String;
      final List<String> expectedSteps = (testCase['steps'] as List<dynamic>)
          .cast<String>();
      final bool isDisplaylines = input.contains(r'\displaylines');

      test('$id — ${isDisplaylines ? "displaylines→sendMathLiveSolution" : "평문→sendSolution"}', () async {
        final result = _fresh();

        if (isDisplaylines) {
          // displaylines 경로: latexToPlainSolution(언랩) → sendSolution(내부 _splitSteps) 순서를
          // 실제 프로덕션 호출 순서 그대로 거친다(sendMathLiveSolution 정의 그대로).
          await result.notifier.sendMathLiveSolution(input);
        } else {
          // 평문 경로: _splitSteps만 직접 거친다.
          await result.notifier.sendSolution(input);
        }

        if (expectedSteps.isEmpty) {
          // 유효한 줄이 하나도 없으면 sendSolution/sendMathLiveSolution 둘 다 전송을 생략한다
          // (컨트롤러의 "보낼 게 없으면 무시" 가드) — 요청이 아예 안 나간 것을 빈 steps의 증거로 삼는다.
          expect(
            result.fake.lastRequest,
            isNull,
            reason: '[$id] steps=[] 기대인데 요청이 전송됐습니다(전송 가드 미작동 의심)',
          );
        } else {
          expect(
            result.fake.lastRequest,
            isNotNull,
            reason: '[$id] steps=$expectedSteps 기대인데 요청이 전송되지 않았습니다',
          );
          expect(
            result.fake.lastRequest!.solutionSteps,
            expectedSteps,
            reason: '[$id] 분해된 solution_steps가 계약과 불일치',
          );
        }
      });
    }
  });
}
