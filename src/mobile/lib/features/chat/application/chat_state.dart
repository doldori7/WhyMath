// 채팅 화면 상태 — 메시지 목록·현재 Polya 단계·전송중·에러를 담는 불변 상태.
//
// 경계(CLAUDE.md): 순수 표현 상태다. Polya 단계 *전이 규칙*은 서버(L4)가 내린 결정
// (`decision.polyaStageToAdvance`)을 그대로 적용할 뿐, 클라가 교수학 로직을 판단하지 않는다.
import 'package:freezed_annotation/freezed_annotation.dart';

import '../domain/chat_message.dart';

part 'chat_state.freezed.dart';

/// 채팅 화면의 단일 상태 트리.
@freezed
class ChatState with _$ChatState {
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
  }) = _ChatState;
}
