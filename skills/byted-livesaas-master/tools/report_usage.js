#!/usr/bin/env node
"use strict";

const fs = require("node:fs");
const http = require("node:http");
const https = require("node:https");
const path = require("node:path");

const { resolveReportAgent } = require("./detect-agent");

const SKILL_NAME = "byted-livesaas-master";
const DEFAULT_ENDPOINT = "https://live.byteoc.com/apiservice/skill/track";
const TIMEOUT_MS = 800;

function readVersion() {
  try {
    return fs.readFileSync(path.join(__dirname, "..", "VERSION"), "utf8").trim();
  } catch {
    return "";
  }
}

function readArg(name) {
  const prefix = `--${name}=`;
  const inline = process.argv.find((arg) => arg.startsWith(prefix));
  if (inline) return inline.slice(prefix.length);
  const index = process.argv.indexOf(`--${name}`);
  if (index >= 0) return process.argv[index + 1] || "";
  return "";
}

function postJson(urlString, payload) {
  return new Promise((resolve) => {
    let url;
    try {
      url = new URL(urlString);
    } catch {
      resolve(false);
      return;
    }

    const body = JSON.stringify(payload);
    const client = url.protocol === "http:" ? http : https;
    const req = client.request(
      url,
      {
        method: "POST",
        timeout: TIMEOUT_MS,
        headers: {
          "content-type": "application/json",
          "content-length": Buffer.byteLength(body),
        },
      },
      (res) => {
        res.resume();
        res.on("end", () => resolve(res.statusCode >= 200 && res.statusCode < 500));
      }
    );
    req.on("timeout", () => {
      req.destroy();
      resolve(false);
    });
    req.on("error", () => resolve(false));
    req.end(body);
  });
}

async function main() {
  if (process.env.BYTEDLIVE_TELEMETRY_DISABLED === "1" || process.env.BYTEDLIVE_TELEMETRY_DISABLED === "true") {
    return;
  }

  await postJson(process.env.BYTEDLIVE_TELEMETRY_ENDPOINT || DEFAULT_ENDPOINT, {
    skillName: SKILL_NAME,
    agent: resolveReportAgent({
      cliArg: readArg("agent"),
      skillRootDir: path.join(__dirname, ".."),
    }),
    source: "skill-start",
    action: "skill_use",
    eventId: readArg("event-id") || undefined,
    skillVersion: readVersion(),
  });
}

main().catch(() => {});
