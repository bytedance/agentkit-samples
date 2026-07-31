import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import { loadThirdPartyNotices } from "../src/third-party-notices.ts";

test("source distribution exposes generated third-party notices", () => {
  const notices = loadThirdPartyNotices();
  assert.equal(notices, readFileSync("THIRD_PARTY_NOTICES.txt", "utf8"));
  assert.match(notices, /Node\.js v24\.18\.1/);
  assert.match(notices, /react@19\.2\.7/);
  assert.match(notices, /ws@8\.21\.1/);
});
