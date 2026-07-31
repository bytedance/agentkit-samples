import test from "node:test";
import assert from "node:assert/strict";
import { createServer } from "node:http";
import { WebSocket, WebSocketServer } from "ws";
import { sandboxServiceUrl } from "../src/protocol.ts";
import { SandboxTerminalProxy } from "../src/terminal-proxy.ts";

test("native terminal proxy keeps Endpoint credentials in the bridge", async (context) => {
  let terminalUrlQuery = "";
  let terminalPageQuery = "";
  let terminalWebSocketQuery = "";
  let terminalUrlRequests = 0;
  const upstream = createServer((request, response) => {
    const url = new URL(request.url ?? "/", "http://upstream.local");
    if (url.pathname === "/v1/shell/terminal-url") {
      terminalUrlRequests += 1;
      terminalUrlQuery = url.search;
      response.writeHead(200, { "content-type": "application/json" });
      response.end(JSON.stringify({
        success: true,
        data: "http://upstream.local/terminal?session_id=native-shell-1",
      }));
      return;
    }
    if (url.pathname === "/terminal") {
      terminalPageQuery = url.search;
      response.writeHead(200, { "content-type": "text/html; charset=utf-8" });
      response.end("<!doctype html><title>Native Terminal</title>");
      return;
    }
    if (url.pathname === "/static/sandbox/xterm.js") {
      response.writeHead(200, { "content-type": "text/javascript" });
      response.end("globalThis.nativeTerminal = true;");
      return;
    }
    response.writeHead(404);
    response.end();
  });
  const upstreamWebSocket = new WebSocketServer({ noServer: true });
  upstream.on("upgrade", (request, socket, head) => {
    upstreamWebSocket.handleUpgrade(request, socket, head, (websocket) => {
      terminalWebSocketQuery = new URL(
        request.url ?? "/",
        "http://upstream.local",
      ).search;
      websocket.on("message", (data, isBinary) => websocket.send(data, { binary: isBinary }));
    });
  });
  await new Promise<void>((resolve) => upstream.listen(0, "127.0.0.1", resolve));
  const upstreamAddress = upstream.address();
  assert.ok(upstreamAddress && typeof upstreamAddress === "object");

  const endpoint =
    `http://127.0.0.1:${upstreamAddress.port}/?Authorization=sandbox-secret`;
  const proxy = new SandboxTerminalProxy({
    getSession: (sessionId) => sessionId === "bridge-session"
      ? {
          sandboxServiceUrl: (pathname, websocket = false) =>
            sandboxServiceUrl(endpoint, pathname, websocket),
          safeError: (error) => error instanceof Error ? error.message : String(error),
        }
      : undefined,
  });
  const bridge = createServer((request, response) => {
    const url = new URL(request.url ?? "/", `http://${request.headers.host ?? "localhost"}`);
    void proxy.handleHttp(request, response, url).then((handled) => {
      if (handled) return;
      response.writeHead(404);
      response.end();
    });
  });
  bridge.on("upgrade", (request, socket, head) => {
    if (proxy.handleUpgrade(request, socket, head)) return;
    socket.destroy();
  });
  await new Promise<void>((resolve) => bridge.listen(0, "127.0.0.1", resolve));
  const bridgeAddress = bridge.address();
  assert.ok(bridgeAddress && typeof bridgeAddress === "object");
  const controlOrigin = `http://127.0.0.1:${bridgeAddress.port}`;

  context.after(async () => {
    for (const client of upstreamWebSocket.clients) client.terminate();
    proxy.close();
    await new Promise<void>((resolve) => bridge.close(() => resolve()));
    upstreamWebSocket.close();
    await new Promise<void>((resolve) => upstream.close(() => resolve()));
  });

  const launch = await proxy.terminalUrl(
    `127.0.0.1:${bridgeAddress.port}`,
    "bridge-session",
  );
  assert.equal(launch.shellSessionId, "native-shell-1");
  assert.equal(new URL(launch.url).hostname, "localhost");
  assert.equal(new URL(launch.url).pathname, "/terminal/bridge-session/terminal");
  assert.equal(new URL(launch.url).search, "?session_id=native-shell-1");
  assert.equal(launch.url.includes("sandbox-secret"), false);
  assert.equal(terminalUrlQuery, "?Authorization=sandbox-secret");

  const terminalPage = await fetch(launch.url);
  assert.equal(terminalPage.status, 200);
  assert.equal(terminalPage.headers.get("x-frame-options"), null);
  assert.match(await terminalPage.text(), /Native Terminal/);
  assert.match(terminalPageQuery, /Authorization=sandbox-secret/);
  assert.doesNotMatch(terminalPageQuery, /session_id/);

  const asset = await fetch(new URL(
    `/terminal/bridge-session/static/sandbox/xterm.js`,
    launch.url,
  ));
  assert.equal(asset.status, 200);
  assert.match(await asset.text(), /nativeTerminal/);

  const socketUrl = new URL(
    `/terminal/bridge-session/v1/shell/ws?session_id=${launch.shellSessionId}`,
    launch.url,
  );
  socketUrl.protocol = "ws:";
  const terminal = new WebSocket(socketUrl, {
    headers: { origin: new URL(launch.url).origin },
  });
  context.after(() => terminal.terminate());
  await waitForOpen(terminal);
  terminal.send(JSON.stringify({ type: "input", data: "hello\n" }));
  assert.equal(
    await waitForMessage(terminal),
    JSON.stringify({ type: "input", data: "hello\n" }),
  );
  assert.match(terminalWebSocketQuery, /Authorization=sandbox-secret/);
  assert.match(terminalWebSocketQuery, /session_id=native-shell-1/);

  assert.equal(
    (await fetch(
      `${controlOrigin}/terminal/bridge-session/terminal`,
      { headers: { origin: controlOrigin } },
    )).status,
    403,
  );
  assert.equal(
    (await fetch(launch.url, { headers: { origin: "https://evil.example" } })).status,
    403,
  );

  const resumed = await proxy.terminalUrl(
    `127.0.0.1:${bridgeAddress.port}`,
    "bridge-session",
    "native-shell-1",
  );
  assert.deepEqual(resumed, launch);
  assert.equal(terminalUrlRequests, 1);
});

function waitForOpen(websocket: WebSocket): Promise<void> {
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

function waitForMessage(websocket: WebSocket): Promise<string> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error("WebSocket message timed out")), 5_000);
    websocket.once("message", (data) => {
      clearTimeout(timer);
      resolve(data.toString());
    });
    websocket.once("error", reject);
  });
}
