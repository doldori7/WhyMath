// ====== window.storage shim (localStorage 기반) ======
// 원본 그래프 계산기는 claude.ai 아티팩트 전용 *비동기* 저장 API(window.storage)를 사용한다.
// 실제 브라우저/WebView엔 이 API가 없으므로 localStorage로 동일 인터페이스를 재현한다.
//
// 계약(원본 호출부 실측):
//   get(key)        → Promise<{ value: string | null }>   // 미존재 시 value=null
//   set(key, value) → Promise<void>
//   delete(key)     → Promise<void>
//   list(prefix)    → Promise<{ keys: string[] }>
//
// 컴포넌트 본문은 한 줄도 고치지 않는다 — main.jsx에서 installStorageShim()으로 window.storage에
// 주입하면 기존 `await window.storage.*` 호출이 그대로 동작한다(전부 try/catch로 감싸져 있어 안전).

const get = async (key) => {
  try {
    return { value: window.localStorage.getItem(key) }; // 미존재 시 value=null (원본은 res?.value 접근)
  } catch {
    return { value: null };
  }
};

const set = async (key, value) => {
  try {
    window.localStorage.setItem(key, String(value));
  } catch {
    /* 저장 불가 환경(시크릿 모드 등)이면 조용히 무시 — 메모리 상태는 유지됨 */
  }
};

// delete는 JS 예약어라 내부 함수명은 del, 객체 키만 delete로 매핑한다.
const del = async (key) => {
  try {
    window.localStorage.removeItem(key);
  } catch {
    /* 무시 */
  }
};

const list = async (prefix = "") => {
  const keys = [];
  try {
    for (let i = 0; i < window.localStorage.length; i++) {
      const k = window.localStorage.key(i);
      if (k && k.startsWith(prefix)) keys.push(k);
    }
  } catch {
    /* 무시 */
  }
  return { keys };
};

export const storageShim = { get, set, delete: del, list };

// window.storage가 이미 있으면(실제 claude.ai 환경 등) 덮어쓰지 않는다.
export function installStorageShim() {
  if (typeof window === "undefined") return undefined;
  if (!window.storage) window.storage = storageShim;
  return window.storage;
}
