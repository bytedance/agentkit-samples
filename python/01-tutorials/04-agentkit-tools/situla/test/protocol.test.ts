import test from "node:test";
import assert from "node:assert/strict";
import {
  appServerWebSocketUrl,
  redactSensitiveText,
  redactedUrl,
  sandboxServiceUrl,
} from "../src/protocol.ts";

test("converts a public HTTPS URL and preserves its auth query", () => {
  assert.equal(
    appServerWebSocketUrl(
      "https://sandbox.example/?faasInstanceName=instance&Authorization=token",
    ),
    "wss://sandbox.example/v1/codex/app-server/?faasInstanceName=instance&Authorization=token",
  );
});

test("accepts an already expanded app-server URL", () => {
  assert.equal(
    appServerWebSocketUrl("wss://sandbox.example/v1/codex/app-server/?token=secret"),
    "wss://sandbox.example/v1/codex/app-server/?token=secret",
  );
});

test("redacts the complete query", () => {
  assert.equal(
    redactedUrl("wss://sandbox.example/v1/codex/app-server/?token=secret&x=1"),
    "wss://sandbox.example/v1/codex/app-server/?<redacted>",
  );
});

test("rejects unrelated paths and URL userinfo", () => {
  assert.throws(() => appServerWebSocketUrl("https://sandbox.example/v1/shell/exec"));
  assert.throws(() => appServerWebSocketUrl("https://user:pass@sandbox.example/"));
});

test("redacts normalized URLs and standalone query secrets in error text", () => {
  const publicUrl = "https://sandbox.example/?Authorization=standalone-secret";
  const websocketUrl = appServerWebSocketUrl(publicUrl);
  assert.equal(
    redactSensitiveText(
      `gateway ${websocketUrl} rejected standalone-secret`,
      [publicUrl, websocketUrl],
    ),
    "gateway wss://sandbox.example/v1/codex/app-server/?<redacted> rejected <redacted>",
  );
});

test("builds sandbox HTTP and WebSocket data-plane URLs with auth intact", () => {
  const endpoint = "https://sandbox.example/?Authorization=secret";
  assert.equal(
    sandboxServiceUrl(endpoint, "/v1/file/upload"),
    "https://sandbox.example/v1/file/upload?Authorization=secret",
  );
  assert.equal(
    sandboxServiceUrl(endpoint, "/v1/shell/ws", true),
    "wss://sandbox.example/v1/shell/ws?Authorization=secret",
  );
  assert.equal(
    sandboxServiceUrl(
      "wss://sandbox.example/v1/codex/app-server/?Authorization=secret",
      "/v1/shell/ws",
      true,
    ),
    "wss://sandbox.example/v1/shell/ws?Authorization=secret",
  );
});
