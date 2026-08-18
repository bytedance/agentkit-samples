import test from "node:test";
import assert from "node:assert/strict";
import { BridgeSession, type BridgeEvent } from "../src/bridge.ts";
import {
  CodexAppServerClient,
  type ClientOptions,
  type WebSocketLike,
} from "../src/client.ts";

class FakeWebSocket extends EventTarget {
  readyState = 0;
  readonly sent: Array<Record<string, unknown>> = [];
  onClientMessage?: (message: Record<string, unknown>) => void;

  open(): void {
    this.readyState = 1;
    this.dispatchEvent(new Event("open"));
  }

  send(data: string): void {
    const message = JSON.parse(data) as Record<string, unknown>;
    this.sent.push(message);
    this.onClientMessage?.(message);
  }

  serverSend(message: Record<string, unknown>): void {
    this.dispatchEvent(new MessageEvent("message", { data: JSON.stringify(message) }));
  }

  close(): void {
    if (this.readyState === 3) return;
    this.readyState = 3;
    this.dispatchEvent(new Event("close"));
  }
}

function sessionWithSocket(socket: FakeWebSocket): BridgeSession {
  return new BridgeSession({
    sandboxUrl: "https://sandbox.example/?Authorization=secret",
    requestTimeoutMs: 1_000,
    clientFactory: (url: string, options: ClientOptions) =>
      new CodexAppServerClient(url, {
        ...options,
        webSocketFactory: () => socket as unknown as WebSocketLike,
      }),
  });
}

function respondToSetup(socket: FakeWebSocket): void {
  socket.onClientMessage = (message) => {
    if (message.method === "initialize") {
      socket.serverSend({ id: message.id, result: {} });
    } else if (message.method === "thread/start") {
      socket.serverSend({ id: message.id, result: { thread: { id: "thread-1" } } });
    }
  };
}

test("bridge defaults turn timeout to one hour", () => {
  const socket = new FakeWebSocket();
  let clientOptions: ClientOptions | undefined;
  const session = new BridgeSession({
    sandboxUrl: "https://sandbox.example/?Authorization=secret",
    clientFactory: (url, options) => {
      clientOptions = options;
      return new CodexAppServerClient(url, {
        ...options,
        webSocketFactory: () => socket as unknown as WebSocketLike,
      });
    },
  });

  assert.equal(clientOptions?.requestTimeoutMs, 300_000);
  assert.equal(clientOptions?.turnTimeoutMs, 3_600_000);
  session.close();
});

test("bridge isolates failed subscribers and replays ordered history", async () => {
  const socket = new FakeWebSocket();
  respondToSetup(socket);
  const session = sessionWithSocket(socket);
  session.subscribe(() => {
    throw new Error("subscriber failed");
  });
  const connected = session.connect();
  socket.open();
  await connected;
  session.emit({ type: "notification", method: "hook/started", params: {} });

  const replay: Array<{ event: BridgeEvent; id: number }> = [];
  session.subscribe((event, id) => replay.push({ event, id }));
  assert.deepEqual(replay.map(({ id }) => id), [1, 2]);
  assert.deepEqual(replay.map(({ event }) => event.type), ["ready", "notification"]);
  session.close();
});

test("bridge reports a remote close to browser subscribers", async () => {
  const socket = new FakeWebSocket();
  respondToSetup(socket);
  const session = sessionWithSocket(socket);
  const events: BridgeEvent[] = [];
  session.subscribe((event) => events.push(event));
  const connected = session.connect();
  socket.open();
  await connected;

  socket.close();
  await new Promise((resolve) => setImmediate(resolve));

  assert.deepEqual(events.at(-1), {
    type: "closed",
    reason: "app-server WebSocket connection closed",
  });
});

test("bridge carries workspace settings into new threads and persists session permissions", async () => {
  const socket = new FakeWebSocket();
  let threadNumber = 0;
  socket.onClientMessage = (message) => {
    if (message.method === "initialize") {
      socket.serverSend({ id: message.id, result: {} });
    } else if (message.method === "thread/start") {
      threadNumber += 1;
      socket.serverSend({
        id: message.id,
        result: {
          thread: { id: `thread-${threadNumber}` },
          cwd: threadNumber === 1 ? "/" : "/workspace",
        },
      });
    } else if (message.method === "thread/settings/update") {
      socket.serverSend({ id: message.id, result: {} });
    } else if (message.method === "config/read") {
      socket.serverSend({
        id: message.id,
        result: {
          config: {},
          origins: {},
          layers: [{
            name: { type: "user", file: "/root/.codex/config.toml", profile: null },
            version: "sha256:bridge",
            config: {},
          }],
        },
      });
    } else if (message.method === "config/batchWrite") {
      socket.serverSend({
        id: message.id,
        result: {
          status: "ok",
          version: "sha256:updated",
          filePath: "/root/.codex/config.toml",
          overriddenMetadata: null,
        },
      });
    }
  };
  const session = sessionWithSocket(socket);
  const connected = session.connect();
  socket.open();
  await connected;

  await session.updateWorkspaceDirectory("/workspace");
  await session.updateSessionPermissions({
    approvalPolicy: "never",
    approvalsReviewer: "auto_review",
    sandboxMode: "workspace-write",
    networkAccess: true,
  });
  const snapshot = await session.newThread();

  assert.equal(snapshot.thread.id, "thread-2");
  assert.deepEqual(
    socket.sent.filter((message) => message.method === "thread/start").at(-1)?.params,
    {
      cwd: "/workspace",
    },
  );
  assert.deepEqual(
    socket.sent.find((message) => (
      message.method === "thread/settings/update" &&
      (message.params as Record<string, unknown>).cwd === "/workspace"
    ))?.params,
    {
      threadId: "thread-1",
      cwd: "/workspace",
    },
  );
  assert.deepEqual(
    socket.sent.filter((message) => (
      message.method === "thread/settings/update" &&
      (message.params as Record<string, unknown>).approvalPolicy === "never"
    )).map((message) => message.params),
    [
      {
        threadId: "thread-1",
        approvalPolicy: "never",
        approvalsReviewer: "auto_review",
        sandboxPolicy: {
          type: "workspaceWrite",
          writableRoots: ["/workspace"],
          networkAccess: true,
          excludeTmpdirEnvVar: false,
          excludeSlashTmp: false,
        },
      },
      {
        threadId: "thread-2",
        approvalPolicy: "never",
        approvalsReviewer: "auto_review",
        sandboxPolicy: {
          type: "workspaceWrite",
          writableRoots: ["/workspace"],
          networkAccess: true,
          excludeTmpdirEnvVar: false,
          excludeSlashTmp: false,
        },
      },
    ],
  );
  assert.equal(
    socket.sent.some((message) => message.method === "config/batchWrite"),
    true,
  );
  session.close();
});

test("bridge locks the workspace as soon as the first turn starts", async () => {
  const socket = new FakeWebSocket();
  socket.onClientMessage = (message) => {
    if (message.method === "initialize") {
      socket.serverSend({ id: message.id, result: {} });
    } else if (message.method === "thread/start") {
      socket.serverSend({
        id: message.id,
        result: { thread: { id: "thread-lock" }, cwd: "/" },
      });
    } else if (message.method === "turn/start") {
      socket.serverSend({
        id: message.id,
        result: { turn: { id: "turn-lock", status: "inProgress", items: [] } },
      });
    }
  };
  const session = sessionWithSocket(socket);
  const connected = session.connect();
  socket.open();
  await connected;

  assert.equal(session.workspaceLocked, false);
  await session.startTurn("begin");
  assert.equal(session.workspaceLocked, true);
  await assert.rejects(
    session.updateWorkspaceDirectory("/other"),
    /cannot change workspace after the thread has started/,
  );
  session.close();
});

test("bridge history enforces a byte budget without dropping live events", async () => {
  const socket = new FakeWebSocket();
  respondToSetup(socket);
  const session = sessionWithSocket(socket);
  const liveIds: number[] = [];
  session.subscribe((_event, id) => liveIds.push(id));
  const connected = session.connect();
  socket.open();
  await connected;
  session.emit({
    type: "notification",
    method: "oversized/test",
    params: { value: "x".repeat(2 * 1024 * 1024) },
  });
  session.emit({ type: "notification", method: "small/test", params: {} });

  const replayIds: number[] = [];
  session.subscribe((_event, id) => replayIds.push(id));
  assert.deepEqual(liveIds, [1, 2, 3]);
  assert.deepEqual(replayIds, [1, 3]);
  session.close();
});

test("bridge prevents concurrent turns and can interrupt before start resolves", async () => {
  const socket = new FakeWebSocket();
  let turnStartRequest: Record<string, unknown> | undefined;
  respondToSetup(socket);
  const setupHandler = socket.onClientMessage;
  socket.onClientMessage = (message) => {
    setupHandler?.(message);
    if (message.method === "turn/start") turnStartRequest = message;
    if (message.method === "turn/interrupt") {
      socket.serverSend({ id: message.id, result: {} });
    }
  };
  const session = sessionWithSocket(socket);
  const connected = session.connect();
  socket.open();
  await connected;

  await session.startTurn("first");
  await assert.rejects(session.startTurn("second"), /already running/);
  const interrupted = session.interrupt();
  assert.ok(turnStartRequest);
  socket.serverSend({ id: turnStartRequest.id, result: { turn: { id: "turn-1" } } });
  await interrupted;

  assert.equal(socket.sent.some((message) => message.method === "turn/interrupt"), true);
  session.close();
});

test("bridge keeps Skill paths private and binds selected Skills to turn input", async () => {
  const socket = new FakeWebSocket();
  let turnStartParams: unknown;
  let skillListRequests = 0;
  socket.onClientMessage = (message) => {
    if (message.method === "initialize") {
      socket.serverSend({ id: message.id, result: {} });
    } else if (message.method === "thread/start") {
      socket.serverSend({
        id: message.id,
        result: {
          thread: { id: "thread-1", turns: [] },
          cwd: "/workspace",
        },
      });
    } else if (message.method === "skills/list") {
      skillListRequests += 1;
      socket.serverSend({
        id: message.id,
        result: {
          data: [{
            cwd: "/workspace",
            skills: [
              {
                name: "review",
                description: "Review changes",
                path: "/workspace/.agents/skills/review/SKILL.md",
                enabled: true,
              },
              {
                name: "release",
                description: "Prepare a release",
                path: "/workspace/.agents/skills/release/SKILL.md",
                enabled: true,
              },
            ],
            errors: [],
          }],
        },
      });
    } else if (message.method === "turn/start") {
      turnStartParams = message.params;
      socket.serverSend({ id: message.id, result: { turn: { id: "turn-skill" } } });
      queueMicrotask(() => {
        socket.serverSend({
          method: "turn/completed",
          params: {
            threadId: "thread-1",
            turn: { id: "turn-skill", status: "completed", error: null },
          },
        });
      });
    }
  };

  const session = sessionWithSocket(socket);
  const connected = session.connect();
  socket.open();
  await connected;

  const skills = await session.listSkills();
  assert.equal(skills.length, 2);
  assert.equal(typeof skills[0]?.id, "string");
  assert.deepEqual(
    skills.map(({ name, description }) => ({ name, description })),
    [
      { name: "review", description: "Review changes" },
      { name: "release", description: "Prepare a release" },
    ],
  );
  assert.equal(JSON.stringify(skills).includes("/workspace"), false);
  socket.serverSend({ method: "skills/changed", params: {} });
  assert.deepEqual(await session.listSkills(), skills);
  assert.equal(skillListRequests, 2);

  const review = skills.find((skill) => skill.name === "review")!;
  const release = skills.find((skill) => skill.name === "release")!;
  await assert.rejects(
    session.startTurn("plain prompt", [review.id]),
    /first item in the prompt/,
  );
  await assert.rejects(
    session.startTurn("please use $review", [review.id]),
    /first item in the prompt/,
  );
  await assert.rejects(
    session.startTurn("$release then use $review", [review.id]),
    /match the leading Skill markers/,
  );
  await assert.rejects(
    session.startTurn("$review $release inspect this change", [review.id]),
    /match the leading Skill markers/,
  );
  await session.startTurn(
    "$review $release inspect this change and leave $review in the text",
    [release.id, review.id],
  );

  assert.deepEqual(turnStartParams, {
    threadId: "thread-1",
    input: [
      {
        type: "text",
        text: "$review $release inspect this change and leave $review in the text",
      },
      {
        type: "skill",
        name: "review",
        path: "/workspace/.agents/skills/review/SKILL.md",
      },
      {
        type: "skill",
        name: "release",
        path: "/workspace/.agents/skills/release/SKILL.md",
      },
    ],
  });
  session.close();
});

test("bridge converts cumulative token notifications into per-turn usage", async () => {
  const socket = new FakeWebSocket();
  respondToSetup(socket);
  const setupHandler = socket.onClientMessage;
  socket.onClientMessage = (message) => {
    setupHandler?.(message);
    if (message.method !== "turn/start") return;
    socket.serverSend({ id: message.id, result: { turn: { id: "turn-usage" } } });
    queueMicrotask(() => {
      socket.serverSend(tokenUsageNotification({
        totalTokens: 100,
        inputTokens: 70,
        cachedInputTokens: 20,
        outputTokens: 30,
        reasoningOutputTokens: 10,
      }));
      socket.serverSend(tokenUsageNotification({
        totalTokens: 170,
        inputTokens: 120,
        cachedInputTokens: 30,
        outputTokens: 50,
        reasoningOutputTokens: 15,
      }));
      socket.serverSend({
        method: "turn/completed",
        params: {
          threadId: "thread-1",
          turn: { id: "turn-usage", status: "completed", error: null },
        },
      });
    });
  };
  const session = sessionWithSocket(socket);
  const events: BridgeEvent[] = [];
  const completed = new Promise<void>((resolve) => {
    session.subscribe((event) => {
      events.push(event);
      if (event.type === "turn_completed") resolve();
    });
  });
  const connected = session.connect();
  socket.open();
  await connected;
  const requestId = await session.startTurn("measure this");
  await completed;

  const usageEvents = events.filter(
    (event): event is Extract<BridgeEvent, { type: "token_usage" }> =>
      event.type === "token_usage",
  );
  assert.equal(usageEvents.length, 2);
  assert.deepEqual(usageEvents.at(-1), {
    type: "token_usage",
    requestId,
    turnId: "turn-usage",
    usage: {
      totalTokens: 170,
      inputTokens: 120,
      cachedInputTokens: 30,
      outputTokens: 50,
      reasoningOutputTokens: 15,
    },
    threadTotal: {
      totalTokens: 170,
      inputTokens: 120,
      cachedInputTokens: 30,
      outputTokens: 50,
      reasoningOutputTokens: 15,
    },
    modelContextWindow: 200_000,
  });
  session.close();
});

test("bridge exposes bounded execution steps without raw reasoning", async () => {
  const socket = new FakeWebSocket();
  respondToSetup(socket);
  const setupHandler = socket.onClientMessage;
  socket.onClientMessage = (message) => {
    setupHandler?.(message);
    if (message.method !== "turn/start") return;
    socket.serverSend({ id: message.id, result: { turn: { id: "turn-execution" } } });
    queueMicrotask(() => {
      socket.serverSend({
        method: "item/started",
        params: {
          threadId: "thread-1",
          turnId: "turn-execution",
          item: {
            type: "commandExecution",
            id: "command-1",
            command: "uname -a",
            cwd: "/workspace",
            status: "inProgress",
          },
        },
      });
      socket.serverSend({
        method: "item/completed",
        params: {
          threadId: "thread-1",
          turnId: "turn-execution",
          item: {
            type: "commandExecution",
            id: "command-1",
            command: "uname -a",
            cwd: "/workspace",
            status: "completed",
            aggregatedOutput: "large output is intentionally not forwarded",
            durationMs: 120,
          },
        },
      });
      socket.serverSend({
        method: "item/completed",
        params: {
          threadId: "thread-1",
          turnId: "turn-execution",
          item: {
            type: "reasoning",
            id: "reasoning-1",
            summary: ["Checking the operating system"],
            content: ["private raw chain of thought"],
          },
        },
      });
      socket.serverSend({
        method: "turn/completed",
        params: {
          threadId: "thread-1",
          turn: { id: "turn-execution", status: "completed", error: null },
        },
      });
    });
  };
  const session = sessionWithSocket(socket);
  const events: BridgeEvent[] = [];
  const completed = new Promise<void>((resolve) => {
    session.subscribe((event) => {
      events.push(event);
      if (event.type === "turn_completed") resolve();
    });
  });
  const connected = session.connect();
  socket.open();
  await connected;
  const requestId = await session.startTurn("inspect the environment");
  await completed;

  const updates = events.filter(
    (event): event is Extract<BridgeEvent, { type: "execution_update" }> =>
      event.type === "execution_update",
  );
  assert.equal(updates.length, 3);
  assert.deepEqual(updates[0], {
    type: "execution_update",
    requestId,
    turnId: "turn-execution",
    step: {
      id: "command-1",
      kind: "command",
      title: "运行命令",
      status: "running",
      detail: "$ uname -a\n目录：/workspace",
    },
  });
  assert.equal(updates[1]?.step.status, "completed");
  assert.equal(updates[1]?.step.durationMs, 120);
  assert.equal(updates[1]?.step.detail?.includes("large output"), false);
  assert.equal(updates[2]?.step.detail, "Checking the operating system");
  assert.equal(JSON.stringify(updates).includes("private raw chain of thought"), false);
  assert.equal(
    events.some((event) => event.type === "notification" && event.method.startsWith("item/")),
    false,
  );
  session.close();
});

test("bridge lists and switches persisted threads with restored history", async () => {
  const socket = new FakeWebSocket();
  respondToSetup(socket);
  const setupHandler = socket.onClientMessage;
  socket.onClientMessage = (message) => {
    setupHandler?.(message);
    if (message.method === "thread/list") {
      socket.serverSend({
        id: message.id,
        result: { data: [{ id: "thread-2", preview: "history", updatedAt: 2 }], nextCursor: null },
      });
    } else if (message.method === "thread/resume") {
      socket.serverSend({
        id: message.id,
        result: {
          thread: {
            id: "thread-2",
            preview: "history",
            turns: [{
              id: "turn-2",
              startedAt: 2,
              items: [
                { type: "userMessage", id: "user-2", content: [{ type: "text", text: "history" }] },
                { type: "agentMessage", id: "agent-2", text: "restored" },
              ],
            }],
          },
          model: "gpt-test",
          cwd: "/workspace",
        },
      });
    }
  };
  const session = sessionWithSocket(socket);
  const events: BridgeEvent[] = [];
  session.subscribe((event) => events.push(event));
  const connected = session.connect();
  socket.open();
  await connected;

  assert.deepEqual((await session.listThreads()).data.map((thread) => thread.id), ["thread-2"]);
  const snapshot = await session.switchThread("thread-2");

  assert.equal(snapshot.thread.id, "thread-2");
  assert.deepEqual(snapshot.messages.map((message) => message.content), ["history", "restored"]);
  assert.deepEqual(events.at(-1), {
    type: "thread_changed",
    threadId: "thread-2",
    messages: snapshot.messages,
    model: "gpt-test",
    cwd: "/workspace",
  });
  session.close();
});

function tokenUsageNotification(total: {
  totalTokens: number;
  inputTokens: number;
  cachedInputTokens: number;
  outputTokens: number;
  reasoningOutputTokens: number;
}): Record<string, unknown> {
  return {
    method: "thread/tokenUsage/updated",
    params: {
      threadId: "thread-1",
      turnId: "turn-usage",
      tokenUsage: {
        total,
        last: total,
        modelContextWindow: 200_000,
      },
    },
  };
}
