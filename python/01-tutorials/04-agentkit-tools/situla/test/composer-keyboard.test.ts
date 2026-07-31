import test from "node:test";
import assert from "node:assert/strict";
import { isImeComposerKey } from "../web/src/composer-keyboard.ts";

test("composer ignores Enter used to confirm an IME candidate", () => {
  assert.equal(
    isImeComposerKey(
      { key: "Enter", isComposing: true, keyCode: 13 },
      true,
      false,
    ),
    true,
  );
  assert.equal(
    isImeComposerKey(
      { key: "Enter", isComposing: false, keyCode: 229 },
      false,
      false,
    ),
    true,
  );
  assert.equal(
    isImeComposerKey(
      { key: "Enter", isComposing: false, keyCode: 13 },
      false,
      true,
    ),
    true,
  );
});

test("composer sends a normal Enter after composition has settled", () => {
  assert.equal(
    isImeComposerKey(
      { key: "Enter", isComposing: false, keyCode: 13 },
      false,
      false,
    ),
    false,
  );
});
