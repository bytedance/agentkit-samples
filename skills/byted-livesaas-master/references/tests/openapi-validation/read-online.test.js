"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const { runCli, shouldRunOnline, requiredOnlineEnvReady } = require("./common");

const SHOULD_SKIP = !shouldRunOnline() || !requiredOnlineEnvReady();
const CASES = [
  ["control", "analytics", "watch-duration"],
  ["control", "analytics", "watch-duration-legacy"],
  ["control", "analytics", "user-track"],
  ["control", "account", "get-base"],
  ["control", "account", "get-config"],
  ["control", "channel", "lines"],
  ["control", "account", "product-status"],
  ["control", "account", "ability-amount-console"],
  ["control", "account", "can-use-ability"],
  ["control", "account", "product-statistics-third"],
  ["control", "channel", "lines-pull-info-console"],
  ["control", "media", "check-doc-lib-storage"],
  ["control", "account", "product-list"],
];

for (const args of CASES) {
  test(
    `online read ${args.slice(0, 3).join(" ")}`,
    { skip: SHOULD_SKIP ? "enable BYTEDLIVE_RUN_ONLINE_VALIDATION=true and AK/SK env first" : false },
    () => {
      const result = runCli([...args, "--pretty", "--non-interactive"]);
      assert.equal(result.status, 0, result.stderr || result.stdout);
      assert.match(result.stdout, /"code"\s*:\s*0/);
    }
  );
}
