"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const { runCli, shouldRunOnline, requiredOnlineEnvReady } = require("./common");

const SHOULD_SKIP = !shouldRunOnline() || !requiredOnlineEnvReady();
const ACTIVITY_ID = process.env.BYTEDLIVE_TEST_ACTIVITY_ID || "";

test(
  "online write room.create-v2",
  { skip: SHOULD_SKIP ? "enable BYTEDLIVE_RUN_ONLINE_VALIDATION=true and AK/SK env first" : false },
  () => {
    const result = runCli([
      "control",
      "room",
      "create-v2",
      "--body-json",
      JSON.stringify({ Name: `cli-e2e-${Date.now()}` }),
      "--pretty",
      "--non-interactive",
    ]);
    assert.equal(result.status, 0, result.stderr || result.stdout);
    assert.match(result.stdout, /"code"\s*:\s*0/);
  }
);

test(
  "online write safe with existing activity id",
  { skip: SHOULD_SKIP || !ACTIVITY_ID ? "set BYTEDLIVE_TEST_ACTIVITY_ID to validate write-safe cases" : false },
  () => {
    const cases = [
      ["control", "product", "explain", "--activity-id", ACTIVITY_ID],
      ["control", "product", "enable", "--activity-id", ACTIVITY_ID],
      ["control", "moderation", "add-antidirt", "--activity-id", ACTIVITY_ID],
      ["control", "channel", "close-link-webcast", "--activity-id", ACTIVITY_ID],
    ];
    for (const args of cases) {
      const result = runCli([...args, "--body-json", JSON.stringify({ ActivityId: Number(ACTIVITY_ID) }), "--pretty", "--non-interactive"]);
      assert.equal(result.status, 0, result.stderr || result.stdout);
      assert.match(result.stdout, /"code"\s*:\s*0/);
    }
  }
);
