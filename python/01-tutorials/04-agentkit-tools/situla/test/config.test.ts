import test from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, rmSync, statSync, writeFileSync, mkdirSync } from "node:fs";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { loadSitulaConfiguration, writeSitulaConfiguration } from "../src/config.ts";

test("configuration is read only from config.json and ignores environment overrides", (context) => {
  const root = mkdtempSync(join(tmpdir(), "situla-config-test-"));
  context.after(() => rmSync(root, { recursive: true, force: true }));
  const directory = join(root, "situla");
  mkdirSync(directory);
  writeFileSync(join(directory, "config.json"), JSON.stringify({
    VOLCENGINE_REGION: "cn-file", VOLCENGINE_SERVICE: "agentkit_custom",
    VOLCENGINE_HOST: "agentkit-custom.example.com", SITULA_PORT: 9000,
  }));
  const loaded = loadSitulaConfiguration({
    XDG_CONFIG_HOME: root, VOLCENGINE_REGION: "cn-env", AGENTKIT_HTTP_TIMEOUT: "45",
  });
  assert.equal(loaded.values.VOLCENGINE_REGION, "cn-file");
  assert.equal("TOOL_TYPE" in loaded.values, false);
  assert.equal(loaded.values.VOLCENGINE_SERVICE, "agentkit_custom");
  assert.equal(loaded.values.AGENTKIT_HTTP_TIMEOUT, "30");
  assert.equal(loaded.values.AGENTKIT_HTTP_RETRIES, "2");
  assert.equal(loaded.values.SITULA_PORT, "9000");
});

test("configuration writer creates one private config file without credentials", (context) => {
  const root = mkdtempSync(join(tmpdir(), "situla-config-write-test-"));
  context.after(() => rmSync(root, { recursive: true, force: true }));
  const initial = loadSitulaConfiguration({ XDG_CONFIG_HOME: root });
  const values = { ...initial.values, VOLCENGINE_SERVICE: "agentkit_custom", VOLCENGINE_HOST: "agentkit-custom.example.com" };
  writeSitulaConfiguration(values, initial.paths);
  assert.equal(statSync(initial.paths.directory).mode & 0o777, 0o700);
  assert.equal(statSync(initial.paths.config).mode & 0o777, 0o600);
  const config = JSON.parse(readFileSync(initial.paths.config, "utf8"));
  assert.equal(config.TOOL_TYPE, undefined);
  assert.equal(config.VOLCENGINE_SERVICE, "agentkit_custom");
  assert.equal(config.VOLCENGINE_ACCESS_KEY, undefined);
  assert.equal(config.VOLCENGINE_SESSION_TOKEN, undefined);
});

test("legacy TOOL_TYPE is accepted while reading and removed on the next write", (context) => {
  const root = mkdtempSync(join(tmpdir(), "situla-tool-type-test-"));
  context.after(() => rmSync(root, { recursive: true, force: true }));
  const directory = join(root, "situla");
  mkdirSync(directory);
  writeFileSync(join(directory, "config.json"), JSON.stringify({ TOOL_TYPE: "Hermes" }));
  const loaded = loadSitulaConfiguration({ XDG_CONFIG_HOME: root });
  assert.equal("TOOL_TYPE" in loaded.values, false);
  writeSitulaConfiguration(loaded.values, loaded.paths);
  assert.equal(JSON.parse(readFileSync(loaded.paths.config, "utf8")).TOOL_TYPE, undefined);
});
