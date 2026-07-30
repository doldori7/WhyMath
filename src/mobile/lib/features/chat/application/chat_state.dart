// 채팅 화면 상태 — 메시지 목록·현재 Polya 단계·전송중·에러를 담는 불변 상태.
//
// 경계(CLAUDE.md): 순수 표현 상태다. Polya 단계 *전이 규칙*은 서버(L4)가 내린 결정
// (`decision.polyaStageToAdvance`)을 그대로 적용할 뿐, 클라가 교수학 로직을 판단하지 않는다.
import 'package:freezed_annotation/freezed_annotation.dart';

import '../domain/chat_message.dart';

part 'chat_state.freezed.dart';

/// 채팅 화면의 단일 상태 트리.
@freezed
abstract class ChatState with _$ChatState {
  const factory ChatState({
    /// 화면에 그릴 대화 누적(오래된 → 최신 순).
    @Default(<ChatMessage>[]) List<ChatMessage> messages,

    /// 현재 Polya 단계 문자열("understand"·"plan"·"execute"·"review").
    /// 백엔드 PolyaStage 진입값과 동일하게 "understand"에서 시작한다.
    @Default('understand') String polyaState,

    /// 활성 코치 세션 PK(UUID 문자열)·없으면 null. 첫 발화에서 세션을 생성해 채워지고,
    /// 이후 발화는 이 세션에 턴으로 누적된다(WH-1 턴·가설 영속·백엔드 E2E 앵커 정합).
    String? dialogueId,

    /// 코치 응답 대기 중인지(입력 잠금·로딩 인디케이터 표시).
    @Default(false) bool isSending,

    /// 마지막 호출 실패 메시지(없으면 null). 가용성을 위해 앱은 죽지 않는다.
    String? error,

    /// S3-27(원 S3-10) 완료 통합 — 이 문제가 *완료*됐는지(다음 문항 진행 신호·서버 권위).
    ///
    /// 완료는 오직 풀이 제출→정답 도달→Polya 돌아보기 1턴을 거쳐 서버가 내려주는 신호
    /// (`problem_complete`)로만 true가 된다(별도 '정답 제출' 버튼 없음). true면 화면이
    /// "다음 문제로" 어포던스를 코치 대화 흐름 안에 노출한다. 완료·정답 판정은 서버가 한다
    /// (수학 로직 클라 금지) — 클라는 이 신호를 소비만 한다.
    @Default(false) bool problemComplete,

    /// 정답 도달 후 완료 *직전 돌아보기(메타인지) 응답을 대기* 중인지(완료 아님·서버 신호).
    ///
    /// true면 코치 발화가 이미 "왜 이 답이 나왔는지" 메타인지 프롬프트라, 학생이 평소처럼
    /// 자연어로 답하면 된다 — 화면은 (선택) 작은 돌아보기 힌트만 두고 진행 어포던스는 띄우지
    /// 않는다. 완료는 그 다음 응답에서 [problemComplete]=true로 온다.
    @Default(false) bool awaitingReflection,

    /// 완료 시 서버가 적재한 ProblemAttempt PK(선택·참조용)·아니면 null.
    String? completedAttemptId,
  }) = _ChatState;
}
