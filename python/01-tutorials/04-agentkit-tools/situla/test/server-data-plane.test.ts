import test from "node:test";
import assert from "node:assert/strict";
import { spawn, type ChildProcessWithoutNullStreams } from "node:child_process";
import { createServer } from "node:http";
import { mkdtempSync, mkdirSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { WebSocket, WebSocketServer } from "ws";

test("bridge proxies sandbox files, terminal, and the embedded isolated browser", async (context) => {
  let uploadContentType = "";
  let uploadBody = "";
  let browserInfoQuery = "";
  let browserForwardedPrefix = "";
  let cdpUpstreamUrl = "";
  let terminalPageQuery = "";
  let terminalWebSocketQuery = "";
  let workspaceSettingsRequest: Record<string, unknown> | undefined;
  let permissionSettingsRequest: Record<string, unknown> | undefined;
  let threadPermissionSettingsRequest: Record<string, unknown> | undefined;
  const sandboxServer = createServer(async (request, response) => {
    const requestUrl = new URL(request.url ?? "/", "http://sandbox.local");
    if (request.method === "POST" && request.url?.startsWith("/v1/file/upload")) {
      uploadContentType = request.headers["content-type"] ?? "";
      const chunks: Buffer[] = [];
      for await (const chunk of request) chunks.push(Buffer.from(chunk));
      uploadBody = Buffer.concat(chunks).toString("utf8");
      response.writeHead(200, { "content-type": "application/json" });
      response.end(JSON.stringify({ success: true }));
      return;
    }
    if (request.method === "GET" && requestUrl.pathname === "/v1/shell/terminal-url") {
      response.writeHead(200, { "content-type": "application/json" });
      response.end(JSON.stringify({
        success: true,
        data: "http://sandbox.local/terminal?session_id=shell-data-plane",
      }));
      return;
    }
    if (request.method === "GET" && requestUrl.pathname === "/terminal") {
      terminalPageQuery = requestUrl.search;
      response.writeHead(200, { "content-type": "text/html; charset=utf-8" });
      response.end("<!doctype html><title>Sandbox Terminal Test</title>");
      return;
    }
    if (request.method === "GET" && requestUrl.pathname === "/static/sandbox/terminal-test.js") {
      response.writeHead(200, { "content-type": "text/javascript; charset=utf-8" });
      response.end("globalThis.sandboxTerminalAsset = true;");
      return;
    }
    if (request.method === "GET" && requestUrl.pathname === "/browser-ui") {
      response.writeHead(200, { "content-type": "text/html; charset=utf-8" });
      response.end("<!doctype html><title>Sandbox Browser Test</title>");
      return;
    }
    if (request.method === "GET" && requestUrl.pathname === "/static/sandbox/browser-test.js") {
      response.writeHead(200, { "content-type": "text/javascript; charset=utf-8" });
      response.end("globalThis.sandboxBrowserAsset = true;");
      return;
    }
    if (request.method === "GET" && requestUrl.pathname === "/v1/browser/info") {
      browserInfoQuery = requestUrl.search;
      browserForwardedPrefix = String(request.headers["x-forwarded-prefix"] ?? "");
      const forwardedHost = String(request.headers["x-forwarded-host"] ?? "localhost");
      response.writeHead(200, { "content-type": "application/json" });
      response.end(JSON.stringify({
        success: true,
        data: {
          cdp_url: `ws://${forwardedHost}${browserForwardedPrefix}/cdp/devtools/browser/browser-test${requestUrl.search}`,
          cdp_ui_url: `http://${forwardedHost}${browserForwardedPrefix}/browser-ui${requestUrl.search}`,
          vnc_url: `http://${forwardedHost}${browserForwardedPrefix}/vnc/index.html${requestUrl.search}`,
          viewport: { width: 1280, height: 720 },
        },
      }));
      return;
    }
    response.writeHead(404);
    response.end();
  });
  const sandboxWss = new WebSocketServer({ noServer: true });
  sandboxServer.on("upgrade", (request, socket, head) => {
    sandboxWss.handleUpgrade(request, socket, head, (websocket) => {
      const pathname = new URL(request.url ?? "/", "http://localhost").pathname;
      if (pathname === "/v1/codex/app-server/") {
        websocket.on("message", (raw) => {
          const message = JSON.parse(raw.toString()) as Record<string, unknown>;
          if (message.method === "initialize") {
            websocket.send(JSON.stringify({ id: message.id, result: {} }));
          } else if (message.method === "thread/start") {
            websocket.send(JSON.stringify({
              id: message.id,
              result: {
                thread: { id: "thread-data-plane" },
                cwd: "/",
                approvalPolicy: "on-request",
                approvalsReviewer: "user",
                sandbox: {
                  type: "readOnly",
                  networkAccess: false,
                },
              },
            }));
          } else if (message.method === "fs/readDirectory") {
            websocket.send(JSON.stringify({
              id: message.id,
              result: {
                entries: [
                  { fileName: "home", isDirectory: true, isFile: false },
                  { fileName: "etc", isDirectory: true, isFile: false },
                  { fileName: "README", isDirectory: false, isFile: true },
                ],
              },
            }));
          } else if (message.method === "thread/settings/update") {
            const params = message.params as Record<string, unknown>;
            if (params.cwd !== undefined) {
              workspaceSettingsRequest = params;
            } else {
              threadPermissionSettingsRequest = params;
            }
            websocket.send(JSON.stringify({ id: message.id, result: {} }));
          } else if (message.method === "config/read") {
            websocket.send(JSON.stringify({
              id: message.id,
              result: {
                config: {},
                origins: {},
                layers: [{
                  name: {
                    type: "user",
                    file: "/root/.codex/config.toml",
                    profile: null,
                  },
                  version: "sha256:data-plane",
                  config: {},
                }],
              },
            }));
          } else if (message.method === "config/batchWrite") {
            permissionSettingsRequest = message.params as Record<string, unknown>;
            websocket.send(JSON.stringify({
              id: message.id,
              result: {
                status: "ok",
                version: "sha256:updated",
                filePath: "/root/.codex/config.toml",
                overriddenMetadata: null,
              },
            }));
          }
        });
        return;
      }
      if (pathname === "/v1/shell/ws") {
        terminalWebSocketQuery = new URL(request.url ?? "/", "http://localhost").search;
        websocket.send(JSON.stringify({ type: "session_id", data: "shell-data-plane" }));
        websocket.send(JSON.stringify({ type: "ready" }));
        websocket.on("message", (raw) => {
          const message = JSON.parse(raw.toString()) as { type?: string; data?: string };
          if (message.type === "input") {
            websocket.send(JSON.stringify({ type: "output", data: `echo:${message.data}` }));
          }
        });
        return;
      }
      if (pathname === "/cdp/devtools/browser/browser-test") {
        cdpUpstreamUrl = request.url ?? "";
        websocket.on("message", (raw, isBinary) => {
          websocket.send(raw, { binary: isBinary });
        });
      }
    });
  });
  await new Promise<void>((resolve) => sandboxServer.listen(0, "127.0.0.1", resolve));
  context.after(async () => {
    for (const client of sandboxWss.clients) client.terminate();
    sandboxWss.close();
    await new Promise<void>((resolve) => sandboxServer.close(() => resolve()));
  });
  const sandboxAddress = sandboxServer.address();
  assert.ok(sandboxAddress && typeof sandboxAddress === "object");

  const configHome = mkdtempSync(join(tmpdir(), "situla-data-plane-test-"));
  mkdirSync(join(configHome, "situla"));
  writeFileSync(join(configHome, "situla", "config.json"), JSON.stringify({ SITULA_PORT: 0 }));
  context.after(() => rmSync(configHome, { recursive: true, force: true }));
  const child = spawn(
    process.execPath,
    ["--disable-warning=ExperimentalWarning", "--experimental-strip-types", "src/server.ts"],
    {
      cwd: process.cwd(),
      env: {
        ...process.env,
        XDG_CONFIG_HOME: configHome,
        SITULA_PRIVATE_TYPE: "",
      },
      stdio: "pipe",
    },
  );
  context.after(async () => stopChild(child));
  const bridgePort = await listeningPort(child);
  const origin = `http://127.0.0.1:${bridgePort}`;
  const capability = await fetch(`${origin}/api/capability`, { headers: { origin } });
  const cookie = capability.headers.get("set-cookie")?.split(";", 1)[0];
  assert.ok(cookie);

  const connectedResponse = await fetch(`${origin}/api/sessions`, {
    method: "POST",
    headers: { cookie, origin, "content-type": "application/json" },
    body: JSON.stringify({
      sandboxUrl: `http://127.0.0.1:${sandboxAddress.port}/?Authorization=sandbox-secret`,
    }),
  });
  assert.equal(connectedResponse.status, 201);
  const connected = await connectedResponse.json() as { id: string };

  assert.equal(
    (await fetch(
      `${origin}/api/sessions/${encodeURIComponent(connected.id)}/directories`,
      { headers: { cookie, origin } },
    )).status,
    400,
  );
  assert.equal(
    (await fetch(
      `${origin}/api/sessions/${encodeURIComponent(connected.id)}/permissions`,
      {
        method: "POST",
        headers: { cookie, origin, "content-type": "application/json" },
        body: JSON.stringify({ sandboxMode: "unconfined" }),
      },
    )).status,
    400,
  );

  const directoriesResponse = await fetch(
    `${origin}/api/sessions/${encodeURIComponent(connected.id)}/directories?path=%2F`,
    { headers: { cookie, origin } },
  );
  assert.equal(directoriesResponse.status, 200);
  assert.deepEqual(await directoriesResponse.json(), {
    path: "/",
    directories: [
      { name: "etc", path: "/etc" },
      { name: "home", path: "/home" },
    ],
  });

  const workspaceSettingsResponse = await fetch(
    `${origin}/api/sessions/${encodeURIComponent(connected.id)}/workspace`,
    {
      method: "POST",
      headers: { cookie, origin, "content-type": "application/json" },
      body: JSON.stringify({ cwd: "/home" }),
    },
  );
  assert.equal(workspaceSettingsResponse.status, 200);
  assert.deepEqual(await workspaceSettingsResponse.json(), { cwd: "/home" });
  assert.deepEqual(workspaceSettingsRequest, {
    threadId: "thread-data-plane",
    cwd: "/home",
  });

  const permissionSettingsResponse = await fetch(
    `${origin}/api/sessions/${encodeURIComponent(connected.id)}/permissions`,
    {
      method: "POST",
      headers: { cookie, origin, "content-type": "application/json" },
      body: JSON.stringify({
        approvalPolicy: "never",
        approvalsReviewer: "auto_review",
        sandboxMode: "workspace-write",
        networkAccess: true,
      }),
    },
  );
  assert.equal(permissionSettingsResponse.status, 200);
  assert.deepEqual(await permissionSettingsResponse.json(), {
    approvalPolicy: "never",
    approvalsReviewer: "auto_review",
    sandboxMode: "workspace-write",
    networkAccess: true,
  });
  assert.deepEqual(permissionSettingsRequest, {
    edits: [
      { keyPath: "sandbox_mode", value: "workspace-write", mergeStrategy: "replace" },
      { keyPath: "approval_policy", value: "never", mergeStrategy: "replace" },
      { keyPath: "approvals_reviewer", value: "auto_review", mergeStrategy: "replace" },
      {
        keyPath: "sandbox_workspace_write.network_access",
        value: true,
        mergeStrategy: "replace",
      },
    ],
    expectedVersion: "sha256:data-plane",
    reloadUserConfig: true,
  });
  assert.deepEqual(threadPermissionSettingsRequest, {
    threadId: "thread-data-plane",
    approvalPolicy: "never",
    approvalsReviewer: "auto_review",
    sandboxPolicy: {
      type: "workspaceWrite",
      writableRoots: ["/home"],
      networkAccess: true,
      excludeTmpdirEnvVar: false,
      excludeSlashTmp: false,
    },
  });

  const form = new FormData();
  form.set("path", "/tmp/situla-upload.txt");
  form.set("file", new File(["upload-marker"], "situla-upload.txt"));
  const uploaded = await fetch(
    `${origin}/api/sessions/${encodeURIComponent(connected.id)}/files/upload`,
    { method: "POST", headers: { cookie, origin }, body: form },
  );
  assert.equal(uploaded.status, 200);
  assert.match(uploadContentType, /^multipart\/form-data; boundary=/);
  assert.match(uploadBody, /\/tmp\/situla-upload\.txt/);
  assert.match(uploadBody, /upload-marker/);

  const terminalResponse = await fetch(
    `${origin}/api/sessions/${encodeURIComponent(connected.id)}/terminal`,
    { headers: { cookie, origin } },
  );
  assert.equal(terminalResponse.status, 200);
  const terminalLaunch = await terminalResponse.json() as {
    url: string;
    shellSessionId: string;
  };
  assert.equal(terminalLaunch.shellSessionId, "shell-data-plane");
  assert.notEqual(new URL(terminalLaunch.url).origin, origin);
  assert.equal(new URL(terminalLaunch.url).port, new URL(origin).port);
  assert.equal(terminalLaunch.url.includes("sandbox-secret"), false);
  assert.equal(
    (await fetch(`${origin}${new URL(terminalLaunch.url).pathname}`, {
      headers: { origin },
    })).status,
    403,
  );

  const terminalPage = await fetch(terminalLaunch.url);
  assert.equal(terminalPage.status, 200);
  assert.equal(terminalPage.headers.get("x-frame-options"), null);
  assert.equal(terminalPage.headers.get("cross-origin-resource-policy"), "cross-origin");
  assert.match(await terminalPage.text(), /Sandbox Terminal Test/);
  assert.match(terminalPageQuery, /Authorization=sandbox-secret/);
  assert.doesNotMatch(terminalPageQuery, /session_id/);
  const terminalOrigin = new URL(terminalLaunch.url).origin;
  const terminalAsset = await fetch(
    new URL(`/terminal/${connected.id}/static/sandbox/terminal-test.js`, terminalLaunch.url),
    { headers: { origin: terminalOrigin } },
  );
  assert.equal(terminalAsset.status, 200);
  assert.match(await terminalAsset.text(), /sandboxTerminalAsset/);

  const terminalSocketUrl = new URL(
    `/terminal/${connected.id}/v1/shell/ws?session_id=${terminalLaunch.shellSessionId}`,
    terminalLaunch.url,
  );
  terminalSocketUrl.protocol = "ws:";
  const terminal = new WebSocket(terminalSocketUrl, {
    headers: { origin: terminalOrigin },
  });
  context.after(() => terminal.terminate());
  const ready = waitForTerminalMessage(terminal, (message) => message.type === "ready");
  await waitForWebSocketOpen(terminal);
  await ready;
  terminal.send(JSON.stringify({ type: "input", data: "hello\n" }));
  const output = await waitForTerminalMessage(
    terminal,
    (message) => message.type === "output",
  );
  assert.equal(output.data, "echo:hello\n");
  assert.match(terminalWebSocketQuery, /Authorization=sandbox-secret/);
  assert.match(terminalWebSocketQuery, /session_id=shell-data-plane/);

  const browserResponse = await fetch(
    `${origin}/api/sessions/${encodeURIComponent(connected.id)}/browser`,
    { headers: { cookie, origin } },
  );
  assert.equal(browserResponse.status, 200);
  const { url: browserUrl } = await browserResponse.json() as { url: string };
  assert.notEqual(new URL(browserUrl).origin, origin);
  assert.equal(new URL(browserUrl).port, new URL(origin).port);
  assert.equal(browserUrl.includes("sandbox-secret"), false);
  assert.equal(
    (await fetch(`${origin}${new URL(browserUrl).pathname}`, { headers: { origin } })).status,
    403,
  );

  const browserPage = await fetch(browserUrl);
  assert.equal(browserPage.status, 200);
  assert.equal(browserPage.headers.get("x-frame-options"), null);
  assert.equal(browserPage.headers.get("cross-origin-resource-policy"), "cross-origin");
  assert.match(await browserPage.text(), /Sandbox Browser Test/);
  const browserOrigin = new URL(browserUrl).origin;
  const browserAsset = await fetch(new URL("static/sandbox/browser-test.js", browserUrl), {
    headers: { origin: browserOrigin },
  });
  assert.equal(browserAsset.status, 200);
  assert.match(await browserAsset.text(), /sandboxBrowserAsset/);

  const browserInfoResponse = await fetch(new URL("v1/browser/info", browserUrl), {
    headers: { origin: browserOrigin },
  });
  assert.equal(browserInfoResponse.status, 200);
  const browserInfo = await browserInfoResponse.json() as {
    data: { cdp_url: string; cdp_ui_url: string; vnc_url?: string };
  };
  assert.equal(browserInfo.data.vnc_url, undefined);
  assert.equal(JSON.stringify(browserInfo).includes("sandbox-secret"), false);
  assert.equal(new URL(browserInfo.data.cdp_url).search, "");
  assert.equal(new URL(browserInfo.data.cdp_url).origin.replace(/^ws/, "http"), browserOrigin);
  assert.equal(browserInfoQuery, "?Authorization=sandbox-secret");
  assert.equal(browserForwardedPrefix, `/browser/${connected.id}`);

  const cdp = new WebSocket(browserInfo.data.cdp_url, { headers: { origin: browserOrigin } });
  context.after(() => cdp.terminate());
  await waitForWebSocketOpen(cdp);
  cdp.send(JSON.stringify({ id: 1, method: "Browser.getVersion" }));
  assert.equal(
    await waitForWebSocketText(cdp),
    JSON.stringify({ id: 1, method: "Browser.getVersion" }),
  );
  assert.equal(cdpUpstreamUrl, "/cdp/devtools/browser/browser-test?Authorization=sandbox-secret");

  assert.equal(
    (await fetch(browserUrl, { headers: { origin: "https://evil.example" } })).status,
    403,
  );
});

function waitForTerminalMessage(
  websocket: WebSocket,
  predicate: (message: { type?: string; data?: string }) => boolean,
): Promise<{ type?: string; data?: string }> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error("terminal message timed out")), 5_000);
    const listener = (raw: WebSocket.RawData) => {
      const message = JSON.parse(raw.toString()) as { type?: string; data?: string };
      if (!predicate(message)) return;
      clearTimeout(timer);
      websocket.off("message", listener);
      resolve(message);
    };
    websocket.on("message", listener);
    websocket.once("error", reject);
  });
}

function waitForWebSocketOpen(websocket: WebSocket): Promise<void> {
  if (websocket.readyState === WebSocket.OPEN) return Promise.resolve();
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error("WebSocket open timed out")), 5_000);
    websocket.once("open", () => {
      clearTimeout(timer);
      resolve();
    });
    websocket.once("error", reject);
  });
}

function waitForWebSocketText(websocket: WebSocket): Promise<string> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error("WebSocket message timed out")), 5_000);
    websocket.once("message", (raw) => {
      clearTimeout(timer);
      resolve(raw.toString());
    });
    websocket.once("error", reject);
  });
}

function listeningPort(child: ChildProcessWithoutNullStreams): Promise<number> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error("server did not start")), 5_000);
    child.once("error", reject);
    child.once("exit", (code) => reject(new Error(`server exited early (${code})`)));
    child.stdout.setEncoding("utf8");
    child.stdout.on("data", (chunk: string) => {
      const match = chunk.match(/Situla web client: http:\/\/127\.0\.0\.1:(\d+)/);
      if (!match) return;
      clearTimeout(timer);
      resolve(Number(match[1]));
    });
  });
}

async function stopChild(child: ChildProcessWithoutNullStreams): Promise<void> {
  if (child.exitCode !== null) return;
  child.kill("SIGTERM");
  await new Promise<void>((resolve) => child.once("exit", () => resolve()));
}
