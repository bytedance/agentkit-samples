import test from "node:test";
import assert from "node:assert/strict";
import { spawn, type ChildProcessWithoutNullStreams } from "node:child_process";
import { mkdtempSync, rmSync, mkdirSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

test("bridge API rejects cross-site and unauthenticated browser requests", async (context) => {
  const configHome = mkdtempSync(join(tmpdir(), "situla-server-test-"));
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
        SITULA_PRIVATE_TYPE: "HermesEnv",
      },
      stdio: "pipe",
    },
  );
  context.after(async () => stopChild(child));
  const port = await listeningPort(child);
  const origin = `http://127.0.0.1:${port}`;

  assert.equal((await fetch(`${origin}/api/health`)).status, 200);
  assert.equal((await fetch(`${origin}/api/sessions`, { method: "POST" })).status, 401);
  assert.equal(
    (await fetch(`${origin}/api/capability`, { headers: { origin: "https://evil.example" } })).status,
    403,
  );

  const capability = await fetch(`${origin}/api/capability`, { headers: { origin } });
  assert.equal(capability.status, 200);
  const cookie = capability.headers.get("set-cookie")?.split(";", 1)[0];
  assert.ok(cookie);
  const controlConfig = await fetch(`${origin}/api/agentkit/config`, {
    headers: { cookie, origin },
  });
  assert.deepEqual(await controlConfig.json(), {
    configured: false,
    consoleLogin: false,
    privateType: "HermesEnv",
  });
  assert.equal(
    (await fetch(`${origin}/api/agentkit/tools`, { headers: { cookie, origin } })).status,
    503,
  );
  const missingToolId = await fetch(`${origin}/api/sessions`, {
    method: "POST",
    headers: { cookie, origin, "content-type": "application/json" },
    body: JSON.stringify({ agentkitSessionId: "session-without-tool" }),
  });
  assert.deepEqual(
    { status: missingToolId.status, body: await missingToolId.json() },
    { status: 400, body: { error: "agentkitToolId is required with agentkitSessionId" } },
  );
  assert.equal(
    (await fetch(`${origin}/api/sessions`, {
      method: "POST",
      headers: { cookie, origin: "https://evil.example", "content-type": "application/json" },
      body: "{}",
    })).status,
    403,
  );
  assert.equal(
    (await fetch(`${origin}/api/sessions`, {
      method: "POST",
      headers: { cookie, origin },
      body: "{}",
    })).status,
    415,
  );
  const malformed = await fetch(`${origin}/api/sessions`, {
    method: "POST",
    headers: { cookie, origin, "content-type": "application/json" },
    body: "{",
  });
  assert.deepEqual(
    { status: malformed.status, body: await malformed.json() },
    { status: 400, body: { error: "request body must be valid JSON" } },
  );
});

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
