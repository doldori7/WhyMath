// 채팅 도메인 모델 — 화면에 그릴 대화 한 줄(런타임 전용·JSON 불요).
//
// 경계(CLAUDE.md): 수학·교수학 *결정*은 서버(L4)가 내리고, 이 모델은 그 결과를
// 화면 버블로 *렌더*하기 위한 표현 컨테이너일 뿐이다(표현≠의미). coach 메시지는
// 후속 신호 렌더(소크라테스 배지·검증 단계 등)를 위해 원본 [CoachResponse]를 보관한다.
import 'package:freezed_annotation/freezed_annotation.dart';

import '../data/coach_models.dart';
import '../data/scene_models.dart';

part 'chat_message.freezed.dart';

/// 대화 화자 — 학생 입력인지 코치 발화인지.
enum ChatRole {
  /// 학생 발화(입력 필드에서 보낸 텍스트).
  student,

  /// 코치 발화(서버 결정 프롬프트·검산 코칭 등).
  coach,
}

/// 화면에 그릴 대화 한 줄.
///
/// - [role] : 학생/코치 구분(버블 정렬·색).
/// - [text] : 표시 본문(학생=입력, 코치=`decision.prompt` 등 메타인지 유도 발화).
/// - [socraticCategory] : 코치 발화의 소크라테스 카테고리 라벨(있으면 배지로 표시).
/// - [response] : 코치 발화의 원본 응답(후속 신호 시각화용 보관·없으면 null).
/// - [isSolution] : 학생 메시지가 *풀이 단계 입력*인지(대화 입력과 구분·표시 cue용).
///
/// JSON 직렬화는 두지 않는다 — 서버 계약은 [CoachRequest]/[CoachResponse]가 전담하고
/// 이 클래스는 *화면 상태*라 영속·전송 대상이 아니다(런타임 모델).
@freezed
class ChatMessage with _$ChatMessage {
  const factory ChatMessage({
    /// 화자(학생/코치).
    required ChatRole role,

    /// 표시 본문.
    required String text,

    /// 코치 발화의 소크라테스 카테고리 문자열(빈 문자열·null이면 배지 미표시).
    String? socraticCategory,

    /// 코치 발화의 원본 응답(후속 신호 렌더용·학생 메시지엔 null).
    CoachResponse? response,

    /// 약점개념 학습 장면(S5a 엔드포인트 산출물·`SceneRenderer`로 렌더·없으면 null).
    LearningScene? scene,

    /// 학생 메시지가 풀이 단계 입력인지(기본 false·대화 입력). 코치 메시지엔 의미 없음.
    @Default(false) bool isSolution,
  }) = _ChatMessage;

  const ChatMessage._();

  /// 학생 입력 한 줄을 만든다([isSolution]이면 풀이 단계 입력으로 표시).
  factory ChatMessage.student(String text, {bool isSolution = false}) =>
      ChatMessage(
        role: ChatRole.student,
        text: text,
        isSolution: isSolution,
      );

  /// 코치 발화 한 줄을 만든다(원본 응답·소크라테스 카테고리 옵션 보관).
  factory ChatMessage.coach(
    String text, {
    String? socraticCategory,
    CoachResponse? response,
  }) =>
      ChatMessage(
        role: ChatRole.coach,
        text: text,
        socraticCategory: socraticCategory,
        response: response,
      );

  /// 학습 장면 한 줄을 만든다(코치 측·텍스트 버블 없이 [SceneRenderer]로만 렌더).
  factory ChatMessage.scene(LearningScene scene) => ChatMessage(
        role: ChatRole.coach,
        text: '',
        scene: scene,
      );

  /// 코치 발화 여부(버블 분기 편의).
  bool get isCoach => role == ChatRole.coach;
}
