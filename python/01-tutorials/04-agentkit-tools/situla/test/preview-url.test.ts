import test from "node:test";
import assert from "node:assert/strict";
import {
  extractSandboxPreviewUrls,
  normalizeSandboxPreviewUrl,
} from "../web/src/preview-url.ts";

test("preview URLs are extracted, normalized, and deduplicated", () => {
  assert.deepEqual(
    extractSandboxPreviewUrls(`服务已启动：

- http://127.0.0.1:8000/index.html
- [备用地址](http://0.0.0.0:8000/index.html)
- https://localhost:8443/demo?q=1#result。`),
    [
      "http://127.0.0.1:8000/index.html",
      "https://localhost:8443/demo?q=1#result",
    ],
  );
});

test("Markdown emphasis suffixes do not create duplicate preview cards", () => {
  assert.deepEqual(
    extractSandboxPreviewUrls([
      "`curl http://127.0.0.1:8000/index.html`",
      "**http://127.0.0.1:8000/index.html**。",
    ].join("\n")),
    ["http://127.0.0.1:8000/index.html"],
  );
});

test("preview URL detection ignores non-loopback and credentialed addresses", () => {
  assert.deepEqual(
    extractSandboxPreviewUrls([
      "https://example.com/demo",
      "http://localhost.evil.example:8000/",
      "http://user:secret@127.0.0.1:8000/",
    ].join(" ")),
    [],
  );
  assert.equal(normalizeSandboxPreviewUrl("ftp://127.0.0.1/demo"), undefined);
  assert.equal(normalizeSandboxPreviewUrl("http://[::1]:3000/"), "http://[::1]:3000/");
});

test("preview URL extraction is bounded", () => {
  assert.deepEqual(
    extractSandboxPreviewUrls(
      "http://localhost:3000 http://localhost:3001 http://localhost:3002 http://localhost:3003",
    ),
    [
      "http://localhost:3000/",
      "http://localhost:3001/",
      "http://localhost:3002/",
    ],
  );
});
