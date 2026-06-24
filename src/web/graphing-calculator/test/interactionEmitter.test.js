import { describe, it, expect, afterEach } from "vitest";
import { emitInteraction } from "../src/lib/interactionEmitter";

describe("emitInteraction — 학습 로그 아웃바운드 채널", () => {
  afterEach(() => {
    delete window.WhymathInteraction;
  });

  it("채널이 없으면 no-op으로 false", () => {
    expect(emitInteraction("param_change", { name: "a", value: 2 })).toBe(false);
  });

  it("채널이 있으면 {type,payload,at} JSON 1건을 postMessage하고 true", () => {
    const posted = [];
    window.WhymathInteraction = { postMessage: (s) => posted.push(s) };
    const ok = emitInteraction("param_change", { name: "a", value: 2 });
    expect(ok).toBe(true);
    expect(posted).toHaveLength(1);
    const evt = JSON.parse(posted[0]);
    expect(evt.type).toBe("param_change");
    expect(evt.payload).toEqual({ name: "a", value: 2 });
    expect(typeof evt.at).toBe("number");
  });

  it("payload 누락 시 빈 객체로 채운다", () => {
    let captured = null;
    window.WhymathInteraction = { postMessage: (s) => (captured = JSON.parse(s)) };
    emitInteraction("param_play");
    expect(captured.payload).toEqual({});
  });

  it("postMessage가 throw해도 흡수하고 false", () => {
    window.WhymathInteraction = {
      postMessage: () => {
        throw new Error("channel broken");
      },
    };
    expect(() => emitInteraction("surface_change", { expr: "x^2" })).not.toThrow();
    expect(emitInteraction("surface_change", { expr: "x^2" })).toBe(false);
  });
});
