import test from "node:test";
import assert from "node:assert/strict";
import { AgentkitToolsClient } from "../src/agentkit.ts";

test("AgentKit client lists every Tool type with bounded pagination metadata", async () => {
  const calls: Array<{ url: string; body: string }> = [];
  const client = new AgentkitToolsClient({
    accessKey: "AKID",
    secretKey: "SECRET",
    fetch: async (input, init) => {
      calls.push({ url: String(input), body: String(init?.body) });
      return Response.json({
        ResponseMetadata: { RequestId: "tools-page-1" },
        Result: {
          NextToken: "tools-next",
          Tools: [
            {
              ToolId: "tool-code",
              Name: "Code workspace",
              Description: "CodeEnv tool",
              Status: "Ready",
              ToolType: "CodeEnv",
              ProjectName: "default",
              CreatedAt: "2026-07-01T00:00:00Z",
              UpdatedAt: "2026-07-18T00:00:00Z",
              EnableSnapshot: true,
            },
            { ToolId: "tool-private", Status: "Creating", ToolType: "Private" },
          ],
        },
      });
    },
  });

  const page = await client.listTools();

  assert.equal(calls[0]?.url, "https://agentkit.cn-beijing.volcengineapi.com/?Action=ListTools&Version=2025-10-30");
  assert.equal(calls[0]?.body, JSON.stringify({ MaxResults: 10 }));
  assert.equal(page.nextToken, "tools-next");
  assert.equal(page.requestId, "tools-page-1");
  assert.deepEqual(page.data, [
    {
      toolId: "tool-code",
      name: "Code workspace",
      description: "CodeEnv tool",
      status: "Ready",
      toolType: "CodeEnv",
      projectName: "default",
      createdAt: "2026-07-01T00:00:00Z",
      updatedAt: "2026-07-18T00:00:00Z",
      enableSnapshot: true,
    },
    { toolId: "tool-private", status: "Creating", toolType: "Private" },
  ]);
});

test("AgentKit Tool search uses the SDK ListTools contains-filter contract", async () => {
  const bodies: string[] = [];
  const client = new AgentkitToolsClient({
    accessKey: "AKID",
    secretKey: "SECRET",
    fetch: async (_input, init) => {
      bodies.push(String(init?.body));
      return Response.json({ Result: { Tools: [] } });
    },
  });

  for (const field of ["Name", "Id", "Description"] as const) {
    await client.listTools({
      maxResults: 25,
      nextToken: "cursor",
      search: { field, value: " sandbox " },
    });
  }

  assert.deepEqual(bodies, ["Name", "Id", "Description"].map((field) => JSON.stringify({
    MaxResults: 25,
    NextToken: "cursor",
    Filters: [{ NameContains: field, Values: ["sandbox"] }],
  })));
  await assert.rejects(client.listTools({ maxResults: 101 }), /between 1 and 100/);
});

test("AgentKit client gets Tool details including the snapshot switch", async () => {
  const calls: Array<{ url: string; body: string }> = [];
  const client = new AgentkitToolsClient({
    accessKey: "AKID",
    secretKey: "SECRET",
    fetch: async (input, init) => {
      calls.push({ url: String(input), body: String(init?.body) });
      return Response.json({
        ResponseMetadata: { RequestId: "get-tool" },
        Result: {
          ToolId: "tool-snapshot",
          Name: "Snapshot Tool",
          Status: "Ready",
          ToolType: "CodeEnv",
          EnableSnapshot: false,
        },
      });
    },
  });

  assert.deepEqual(await client.getTool("tool-snapshot"), {
    toolId: "tool-snapshot",
    name: "Snapshot Tool",
    status: "Ready",
    toolType: "CodeEnv",
    enableSnapshot: false,
  });
  assert.equal(
    calls[0]?.url,
    "https://agentkit.cn-beijing.volcengineapi.com/?Action=GetTool&Version=2025-10-30",
  );
  assert.equal(calls[0]?.body, JSON.stringify({ ToolId: "tool-snapshot" }));
});

test("AgentKit Tool pagination rejects malformed pages and repeated cursors", async () => {
  let attempts = 0;
  const client = new AgentkitToolsClient({
    accessKey: "AKID",
    secretKey: "SECRET",
    fetch: async () => {
      attempts += 1;
      return Response.json({
        ResponseMetadata: { RequestId: `tool-page-${attempts}` },
        Result: {
          NextToken: "same-tool-token",
          Tools: [{ ToolId: `tool-${attempts}`, Status: "Ready" }],
        },
      });
    },
  });

  await assert.rejects(client.listAllTools(), /tool-page-2.*repeated NextToken/);
  assert.equal(attempts, 2);

  const malformed = new AgentkitToolsClient({
    accessKey: "AKID",
    secretKey: "SECRET",
    fetch: async () => Response.json({
      ResponseMetadata: { RequestId: "malformed-tools" },
      Result: { Tools: {} },
    }),
  });
  await assert.rejects(malformed.listTools(), /malformed-tools.*Tools is not an array/);
});

test("AgentKit client signs ListSessions and projects instance metadata", async () => {
  const calls: Array<{ url: string; init?: RequestInit }> = [];
  const client = new AgentkitToolsClient({
    accessKey: "AKID",
    secretKey: "SECRET",
    sessionToken: "SESSION",
    region: "cn-beijing",
    now: () => new Date("2026-07-18T01:02:03.000Z"),
    fetch: async (input, init) => {
      calls.push({ url: String(input), init });
      return Response.json({
        Result: {
          NextToken: "next-page",
          SessionInfos: [{
            SessionId: "session-1",
            UserSessionId: "task-1",
            Status: "Ready",
            ToolType: "CodeEnv",
            CreatedAt: "2026-07-18T00:00:00Z",
            ExpireAt: "2026-07-18T08:00:00Z",
            Endpoint: "https://sandbox.example/?Authorization=secret",
            SessionMeta: { WebshellUrl: "https://shell.example" },
          }],
        },
      });
    },
  });

  const page = await client.listSessions("tool-1");

  assert.equal(calls[0]?.url, "https://agentkit.cn-beijing.volcengineapi.com/?Action=ListSessions&Version=2025-10-30");
  assert.equal(calls[0]?.init?.method, "POST");
  assert.equal(calls[0]?.init?.body, JSON.stringify({ ToolId: "tool-1", MaxResults: 100 }));
  const headers = calls[0]?.init?.headers as Record<string, string>;
  assert.equal(headers["X-Date"], "20260718T010203Z");
  assert.equal(headers["X-Security-Token"], "SESSION");
  assert.match(headers.Authorization, /^HMAC-SHA256 Credential=AKID\/20260718\/cn-beijing\/agentkit\/request,/);
  assert.match(headers.Authorization, /SignedHeaders=content-type;host;x-content-sha256;x-date;x-security-token/);
  assert.match(headers["X-Content-Sha256"], /^[a-f0-9]{64}$/);
  assert.match(headers["X-Custom-Request-Context"], /^situla\/0\.1\.1 /);
  assert.equal(page.nextToken, "next-page");
  assert.deepEqual(page.data, [{
    sessionId: "session-1",
    toolId: "tool-1",
    userSessionId: "task-1",
    status: "Ready",
    toolType: "CodeEnv",
    createdAt: "2026-07-18T00:00:00Z",
    expireAt: "2026-07-18T08:00:00Z",
    endpoint: "https://sandbox.example/?Authorization=secret",
    webshellUrl: "https://shell.example",
  }]);
});

test("AgentKit client creates a minute-TTL session and surfaces API errors", async () => {
  const bodies: string[] = [];
  let fail = false;
  const client = new AgentkitToolsClient({
    accessKey: "AKID",
    secretKey: "SECRET",
    fetch: async (_input, init) => {
      bodies.push(String(init?.body));
      if (fail) {
        return Response.json({
          ResponseMetadata: { Error: { Code: "AccessDenied", Message: "denied" } },
        });
      }
      return Response.json({
        Result: { SessionId: "session-2", UserSessionId: "task-2" },
      });
    },
  });

  assert.deepEqual(await client.createSession("tool-2", {
    userSessionId: "task-2",
    ttl: 60,
  }), {
    sessionId: "session-2",
    toolId: "tool-2",
    userSessionId: "task-2",
    status: "Creating",
  });
  assert.equal(bodies[0], JSON.stringify({
    ToolId: "tool-2",
    UserSessionId: "task-2",
    Ttl: 60,
    TtlUnit: "second",
  }));
  await assert.rejects(client.createSession("tool-2", { ttl: 30 }), /between 60 and 86400/);
  await assert.rejects(
    client.createSession("tool-2", { userSessionId: "中文不允许" }),
    /only letters, digits, hyphens, or underscores/,
  );
  fail = true;
  await assert.rejects(client.getSession("tool-2", "session-2"), /AccessDenied.*denied/);
});

test("AgentKit client paginates snapshots and resumes one with a bounded TTL", async () => {
  const calls: Array<{ action: string; body: Record<string, unknown> }> = [];
  const pagination = Object.fromEntries([["NextToken", "snapshot-next"]]);
  let snapshotPage = 0;
  const client = new AgentkitToolsClient({
    accessKey: "AKID",
    secretKey: "SECRET",
    fetch: async (input, init) => {
      const action = new URL(String(input)).searchParams.get("Action") ?? "";
      const body = JSON.parse(String(init?.body)) as Record<string, unknown>;
      calls.push({ action, body });
      if (action === "ListSessionSnapshots") {
        snapshotPage += 1;
        return Response.json({
          ResponseMetadata: { RequestId: `snapshot-page-${snapshotPage}` },
          Result: snapshotPage === 1
            ? {
                ...pagination,
                Snapshots: [{
                  SnapshotId: "snapshot-new",
                  ToolId: "tool-snapshot",
                  SessionId: "session-old",
                  UserSessionId: "task-snapshot",
                  Status: "Ready",
                  Reason: "Expired",
                  CreatedAt: "2026-08-03T10:00:00Z",
                }],
              }
            : {
                Snapshots: [{
                  SnapshotId: "snapshot-old",
                  UserSessionId: "task-snapshot",
                  CreatedAt: "2026-08-03T09:00:00Z",
                }],
              },
        });
      }
      if (action === "ResumeSessionFromSnapshot") {
        return Response.json({ Result: { SessionId: "session-restored" } });
      }
      throw new Error(`unexpected action ${action}`);
    },
  });

  assert.deepEqual(await client.listAllSessionSnapshots("tool-snapshot", {
    userSessionId: "task-snapshot",
  }), [
    {
      snapshotId: "snapshot-new",
      toolId: "tool-snapshot",
      sessionId: "session-old",
      userSessionId: "task-snapshot",
      status: "Ready",
      reason: "Expired",
      createdAt: "2026-08-03T10:00:00Z",
    },
    {
      snapshotId: "snapshot-old",
      toolId: "tool-snapshot",
      userSessionId: "task-snapshot",
      createdAt: "2026-08-03T09:00:00Z",
    },
  ]);
  assert.deepEqual(await client.resumeSessionFromSnapshot(
    "tool-snapshot",
    "snapshot-new",
    60,
  ), {
    sessionId: "session-restored",
    toolId: "tool-snapshot",
    status: "Starting",
  });
  assert.deepEqual(calls.map(({ action, body }) => ({ action, body })), [
    {
      action: "ListSessionSnapshots",
      body: {
        ToolId: "tool-snapshot",
        MaxResults: 100,
        UserSessionId: "task-snapshot",
      },
    },
    {
      action: "ListSessionSnapshots",
      body: {
        ToolId: "tool-snapshot",
        MaxResults: 100,
        UserSessionId: "task-snapshot",
        ...pagination,
      },
    },
    {
      action: "ResumeSessionFromSnapshot",
      body: {
        ToolId: "tool-snapshot",
        SnapshotId: "snapshot-new",
        Ttl: 60,
        CreateNewInstance: false,
      },
    },
  ]);
});

test("AgentKit client finds an active Session by exact UserSessionId before restore", async () => {
  let body: Record<string, unknown> | undefined;
  const client = new AgentkitToolsClient({
    accessKey: "AKID",
    secretKey: "SECRET",
    fetch: async (_input, init) => {
      body = JSON.parse(String(init?.body)) as Record<string, unknown>;
      return Response.json({
        Result: {
          SessionInfos: [
            { SessionId: "terminating", UserSessionId: "task-1", Status: "Terminating" },
            { SessionId: "ready", UserSessionId: "task-1", Status: "Ready" },
          ],
        },
      });
    },
  });

  assert.equal(
    (await client.findSessionByUserSessionId("tool-1", "task-1"))?.sessionId,
    "ready",
  );
  assert.deepEqual(body, {
    ToolId: "tool-1",
    MaxResults: 100,
    Filters: [{ Name: "UserSessionId", Values: ["task-1"] }],
  });
});

test("AgentKit client supports a configured custom service and host", async () => {
  const calls: Array<{ url: string; authorization: string }> = [];
  const clientWithFetch = new AgentkitToolsClient({
    accessKey: "ak",
    secretKey: "sk",
    region: "cn-beijing",
    service: "agentkit_custom",
    host: "agentkit-custom.example.com",
    fetch: async (input, init) => {
      const headers = new Headers(init?.headers);
      calls.push({
        url: String(input),
        authorization: headers.get("authorization") ?? "",
      });
      return Response.json({ Result: { Tools: [] } });
    },
  });

  await clientWithFetch.listTools();
  assert.equal(
    calls[0]?.url,
    "https://agentkit-custom.example.com/?Action=ListTools&Version=2025-10-30",
  );
  assert.match(calls[0]?.authorization ?? "", /\/cn-beijing\/agentkit_custom\/request/);
});

test("AgentKit client retries 503 responses and honors Retry-After", async () => {
  let attempts = 0;
  const delays: number[] = [];
  const client = new AgentkitToolsClient({
    accessKey: "AKID",
    secretKey: "SECRET",
    retries: 2,
    sleep: async (milliseconds) => {
      delays.push(milliseconds);
    },
    fetch: async () => {
      attempts += 1;
      if (attempts === 1) {
        return Response.json(
          { ResponseMetadata: { RequestId: "retry-request" } },
          { status: 503, headers: { "Retry-After": "1" } },
        );
      }
      return Response.json({
        ResponseMetadata: { RequestId: "success-request" },
        Result: { SessionInfos: [] },
      });
    },
  });

  const page = await client.listSessions("tool-retry");
  assert.equal(attempts, 2);
  assert.deepEqual(delays, [1_000]);
  assert.equal(page.requestId, "success-request");
});

test("AgentKit errors preserve code, HTTP status, and RequestId", async () => {
  const client = new AgentkitToolsClient({
    accessKey: "AKID",
    secretKey: "SECRET",
    retries: 0,
    fetch: async () => Response.json({
      ResponseMetadata: {
        RequestId: "request-404",
        Error: { Code: "InvalidResource.NotFound", Message: "missing" },
      },
    }, { status: 404 }),
  });

  await assert.rejects(client.listSessions("missing-tool"), (error: unknown) => {
    assert.ok(error instanceof Error);
    assert.equal(error.name, "AgentkitApiError");
    assert.match(error.message, /InvalidResource\.NotFound/);
    assert.match(error.message, /HTTP 404/);
    assert.match(error.message, /RequestId request-404/);
    return true;
  });
});

test("AgentKit client rejects malformed success payloads", async () => {
  const client = new AgentkitToolsClient({
    accessKey: "AKID",
    secretKey: "SECRET",
    fetch: async () => Response.json({
      ResponseMetadata: { RequestId: "bad-response" },
      Result: { SessionInfos: {} },
    }),
  });
  await assert.rejects(client.listSessions("tool-invalid"), /bad-response.*SessionInfos is not an array/);
});

test("AgentKit pagination rejects repeated continuation tokens", async () => {
  let attempts = 0;
  const client = new AgentkitToolsClient({
    accessKey: "AKID",
    secretKey: "SECRET",
    fetch: async () => {
      attempts += 1;
      return Response.json({
        ResponseMetadata: { RequestId: `page-${attempts}` },
        Result: {
          NextToken: "repeated-token",
          SessionInfos: [{ SessionId: `session-${attempts}`, Status: "Ready" }],
        },
      });
    },
  });

  await assert.rejects(client.listAllSessions("tool-pages"), /page-2.*repeated NextToken/);
  assert.equal(attempts, 2);
});
