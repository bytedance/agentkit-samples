"use strict";

const path = require("node:path");
const { normalizeAgentName } = require("./agent-normalize");

const AGENT_INSTALL_MARKERS = [
  { marker: `${path.sep}.cursor${path.sep}skills${path.sep}`, agent: "cursor" },
  { marker: `${path.sep}.codex${path.sep}skills${path.sep}`, agent: "codex" },
  { marker: `${path.sep}.claude${path.sep}skills${path.sep}`, agent: "claude-code" },
  { marker: `${path.sep}.trae-cn${path.sep}skills${path.sep}`, agent: "trae-cn" },
  { marker: `${path.sep}.trae${path.sep}skills${path.sep}`, agent: "trae" },
  { marker: `${path.sep}.openclaw${path.sep}skills${path.sep}`, agent: "openclaw" },
];

function detectAgentFromInstallPath(skillRootDir) {
  const normalized = path.normalize(skillRootDir);
  for (const { marker, agent } of AGENT_INSTALL_MARKERS) {
    if (normalized.includes(marker)) {
      return agent;
    }
  }
  return "";
}

function resolveReportAgent(options = {}) {
  const { cliArg, skillRootDir } = options;
  if (cliArg) {
    return normalizeAgentName(cliArg);
  }

  const fromEnv = process.env.BYTEDLIVE_AGENT || process.env.BYTEDLIVE_SKILL_AGENT;
  if (fromEnv) {
    return normalizeAgentName(fromEnv);
  }

  const fromPath = detectAgentFromInstallPath(skillRootDir);
  if (fromPath) {
    return fromPath;
  }

  return "unknown";
}

module.exports = {
  detectAgentFromInstallPath,
  normalizeAgentName,
  resolveReportAgent,
};
