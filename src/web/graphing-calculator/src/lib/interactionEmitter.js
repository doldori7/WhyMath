// ====== 학습 로그 아웃바운드 이미터 (L5 조작 신호 → 호스트) ======
// 학생이 임베드 계산기에서 조작한 신호(슬라이더 탐구·3D 식 변경 — 능동 탐구·메타인지 신호)를
// 호스트(Flutter WebView)로 내보낸다. 인바운드(window.whymathApplySpec)의 짝.
//
// 채널: Flutter webview_flutter가 window.WhymathInteraction(.postMessage(string)) 전역 객체를 주입한다.
// 브라우저 단독 실행(채널 없음)에선 no-op으로 false를 돌려준다 — 웹 단독 동작에 영향 0.

/**
 * 상호작용 이벤트를 호스트 채널로 방출한다.
 * @param {string} type - 이벤트 종류("param_change"·"param_play"·"surface_change"·"surface_range").
 * @param {object} [payload] - 이벤트 데이터(예: { name, value }).
 * @returns {boolean} 방출 성공 여부(채널 없거나 실패 시 false).
 */
export const emitInteraction = (type, payload) => {
  if (typeof window === "undefined") return false;
  const ch = window.WhymathInteraction;
  if (!ch || typeof ch.postMessage !== "function") return false;
  try {
    ch.postMessage(JSON.stringify({ type, payload: payload ?? {}, at: Date.now() }));
    return true;
  } catch {
    // 직렬화/전송 실패는 학습 흐름을 막지 않는다(조용히 무시).
    return false;
  }
};
