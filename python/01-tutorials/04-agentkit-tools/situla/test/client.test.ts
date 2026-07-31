import test from "node:test";
import assert from "node:assert/strict";
import {
  CodexAppServerClient,
  type ApprovalDecision,
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
    this.dispatchEvent(
      new MessageEvent("message", { data: JSON.stringify(message) }),
    );
  }

  close(): void {
    if (this.readyState === 3) return;
    this.readyState = 3;
    this.dispatchEvent(new Event("close"));
  }
}

function createClient(
  socket: FakeWebSocket,
  extra: ConstructorParameters<typeof CodexAppServerClient>[1] = {},
): CodexAppServerClient {
  return new CodexAppServerClient("https://sandbox.example/?Authorization=secret", {
    requestTimeoutMs: 1_000,
    turnTimeoutMs: 1_000,
    ...extra,
    webSocketFactory: () => socket as unknown as WebSocketLike,
  });
}

test("initializes, starts a thread, and streams a completed turn", async () => {
  const socket = new FakeWebSocket();
  socket.onClientMessage = (message) => {
    if (message.method === "initialize") {
      socket.serverSend({ id: message.id, result: { userAgent: "test" } });
    } else if (message.method === "thread/start") {
      socket.serverSend({ id: message.id, result: { thread: { id: "thread-1" } } });
    } else if (message.method === "turn/start") {
      socket.serverSend({ id: message.id, result: { turn: { id: "turn-1" } } });
      queueMicrotask(() => {
        socket.serverSend({
          method: "item/agentMessage/delta",
          params: { threadId: "thread-1", turnId: "turn-1", itemId: "item-1", delta: "hello" },
        });
        socket.serverSend({
          method: "item/agentMessage/delta",
          params: { threadId: "thread-1", turnId: "turn-1", itemId: "item-1", delta: " world" },
        });
        socket.serverSend({
          method: "turn/completed",
          params: { threadId: "thread-1", turn: { id: "turn-1", status: "completed", error: null } },
        });
      });
    }
  };

  const client = createClient(socket);
  const connected = client.connect();
  socket.open();
  await connected;
  assert.equal(await client.startThread(), "thread-1");
  const chunks: string[] = [];
  const result = await client.runTurn("hi", (delta) => chunks.push(delta));

  assert.deepEqual(result, {
    turnId: "turn-1",
    status: "completed",
    text: "hello world",
  });
  assert.deepEqual(chunks, ["hello", " world"]);
  assert.deepEqual(socket.sent[0]?.params, {
    clientInfo: {
      name: "agentkit_codex_app_server_client",
      title: "AgentKit Codex App Server Client",
      version: "0.1.0",
    },
    capabilities: { experimentalApi: true },
  });
  assert.equal(socket.sent[1]?.method, "initialized");
  client.close();
});

test("lists workspace skills and sends selected skills as structured turn input", async () => {
  const socket = new FakeWebSocket();
  let turnStartParams: unknown;
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
      socket.serverSend({
        id: message.id,
        result: {
          data: [{
            cwd: "/workspace",
            skills: [{
              name: "review",
              description: "Review changes",
              path: "/workspace/.agents/skills/review/SKILL.md",
              enabled: true,
            }],
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

  const client = createClient(socket);
  const connected = client.connect();
  socket.open();
  await connected;
  await client.startThread();
  const skills = await client.listSkills();
  await client.runTurn("$review inspect this change", undefined, undefined, skills);

  assert.deepEqual(
    socket.sent.find((message) => message.method === "skills/list")?.params,
    { cwds: ["/workspace"], forceReload: false },
  );
  assert.deepEqual(turnStartParams, {
    threadId: "thread-1",
    input: [
      { type: "text", text: "$review inspect this change" },
      {
        type: "skill",
        name: "review",
        path: "/workspace/.agents/skills/review/SKILL.md",
      },
    ],
  });
  client.close();
});

test("answers command approval requests through the configured handler", async () => {
  const socket = new FakeWebSocket();
  let approvalResponse: Record<string, unknown> | undefined;
  socket.onClientMessage = (message) => {
    if (message.method === "initialize") {
      socket.serverSend({ id: message.id, result: {} });
    } else if (message.method === "thread/start") {
      socket.serverSend({ id: message.id, result: { thread: { id: "thread-1" } } });
    } else if (message.method === "turn/start") {
      socket.serverSend({ id: message.id, result: { turn: { id: "turn-1" } } });
      queueMicrotask(() =>
        socket.serverSend({
          id: "approval-1",
          method: "item/commandExecution/requestApproval",
          params: {
            threadId: "thread-1",
            turnId: "turn-1",
            itemId: "item-1",
            startedAtMs: 1,
            environmentId: null,
            command: "pwd",
          },
        }),
      );
    } else if (message.id === "approval-1") {
      approvalResponse = message;
      socket.serverSend({
        method: "turn/completed",
        params: { threadId: "thread-1", turn: { id: "turn-1", status: "completed", error: null } },
      });
    }
  };

  const client = createClient(socket, {
    approvalHandler: async (): Promise<ApprovalDecision> => "acceptForSession",
  });
  const connected = client.connect();
  socket.open();
  await connected;
  await client.startThread();
  await client.runTurn("run pwd");

  assert.deepEqual(approvalResponse, {
    id: "approval-1",
    result: { decision: "acceptForSession" },
  });
  client.close();
});

test("uses completed agent text when no delta was emitted", async () => {
  const socket = new FakeWebSocket();
  socket.onClientMessage = (message) => {
    if (message.method === "initialize") {
      socket.serverSend({ id: message.id, result: {} });
    } else if (message.method === "thread/start") {
      socket.serverSend({ id: message.id, result: { thread: { id: "thread-1" } } });
    } else if (message.method === "turn/start") {
      socket.serverSend({ id: message.id, result: { turn: { id: "turn-1" } } });
      socket.serverSend({
        method: "item/completed",
        params: {
          threadId: "thread-1",
          turnId: "turn-1",
          item: { type: "agentMessage", text: "fallback", phase: "final_answer" },
        },
      });
      socket.serverSend({
        method: "turn/completed",
        params: { threadId: "thread-1", turn: { id: "turn-1", status: "completed", error: null } },
      });
    }
  };

  const client = createClient(socket);
  const connected = client.connect();
  socket.open();
  await connected;
  await client.startThread();
  assert.equal((await client.runTurn("hi")).text, "fallback");
  client.close();
});

test("uses authoritative completed text when streamed deltas were partial", async () => {
  const socket = new FakeWebSocket();
  socket.onClientMessage = (message) => {
    if (message.method === "initialize") {
      socket.serverSend({ id: message.id, result: {} });
    } else if (message.method === "thread/start") {
      socket.serverSend({ id: message.id, result: { thread: { id: "thread-1" } } });
    } else if (message.method === "turn/start") {
      socket.serverSend({ id: message.id, result: { turn: { id: "turn-1" } } });
      socket.serverSend({
        method: "item/agentMessage/delta",
        params: { threadId: "thread-1", turnId: "turn-1", itemId: "item-1", delta: "tail" },
      });
      socket.serverSend({
        method: "item/completed",
        params: {
          threadId: "thread-1",
          turnId: "turn-1",
          item: { type: "agentMessage", text: "complete answer including tail", phase: "final_answer" },
        },
      });
      socket.serverSend({
        method: "turn/completed",
        params: { threadId: "thread-1", turn: { id: "turn-1", status: "completed", error: null } },
      });
    }
  };

  const client = createClient(socket);
  const connected = client.connect();
  socket.open();
  await connected;
  await client.startThread();
  assert.equal((await client.runTurn("hi")).text, "complete answer including tail");
  client.close();
});

test("declines permission expansion with a valid empty turn grant", async () => {
  const socket = new FakeWebSocket();
  let permissionResponse: Record<string, unknown> | undefined;
  socket.onClientMessage = (message) => {
    if (message.method === "initialize") {
      socket.serverSend({ id: message.id, result: {} });
    } else if (message.id === "permission-1") {
      permissionResponse = message;
    }
  };

  const client = createClient(socket);
  const connected = client.connect();
  socket.open();
  await connected;
  socket.serverSend({
    id: "permission-1",
    method: "item/permissions/requestApproval",
    params: { permissions: { network: { enabled: true }, fileSystem: null } },
  });
  await new Promise((resolve) => setImmediate(resolve));

  assert.deepEqual(permissionResponse, {
    id: "permission-1",
    result: { permissions: {}, scope: "turn" },
  });
  client.close();
});

test("rejects promptly when the WebSocket closes before opening", async () => {
  const socket = new FakeWebSocket();
  let disconnects = 0;
  const client = createClient(socket, {
    connectTimeoutMs: 5_000,
    onDisconnect: () => {
      disconnects += 1;
    },
  });

  const connected = client.connect();
  socket.close();

  await assert.rejects(connected, /closed before the connection opened/);
  assert.equal(disconnects, 1);
  client.close();
});

test("isolates notification and delta callback failures", async () => {
  const socket = new FakeWebSocket();
  socket.onClientMessage = (message) => {
    if (message.method === "initialize") {
      socket.serverSend({ id: message.id, result: {} });
    } else if (message.method === "thread/start") {
      socket.serverSend({ id: message.id, result: { thread: { id: "thread-1" } } });
    } else if (message.method === "turn/start") {
      socket.serverSend({ id: message.id, result: { turn: { id: "turn-1" } } });
      queueMicrotask(() => {
        socket.serverSend({
          method: "item/agentMessage/delta",
          params: { threadId: "thread-1", turnId: "turn-1", itemId: "item-1", delta: "still works" },
        });
        socket.serverSend({
          method: "turn/completed",
          params: { threadId: "thread-1", turn: { id: "turn-1", status: "completed", error: null } },
        });
      });
    }
  };

  const client = createClient(socket);
  client.onNotification(() => {
    throw new Error("listener failed");
  });
  const connected = client.connect();
  socket.open();
  await connected;
  await client.startThread();
  const result = await client.runTurn("hi", () => {
    throw new Error("delta consumer failed");
  });

  assert.deepEqual(result, {
    turnId: "turn-1",
    status: "completed",
    text: "still works",
  });
  assert.equal(socket.readyState, 1);
  client.close();
});

test("returns invalid params for malformed server requests", async () => {
  const socket = new FakeWebSocket();
  socket.onClientMessage = (message) => {
    if (message.method === "initialize") socket.serverSend({ id: message.id, result: {} });
  };
  const client = createClient(socket);
  const connected = client.connect();
  socket.open();
  await connected;

  socket.serverSend({
    id: "bad-approval",
    method: "item/commandExecution/requestApproval",
    params: null,
  });
  await new Promise((resolve) => setImmediate(resolve));

  assert.deepEqual(socket.sent.at(-1), {
    id: "bad-approval",
    error: {
      code: -32602,
      message: "invalid params for item/commandExecution/requestApproval",
    },
  });
  client.close();
});

test("returns method not found for unknown server requests", async () => {
  const socket = new FakeWebSocket();
  socket.onClientMessage = (message) => {
    if (message.method === "initialize") socket.serverSend({ id: message.id, result: {} });
  };
  const client = createClient(socket);
  const connected = client.connect();
  socket.open();
  await connected;

  socket.serverSend({ id: "unknown-1", method: "future/dangerousAction" });
  await new Promise((resolve) => setImmediate(resolve));

  assert.deepEqual(socket.sent.at(-1), {
    id: "unknown-1",
    error: {
      code: -32601,
      message: "unsupported server request: future/dangerousAction",
    },
  });
  client.close();
});

test("closes visibly when a notification has malformed params", async () => {
  const socket = new FakeWebSocket();
  let disconnectMessage: string | undefined;
  socket.onClientMessage = (message) => {
    if (message.method === "initialize") socket.serverSend({ id: message.id, result: {} });
  };
  const client = createClient(socket, {
    onDisconnect: (error) => {
      disconnectMessage = error.message;
    },
  });
  const connected = client.connect();
  socket.open();
  await connected;

  socket.serverSend({ method: "turn/completed", params: null });

  assert.equal(socket.readyState, 3);
  assert.equal(disconnectMessage, "app-server sent invalid params for turn/completed");
});

test("does not leak a rejection when closing during an approval", async () => {
  const socket = new FakeWebSocket();
  let resolveApproval: ((decision: ApprovalDecision) => void) | undefined;
  socket.onClientMessage = (message) => {
    if (message.method === "initialize") socket.serverSend({ id: message.id, result: {} });
  };
  const client = createClient(socket, {
    approvalHandler: () =>
      new Promise((resolve) => {
        resolveApproval = resolve;
      }),
  });
  const connected = client.connect();
  socket.open();
  await connected;

  socket.serverSend({
    id: "pending-approval",
    method: "item/fileChange/requestApproval",
    params: { threadId: "thread-1", turnId: "turn-1", itemId: "item-1", startedAtMs: 1 },
  });
  await new Promise((resolve) => setImmediate(resolve));
  client.close();
  resolveApproval?.("decline");
  await new Promise((resolve) => setImmediate(resolve));

  assert.equal(socket.sent.some((message) => message.id === "pending-approval"), false);
});

test("lists, resumes, forks, archives, compacts, and configures threads", async () => {
  const socket = new FakeWebSocket();
  socket.onClientMessage = (message) => {
    const method = message.method;
    if (method === "initialize") {
      socket.serverSend({ id: message.id, result: {} });
    } else if (method === "thread/start") {
      socket.serverSend({
        id: message.id,
        result: {
          thread: { id: "thread-1", preview: "", turns: [] },
          model: "gpt-default",
          cwd: "/workspace",
          approvalPolicy: "on-request",
          approvalsReviewer: "user",
          sandbox: {
            type: "workspaceWrite",
            writableRoots: ["/workspace"],
            networkAccess: false,
            excludeTmpdirEnvVar: false,
            excludeSlashTmp: false,
          },
        },
      });
    } else if (method === "thread/list") {
      socket.serverSend({
        id: message.id,
        result: {
          data: [{ id: "thread-2", preview: "old chat", updatedAt: 20 }],
          nextCursor: "cursor-2",
        },
      });
    } else if (method === "thread/resume") {
      socket.serverSend({
        id: message.id,
        result: {
          thread: {
            id: "thread-2",
            preview: "old chat",
            updatedAt: 20,
            turns: [{
              id: "turn-old",
              startedAt: 20,
              items: [
                { type: "userMessage", id: "user-old", content: [{ type: "text", text: "old chat" }] },
                { type: "agentMessage", id: "agent-old", text: "old answer" },
              ],
            }],
          },
          model: "gpt-old",
          cwd: "/old",
        },
      });
    } else if (method === "thread/fork") {
      socket.serverSend({
        id: message.id,
        result: {
          thread: { id: "thread-3", preview: "old chat", turns: [] },
          model: "gpt-old",
          cwd: "/old",
        },
      });
    } else if (method === "model/list") {
      socket.serverSend({
        id: message.id,
        result: {
          data: [{ model: "gpt-new", displayName: "GPT New", description: "new", isDefault: true }],
          nextCursor: null,
        },
      });
    } else if (method === "fs/readDirectory") {
      socket.serverSend({
        id: message.id,
        result: {
          entries: [
            { fileName: "zeta", isDirectory: true, isFile: false },
            { fileName: "notes.txt", isDirectory: false, isFile: true },
            { fileName: "alpha", isDirectory: true, isFile: false },
          ],
        },
      });
    } else if (method === "config/read") {
      socket.serverSend({
        id: message.id,
        result: {
          config: {},
          origins: {},
          layers: [{
            name: { type: "user", file: "/root/.codex/config.toml", profile: null },
            version: "sha256:before",
            config: {},
          }],
        },
      });
    } else if (method === "turn/start") {
      socket.serverSend({ id: message.id, result: { turn: { id: "turn-settings" } } });
      queueMicrotask(() => {
        socket.serverSend({
          method: "turn/completed",
          params: {
            threadId: "thread-3",
            turn: { id: "turn-settings", status: "completed", error: null },
          },
        });
      });
    } else if (typeof method === "string" && message.id !== undefined) {
      socket.serverSend({ id: message.id, result: {} });
    }
  };

  const client = createClient(socket);
  const connected = client.connect();
  socket.open();
  await connected;
  await client.startThread();

  assert.deepEqual(await client.listThreads({ searchTerm: "old" }), {
    data: [{
      id: "thread-2",
      preview: "old chat",
      cwd: "",
      modelProvider: "",
      createdAt: 0,
      updatedAt: 20,
      status: "unknown",
    }],
    nextCursor: "cursor-2",
  });
  const resumed = await client.resumeThreadSnapshot("thread-2");
  assert.deepEqual(resumed.messages.map(({ role, content }) => ({ role, content })), [
    { role: "user", content: "old chat" },
    { role: "assistant", content: "old answer" },
  ]);
  assert.equal((await client.forkThread()).thread.id, "thread-3");
  assert.deepEqual((await client.listModels()).data, [{
    id: "gpt-new",
    displayName: "GPT New",
    description: "new",
    isDefault: true,
  }]);
  await client.setModel("gpt-new");
  assert.deepEqual(await client.listDirectories("/workspace/"), {
    path: "/workspace",
    parent: "/",
    directories: [
      { name: "alpha", path: "/workspace/alpha" },
      { name: "zeta", path: "/workspace/zeta" },
    ],
  });
  assert.deepEqual(await client.updateThreadSettings({
    cwd: "/workspace/alpha",
  }), {
    cwd: "/workspace/alpha",
    model: "gpt-new",
  });
  assert.deepEqual(await client.updateSessionPermissions({
    approvalPolicy: "never",
    approvalsReviewer: "auto_review",
    sandboxMode: "danger-full-access",
    networkAccess: true,
  }), {
    approvalPolicy: "never",
    approvalsReviewer: "auto_review",
    sandboxMode: "danger-full-access",
    networkAccess: true,
  });
  await client.runTurn("verify settings");
  await client.compactThread();
  await client.archiveThread();

  assert.equal(client.threadId, "thread-3");
  assert.equal(client.model, "gpt-new");
  assert.equal(client.cwd, "/workspace/alpha");
  assert.equal(client.sandboxMode, "danger-full-access");
  assert.equal(client.approvalPolicy, "never");
  assert.deepEqual(
    socket.sent.find((message) => message.method === "thread/list")?.params,
    {
      limit: 30,
      sortKey: "updated_at",
      sortDirection: "desc",
      archived: false,
      searchTerm: "old",
    },
  );
  assert.deepEqual(
    socket.sent.find((message) => message.method === "thread/settings/update")?.params,
    { threadId: "thread-3", model: "gpt-new" },
  );
  assert.deepEqual(
    socket.sent.find((message) => (
      message.method === "thread/settings/update" &&
      (message.params as Record<string, unknown>).cwd === "/workspace/alpha"
    ))?.params,
    {
      threadId: "thread-3",
      cwd: "/workspace/alpha",
    },
  );
  assert.deepEqual(
    socket.sent.find((message) => message.method === "config/batchWrite")?.params,
    {
      edits: [
        { keyPath: "sandbox_mode", value: "danger-full-access", mergeStrategy: "replace" },
        { keyPath: "approval_policy", value: "never", mergeStrategy: "replace" },
        { keyPath: "approvals_reviewer", value: "auto_review", mergeStrategy: "replace" },
        {
          keyPath: "sandbox_workspace_write.network_access",
          value: true,
          mergeStrategy: "replace",
        },
      ],
      expectedVersion: "sha256:before",
      reloadUserConfig: true,
    },
  );
  assert.deepEqual(
    socket.sent.find((message) => (
      message.method === "thread/settings/update" &&
      (message.params as Record<string, unknown>).approvalPolicy === "never"
    ))?.params,
    {
      threadId: "thread-3",
      approvalPolicy: "never",
      approvalsReviewer: "auto_review",
      sandboxPolicy: { type: "dangerFullAccess" },
    },
  );
  assert.deepEqual(
    socket.sent.find((message) => message.method === "turn/start")?.params,
    {
      threadId: "thread-3",
      input: [{ type: "text", text: "verify settings" }],
      approvalPolicy: "never",
      approvalsReviewer: "auto_review",
      sandboxPolicy: { type: "dangerFullAccess" },
    },
  );
  assert.equal(socket.sent.some((message) => message.method === "thread/compact/start"), true);
  assert.equal(socket.sent.some((message) => message.method === "thread/archive"), true);
  client.close();
});
