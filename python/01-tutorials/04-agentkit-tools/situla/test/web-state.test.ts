import test from "node:test";
import assert from "node:assert/strict";
import {
  applyDelta,
  applyExecutionUpdate,
  applyTokenUsage,
  applyTurnCompleted,
  applyTurnStarted,
  failStreamingMessages,
} from "../web/src/event-state.ts";
import type { ChatMessage } from "../web/src/types.ts";

test("turn event helpers tolerate replay and missing start events", () => {
  const started = { type: "turn_started" as const, requestId: "request-1" };
  const initial = applyTurnStarted([], started, 100);
  assert.strictEqual(applyTurnStarted(initial, started, 200), initial);

  const completedWithoutStart = applyTurnCompleted(
    [],
    {
      type: "turn_completed",
      requestId: "request-2",
      turnId: "turn-2",
      status: "completed",
      text: "fallback answer",
    },
    300,
  );
  assert.deepEqual(completedWithoutStart, [
    {
      id: "request-2",
      role: "assistant",
      content: "fallback answer",
      state: "complete",
      timestamp: 300,
      turnId: "turn-2",
    },
  ]);
});

test("token usage attaches to an answer before or after completion", () => {
  const started = applyTurnStarted(
    [],
    { type: "turn_started", requestId: "request-1" },
    100,
  );
  const withUsage = applyTokenUsage(started, {
    type: "token_usage",
    requestId: "request-1",
    turnId: "turn-1",
    usage: {
      totalTokens: 170,
      inputTokens: 120,
      cachedInputTokens: 30,
      outputTokens: 50,
      reasoningOutputTokens: 15,
    },
    threadTotal: {
      totalTokens: 470,
      inputTokens: 350,
      cachedInputTokens: 90,
      outputTokens: 120,
      reasoningOutputTokens: 35,
    },
    modelContextWindow: 200_000,
  });
  const completed = applyTurnCompleted(withUsage, {
    type: "turn_completed",
    requestId: "request-1",
    turnId: "turn-1",
    status: "completed",
    text: "answer",
  });

  assert.equal(completed[0]?.state, "complete");
  assert.equal(completed[0]?.turnId, "turn-1");
  assert.equal(completed[0]?.tokenUsage?.turn.totalTokens, 170);
  assert.equal(completed[0]?.tokenUsage?.threadTotal.totalTokens, 470);
});

test("execution updates attach in order and replace lifecycle state", () => {
  const started = applyTurnStarted(
    [],
    { type: "turn_started", requestId: "request-1" },
    100,
  );
  const running = applyExecutionUpdate(started, {
    type: "execution_update",
    requestId: "request-1",
    turnId: "turn-1",
    step: {
      id: "command-1",
      kind: "command",
      title: "运行命令",
      status: "running",
      detail: "$ pwd",
    },
  });
  const withSecondStep = applyExecutionUpdate(running, {
    type: "execution_update",
    requestId: "request-1",
    turnId: "turn-1",
    step: {
      id: "web-1",
      kind: "web",
      title: "网页搜索",
      status: "completed",
      detail: "Codex app server",
    },
  });
  const completed = applyExecutionUpdate(withSecondStep, {
    type: "execution_update",
    requestId: "request-1",
    turnId: "turn-1",
    step: {
      id: "command-1",
      kind: "command",
      title: "运行命令",
      status: "completed",
      detail: "$ pwd",
      durationMs: 80,
    },
  });

  assert.deepEqual(completed[0]?.execution?.map((step) => step.id), ["command-1", "web-1"]);
  assert.equal(completed[0]?.execution?.[0]?.status, "completed");
  assert.equal(completed[0]?.execution?.[0]?.durationMs, 80);
  assert.equal(completed[0]?.turnId, "turn-1");
});

test("delta helper creates a missing stream and ignores late deltas", () => {
  const streamed = applyDelta(
    [],
    { type: "delta", requestId: "request-1", delta: "hello" },
    100,
  );
  assert.equal(streamed[0]?.content, "hello");

  const completed: ChatMessage[] = [{ ...streamed[0], state: "complete" }];
  assert.strictEqual(
    applyDelta(completed, { type: "delta", requestId: "request-1", delta: " duplicate" }),
    completed,
  );
});

test("completion replaces a partial replay with authoritative final text", () => {
  const partial: ChatMessage[] = [
    {
      id: "request-1",
      role: "assistant",
      content: "tail only",
      state: "streaming",
      timestamp: 100,
    },
  ];
  const completed = applyTurnCompleted(partial, {
    type: "turn_completed",
    requestId: "request-1",
    turnId: "turn-1",
    status: "completed",
    text: "the complete answer, including tail only",
  });
  assert.equal(completed[0]?.content, "the complete answer, including tail only");
});

test("remote close marks an unfinished assistant message as incomplete", () => {
  const messages: ChatMessage[] = [
    {
      id: "request-1",
      role: "assistant",
      content: "partial",
      state: "streaming",
      timestamp: 100,
    },
  ];
  assert.deepEqual(failStreamingMessages(messages), [
    {
      ...messages[0],
      content: "partial\n\n连接已中断，回复可能不完整。",
      state: "error",
    },
  ]);
});
