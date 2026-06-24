// 상호작용 이벤트 로거 — 학생의 시각화 조작을 백엔드(POST /v1/interactions)에 적재. 슬라이스 96-F.
//
// 경계(CLAUDE.md): 웹 계산기가 JS 채널로 보낸 조작 이벤트를 받아 백엔드로 전달만 한다(학습 로그
// 배관·표현≠의미). 슬라이더 드래그는 폭주하므로(onChange가 픽셀마다 발화) `type:payload.name`
// 키로 **트레일링 디바운스**해 마지막 값 1건만 보낸다(HTTP·배터리 절감). fire-and-forget —
// 전송 실패는 학습 흐름을 막지 않는다(흡수).
import 'dart:async';

import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api_client.dart';

/// 시각화 조작 이벤트를 디바운스해 `POST /v1/interactions`로 적재하는 로거.
class InteractionLogger {
  InteractionLogger(this._dio, {this.debounce = const Duration(milliseconds: 600)});

  final Dio _dio;

  /// 같은 키의 연속 이벤트를 합치는 트레일링 디바운스 창.
  final Duration debounce;

  final Map<String, Timer> _timers = {};
  final Map<String, Map<String, dynamic>> _latest = {};

  /// 조작 이벤트를 기록한다(디바운스 후 전송). 이벤트: `{type, payload, at}`.
  void record(Map<String, dynamic> event) {
    final payload = event['payload'];
    final name = (payload is Map && payload['name'] != null) ? '${payload['name']}' : '';
    final key = '${event['type']}:$name';
    _latest[key] = event;
    _timers[key]?.cancel();
    _timers[key] = Timer(debounce, () => _flush(key));
  }

  Future<void> _flush(String key) async {
    _timers.remove(key);
    final event = _latest.remove(key);
    if (event == null) return;
    try {
      await _dio.post<void>('/v1/interactions', data: event);
    } catch (_) {
      // 전송 실패는 학습 흐름을 막지 않는다(조용히 무시).
    }
  }

  /// 대기 중인 타이머를 모두 취소한다(provider dispose 시).
  void dispose() {
    for (final t in _timers.values) {
      t.cancel();
    }
    _timers.clear();
    _latest.clear();
  }
}

/// [InteractionLogger] provider — 공유 [dioProvider](base URL + 인증 인터셉터)를 주입.
final interactionLoggerProvider = Provider<InteractionLogger>((ref) {
  final logger = InteractionLogger(ref.watch(dioProvider));
  ref.onDispose(logger.dispose);
  return logger;
});
