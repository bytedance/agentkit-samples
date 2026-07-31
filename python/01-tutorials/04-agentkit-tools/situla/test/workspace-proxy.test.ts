import test from "node:test";
import assert from "node:assert/strict";
import { createServer } from "node:http";
import { WebSocket, WebSocketServer } from "ws";
import { SandboxWorkspaceProxy } from "../src/workspace-proxy.ts";

test("external workspace proxy keeps endpoint credentials in the bridge for HTTP and WebSocket", async (context) => {
  let httpQuery = "";
  let postedBody = "";
  let hermesSessionToken = "";
  let websocketQuery = "";
  let websocketCookie = "";
  let websocketOrigin = "";
  const upstream = createServer(async (request, response) => {
    const url = new URL(request.url ?? "/", "http://upstream.local");
    httpQuery = url.search;
    if (url.pathname === "/openclaw") {
      response.writeHead(302, {
        location: `http://${request.headers.host}/openclaw/?Authorization=sandbox-secret&next=1`,
      });
      response.end();
      return;
    }
    if (url.pathname === "/openclaw/") {
      response.writeHead(200, {
        "content-type": "text/html; charset=utf-8",
        "set-cookie": "upstream_state=ready; Domain=upstream.example; Path=/; Secure; HttpOnly",
      });
      response.end("<!doctype html><title>OpenClaw workspace</title>");
      return;
    }
    if (request.method === "POST" && url.pathname === "/openclaw/api/message") {
      const chunks: Buffer[] = [];
      for await (const chunk of request) chunks.push(Buffer.from(chunk));
      postedBody = Buffer.concat(chunks).toString("utf8");
      response.writeHead(200, { "content-type": "application/json" });
      response.end(JSON.stringify({ ok: true }));
      return;
    }
    if (url.pathname === "/hermes/api/config") {
      hermesSessionToken = String(request.headers["x-hermes-session-token"] ?? "");
      response.writeHead(200, { "content-type": "application/json" });
      response.end(JSON.stringify({ ok: true }));
      return;
    }
    response.writeHead(404);
    response.end();
  });
  const upstreamWebSocket = new WebSocketServer({ noServer: true });
  upstream.on("upgrade", (request, socket, head) => {
    upstreamWebSocket.handleUpgrade(request, socket, head, (websocket) => {
      const url = new URL(request.url ?? "/", "http://upstream.local");
      websocketQuery = url.search;
      websocketCookie = String(request.headers.cookie ?? "");
      websocketOrigin = String(request.headers.origin ?? "");
      websocket.on("message", (data, isBinary) => websocket.send(data, { binary: isBinary }));
    });
  });
  await new Promise<void>((resolve) => upstream.listen(0, "127.0.0.1", resolve));
  const upstreamAddress = upstream.address();
  assert.ok(upstreamAddress && typeof upstreamAddress === "object");

  const proxy = new SandboxWorkspaceProxy();
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
  const origin = `http://127.0.0.1:${bridgeAddress.port}`;
  const launch = proxy.createLaunch(
    "OpenClaw",
    `http://127.0.0.1:${upstreamAddress.port}/?Authorization=sandbox-secret`,
  );
  const launchCookie = launch.setCookie.split(";", 1)[0];
  const hermesLaunch = proxy.createLaunch(
    "Hermes",
    `http://127.0.0.1:${upstreamAddress.port}/?Authorization=sandbox-secret`,
  );
  const hermesLaunchCookie = hermesLaunch.setCookie.split(";", 1)[0];

  context.after(async () => {
    for (const client of upstreamWebSocket.clients) client.terminate();
    proxy.close();
    await new Promise<void>((resolve) => bridge.close(() => resolve()));
    upstreamWebSocket.close();
    await new Promise<void>((resolve) => upstream.close(() => resolve()));
  });

  assert.equal(launch.url, "/openclaw");
  assert.match(launch.setCookie, /HttpOnly; SameSite=Strict/);
  assert.equal(hermesLaunch.url, "/hermes");
  assert.match(hermesLaunch.setCookie, /Path=\/hermes/);
  const hermesConfig = await fetch(`${origin}/hermes/api/config`, {
    headers: {
      cookie: hermesLaunchCookie,
      origin,
      "x-hermes-session-token": "hermes-session-token",
    },
  });
  assert.equal(hermesConfig.status, 200);
  assert.equal(hermesSessionToken, "hermes-session-token");
  const redirect = await fetch(`${origin}/openclaw`, {
    headers: { cookie: launchCookie, origin },
    redirect: "manual",
  });
  assert.equal(redirect.status, 302);
  assert.equal(redirect.headers.get("location"), "/openclaw/?next=1");
  assert.equal(httpQuery, "?Authorization=sandbox-secret");

  const page = await fetch(`${origin}/openclaw/`, {
    headers: { cookie: launchCookie, origin },
  });
  assert.equal(page.status, 200);
  assert.match(await page.text(), /OpenClaw workspace/);
  const upstreamCookie = page.headers.get("set-cookie") ?? "";
  assert.match(upstreamCookie, /upstream_state=ready/);
  assert.match(upstreamCookie, /Path=\/openclaw/);
  assert.doesNotMatch(upstreamCookie, /Domain=|Secure/i);
  assert.equal(upstreamCookie.includes("sandbox-secret"), false);

  const posted = await fetch(`${origin}/openclaw/api/message?conversation=1`, {
    method: "POST",
    headers: {
      cookie: `${launchCookie}; upstream_state=ready`,
      origin,
      "content-type": "application/json",
    },
    body: JSON.stringify({ text: "hello" }),
  });
  assert.equal(posted.status, 200);
  assert.equal(postedBody, JSON.stringify({ text: "hello" }));
  assert.match(httpQuery, /Authorization=sandbox-secret/);
  assert.match(httpQuery, /conversation=1/);

  const websocket = new WebSocket(
    `ws://127.0.0.1:${bridgeAddress.port}/openclaw/ws?channel=main`,
    { headers: { cookie: `${launchCookie}; upstream_state=ready`, origin } },
  );
  context.after(() => websocket.terminate());
  await waitForOpen(websocket);
  websocket.send("ping");
  assert.equal(await waitForMessage(websocket), "ping");
  assert.match(websocketQuery, /Authorization=sandbox-secret/);
  assert.match(websocketQuery, /channel=main/);
  assert.equal(websocketCookie, "upstream_state=ready");
  assert.equal(websocketOrigin, `http://127.0.0.1:${upstreamAddress.port}`);

  assert.equal((await fetch(`${origin}/openclaw`, { headers: { origin } })).status, 401);
  assert.equal(
    (await fetch(`${origin}/openclaw`, {
      headers: { cookie: launchCookie, origin: "https://evil.example" },
    })).status,
    403,
  );
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
