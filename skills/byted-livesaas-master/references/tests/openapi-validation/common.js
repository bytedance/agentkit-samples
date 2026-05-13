"use strict";

const path = require("node:path");
const { spawnSync } = require("node:child_process");

function repoRoot() {
  return path.resolve(__dirname, "..", "..", "..", "..");
}

function cliPath() {
  const override = process.env.BYTEDLIVE_CLI_PATH;
  if (override) {
    return path.resolve(override);
  }
  return path.join(repoRoot(), "cli", "bin", "bytedlive.js");
}

function runCli(args, extraEnv = {}) {
  const result = spawnSync(process.execPath, [cliPath(), ...args], {
    cwd: repoRoot(),
    stdio: ["ignore", "pipe", "pipe"],
    encoding: "utf8",
    env: { ...process.env, ...extraEnv },
  });
  return {
    status: typeof result.status === "number" ? result.status : 1,
    stdout: String(result.stdout || ""),
    stderr: String(result.stderr || ""),
  };
}

function requiredOnlineEnvReady() {
  return Boolean(process.env.LIVESAAS_ACCESS_KEY_ID && process.env.LIVESAAS_SECRET_ACCESS_KEY);
}

function shouldRunOnline() {
  return String(process.env.BYTEDLIVE_RUN_ONLINE_VALIDATION || "").toLowerCase() === "true";
}

module.exports = {
  runCli,
  shouldRunOnline,
  requiredOnlineEnvReady,
};
