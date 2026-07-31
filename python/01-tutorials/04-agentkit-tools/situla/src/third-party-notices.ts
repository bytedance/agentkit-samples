import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

export function loadThirdPartyNotices(): string {
  return readFileSync(
    fileURLToPath(new URL("../THIRD_PARTY_NOTICES.txt", import.meta.url)),
    "utf8",
  );
}
