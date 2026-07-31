import test from "node:test";
import assert from "node:assert/strict";
import {
  parseSlashInvocation,
  slashMenuItems,
} from "../web/src/slash-commands.ts";

const models = [
  { id: "gpt-fast", displayName: "GPT Fast", description: "quick", isDefault: false },
  { id: "gpt-default", displayName: "GPT Default", description: "default", isDefault: true },
];

test("slash command parser keeps command arguments separate", () => {
  assert.deepEqual(parseSlashInvocation(" /model gpt-fast "), {
    name: "model",
    argument: "gpt-fast",
  });
  assert.deepEqual(parseSlashInvocation("/resume thread-1"), {
    name: "resume",
    argument: "thread-1",
  });
  assert.equal(parseSlashInvocation("regular prompt"), undefined);
});

test("slash command menu filters commands and transitions to model choices", () => {
  assert.deepEqual(
    slashMenuItems("/mod", models).map((item) =>
      item.kind === "command" ? item.command.name : item.model.id),
    ["model", "models"],
  );
  assert.deepEqual(
    slashMenuItems("/model ", models).map((item) =>
      item.kind === "command" ? item.command.name : item.model.id),
    ["gpt-default", "gpt-fast"],
  );
  assert.deepEqual(
    slashMenuItems("/model fast", models).map((item) =>
      item.kind === "command" ? item.command.name : item.model.id),
    ["gpt-fast"],
  );
  assert.deepEqual(
    slashMenuItems("/ski", models).map((item) =>
      item.kind === "command" ? item.command.name : item.model.id),
    ["skills"],
  );
  assert.deepEqual(slashMenuItems("hello /model", models), []);
});
