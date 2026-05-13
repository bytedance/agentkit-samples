"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const { runCli } = require("./common");

const CASES = [
  ["control", "media", "delete-videos", "--video-ids", "vid1,vid2"],
  ["control", "channel", "forbid-live", "--activity-id", "10001"],
  ["control", "room", "delete", "--activity-id", "10001"],
  ["control", "moderation", "delete-message", "--message-id", "msg001"],
];

for (const args of CASES) {
  test(`dryrun ${args.slice(0, 3).join(" ")}`, () => {
    const result = runCli([...args, "--dry-run", "--pretty", "--non-interactive"]);
    assert.equal(result.status, 0, result.stderr || result.stdout);
    assert.match(result.stdout, /"dry_run"\s*:\s*true/);
    assert.match(result.stdout, /"request_preview"/);
  });
}
