import test from "node:test";
import assert from "node:assert/strict";
import {
  parsePrivateRuntimeType,
  runtimeWorkspaceForToolType,
} from "../src/runtime.ts";

test("released AgentKit runtime types resolve to their workspace", () => {
  assert.equal(runtimeWorkspaceForToolType("CodeEnv"), "Codex");
  assert.equal(runtimeWorkspaceForToolType("HermesEnv"), "Hermes");
  assert.equal(runtimeWorkspaceForToolType("ArkClawEnv"), "OpenClaw");
});

test("Private Tools resolve only through a valid SITULA_PRIVATE_TYPE value", () => {
  assert.equal(runtimeWorkspaceForToolType("Private"), undefined);
  assert.equal(runtimeWorkspaceForToolType("Private", "CodeEnv"), "Codex");
  assert.equal(runtimeWorkspaceForToolType("Private", "HermesEnv"), "Hermes");
  assert.equal(runtimeWorkspaceForToolType("Private", "ArkClawEnv"), "OpenClaw");

  assert.equal(parsePrivateRuntimeType(undefined), undefined);
  assert.equal(parsePrivateRuntimeType(""), undefined);
  assert.equal(parsePrivateRuntimeType("Hermes"), undefined);
  assert.equal(parsePrivateRuntimeType("OpenClawEnv"), undefined);
  assert.equal(parsePrivateRuntimeType(" codeenv "), undefined);
  assert.equal(parsePrivateRuntimeType(" ArkClawEnv "), "ArkClawEnv");
});

test("unknown Tool types remain unsupported", () => {
  assert.equal(runtimeWorkspaceForToolType(undefined, "CodeEnv"), undefined);
  assert.equal(runtimeWorkspaceForToolType("Unknown", "CodeEnv"), undefined);
  assert.equal(runtimeWorkspaceForToolType("Hermes"), undefined);
  assert.equal(runtimeWorkspaceForToolType("OpenClaw"), undefined);
  assert.equal(runtimeWorkspaceForToolType("OpenClawEnv"), undefined);
});
