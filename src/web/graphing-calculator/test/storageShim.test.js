import { describe, it, expect, beforeEach } from "vitest";
import { storageShim, installStorageShim } from "../src/lib/storageShim";

beforeEach(() => window.localStorage.clear());

describe("storageShim — localStorage 기반 window.storage 재현", () => {
  it("set → get 라운드트립", async () => {
    await storageShim.set("k", "v");
    expect((await storageShim.get("k")).value).toBe("v");
  });

  it("미존재 키 → value null", async () => {
    expect((await storageShim.get("none")).value).toBeNull();
  });

  it("delete 후 제거됨", async () => {
    await storageShim.set("k", "v");
    await storageShim.delete("k");
    expect((await storageShim.get("k")).value).toBeNull();
  });

  it("list는 prefix로 필터", async () => {
    await storageShim.set("graph:a", "1");
    await storageShim.set("graph:b", "2");
    await storageShim.set("other", "3");
    const { keys } = await storageShim.list("graph:");
    expect(keys.sort()).toEqual(["graph:a", "graph:b"]);
  });

  it("list 빈 저장소 → 빈 배열", async () => {
    expect((await storageShim.list("x")).keys).toEqual([]);
  });

  it("installStorageShim은 window.storage에 주입", () => {
    delete window.storage;
    installStorageShim();
    expect(window.storage).toBe(storageShim);
  });

  it("이미 window.storage가 있으면 덮어쓰지 않음", () => {
    const existing = { get() {}, set() {}, delete() {}, list() {} };
    window.storage = existing;
    installStorageShim();
    expect(window.storage).toBe(existing);
    delete window.storage;
  });
});
