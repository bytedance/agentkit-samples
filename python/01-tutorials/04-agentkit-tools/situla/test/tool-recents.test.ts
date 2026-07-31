import test from "node:test";
import assert from "node:assert/strict";
import {
  enqueueRecentTool,
  readRecentTools,
  refreshRecentTools,
  rememberRecentTool,
  writeRecentTools,
} from "../web/src/tool-recents.ts";

class MemoryStorage {
  readonly values = new Map<string, string>();

  getItem(key: string): string | null {
    return this.values.get(key) ?? null;
  }

  setItem(key: string, value: string): void {
    this.values.set(key, value);
  }

  removeItem(key: string): void {
    this.values.delete(key);
  }
}

test("recent Tool queue is MRU ordered, de-duplicated, and bounded to three", () => {
  const tools = [1, 2, 3, 4].map((index) => ({
    toolId: `tool-${index}`,
    name: `Tool ${index}`,
    status: "Ready",
  }));

  let queue = tools.reduce<ReturnType<typeof enqueueRecentTool>>(
    (current, tool) => enqueueRecentTool(current, tool),
    [],
  );
  assert.deepEqual(queue.map((tool) => tool.toolId), ["tool-4", "tool-3", "tool-2"]);

  queue = enqueueRecentTool(queue, { ...tools[1], name: "Tool 2 refreshed" });
  assert.deepEqual(queue.map((tool) => tool.toolId), ["tool-2", "tool-4", "tool-3"]);
  assert.equal(queue[0]?.name, "Tool 2 refreshed");
});

test("recent Tools persist public metadata and tolerate unavailable storage", () => {
  const storage = new MemoryStorage();
  storage.setItem("situla-recent-tools-v1", "not-json");
  assert.deepEqual(readRecentTools(storage, "account-a"), []);
  assert.equal(storage.getItem("situla-recent-tools-v1"), null);

  rememberRecentTool(storage, "account-a", {
    toolId: "tool-1",
    name: "Workspace",
    status: "Ready",
    toolType: "CodeEnv",
    description: "Shared sandbox",
  });
  assert.deepEqual(readRecentTools(storage, "account-a"), [{
    toolId: "tool-1",
    name: "Workspace",
    description: "Shared sandbox",
    status: "Ready",
    toolType: "CodeEnv",
  }]);
  assert.deepEqual(readRecentTools(storage, "account-b"), []);
  assert.doesNotThrow(() => writeRecentTools({
    getItem: () => null,
    setItem: () => { throw new Error("storage disabled"); },
  }, "account-a", []));
});

test("recent Tools are isolated by login account scope", () => {
  const storage = new MemoryStorage();
  rememberRecentTool(storage, "account-a", {
    toolId: "tool-a",
    name: "Account A Tool",
    status: "Ready",
  });
  rememberRecentTool(storage, "account-b", {
    toolId: "tool-b",
    name: "Account B Tool",
    status: "Ready",
  });

  assert.deepEqual(readRecentTools(storage, "account-a").map((tool) => tool.toolId), ["tool-a"]);
  assert.deepEqual(readRecentTools(storage, "account-b").map((tool) => tool.toolId), ["tool-b"]);
  assert.deepEqual(readRecentTools(storage, undefined), []);
});

test("recent Tool metadata refresh preserves queue order", () => {
  const current = [
    { toolId: "tool-2", name: "Second", status: "Ready" },
    { toolId: "tool-1", name: "Old", status: "Creating" },
  ];
  assert.deepEqual(refreshRecentTools(current, [{
    toolId: "tool-1",
    name: "Fresh",
    status: "Ready",
    description: "Updated",
  }]), [
    current[0],
    { toolId: "tool-1", name: "Fresh", status: "Ready", description: "Updated" },
  ]);
});
