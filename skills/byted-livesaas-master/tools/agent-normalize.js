"use strict";

// Keep in sync with cli/lib/agent-normalize.js

/** 埋点 agent 维度固定枚举，与 CLI `--agent` 文档一致 */
const ALLOWED_AGENTS = new Set([
  "codex",
  "claude-code",
  "cursor",
  "trae",
  "trae-cn",
  "openclaw",
  "unknown",
]);

const AGENT_ALIASES = {
  claudecode: "claude-code",
  claude: "claude-code",
};

function normalizeAgentName(input) {
  const raw = String(input || "").trim().slice(0, 64);
  if (!raw) {
    return "unknown";
  }
  const lower = raw.toLowerCase();
  const canonical = AGENT_ALIASES[lower] || lower;
  return ALLOWED_AGENTS.has(canonical) ? canonical : "unknown";
}

module.exports = {
  ALLOWED_AGENTS,
  normalizeAgentName,
};
