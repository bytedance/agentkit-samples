import test from "node:test";
import assert from "node:assert/strict";
import {
  activeSkillMention,
  composerSkillDisplay,
  composerValueWithSkills,
  insertSkillMention,
  skillDisplayParts,
  skillIdsForText,
  skillMenuItems,
} from "../web/src/skill-mentions.ts";
import type { SkillSummary } from "../web/src/types.ts";

const skills: SkillSummary[] = [
  {
    id: "review-primary",
    name: "review",
    description: "Review the current change",
  },
  {
    id: "review-secondary",
    name: "review",
    description: "Review with the alternate workflow",
  },
  {
    id: "release",
    name: "release",
    description: "Prepare a release",
  },
];

test("Skill mention completion activates only for the token being typed", () => {
  assert.deepEqual(activeSkillMention("$rev"), { start: 0, query: "rev" });
  assert.equal(activeSkillMention("please $rel"), undefined);
  assert.equal(activeSkillMention(" $rel"), undefined);
  assert.equal(activeSkillMention("cost$review"), undefined);
  assert.equal(activeSkillMention("$review continue"), undefined);
});

test("Skill menu filters mentions and inserts the selected canonical name", () => {
  const mention = activeSkillMention("$rel");
  assert.ok(mention);
  assert.deepEqual(
    skillMenuItems(mention, skills).map((skill) => skill.id),
    ["release"],
  );
  assert.equal(
    insertSkillMention("$rel", mention, skills[2]!),
    "$release ",
  );
});

test("structured Skill IDs come only from consecutive recognized markers at the start", () => {
  assert.deepEqual(
    skillIdsForText(
      "$review, then prepare it. Ignore $release and $HOME.",
      skills,
      new Map([["review", "review-secondary"]]),
    ),
    ["review-secondary"],
  );
  assert.deepEqual(
    skillIdsForText("$review $release prepare it", skills),
    ["review-primary", "release"],
  );
  assert.deepEqual(skillIdsForText("$release ship it", skills), ["release"]);
  assert.deepEqual(skillIdsForText("$review then $release later", skills), [
    "review-primary",
  ]);
  assert.deepEqual(skillIdsForText("$unknown $release ship it", skills), []);
  assert.deepEqual(skillIdsForText("please $release ship it", skills), []);
  assert.deepEqual(skillIdsForText("plain prompt", skills), []);
});

test("only selected leading Skill markers become callout metadata", () => {
  assert.deepEqual(
    skillDisplayParts(
      "$imagegen $review create a hero image with $release later",
      ["imagegen", "review", "release"],
    ),
    {
      content: "create a hero image with $release later",
      skillNames: ["imagegen", "review"],
    },
  );
  assert.deepEqual(
    skillDisplayParts("$imagegen create a cover", []),
    {
      content: "$imagegen create a cover",
      skillNames: [],
    },
  );
  assert.deepEqual(
    skillDisplayParts("$unknown $review inspect this", ["review"]),
    {
      content: "$unknown $review inspect this",
      skillNames: [],
    },
  );
  assert.deepEqual(
    skillDisplayParts("$HOME/bin should stay literal", []),
    {
      content: "$HOME/bin should stay literal",
      skillNames: [],
    },
  );
});

test("Skill markers after ordinary prompt text remain literal", () => {
  assert.deepEqual(
    skillDisplayParts(
      "$review inspect this change with $release later",
      ["review", "release"],
    ),
    {
      content: "inspect this change with $release later",
      skillNames: ["review"],
    },
  );
});

test("composer turns confirmed leading Skills into removable blocks", () => {
  assert.deepEqual(
    composerSkillDisplay(
      "$plugin-creator build a plugin",
      ["plugin-creator"],
    ),
    {
      content: "build a plugin",
      skillNames: ["plugin-creator"],
    },
  );
  assert.deepEqual(
    composerSkillDisplay("$plugin", ["plugin"]),
    {
      content: "$plugin",
      skillNames: [],
    },
  );
  assert.deepEqual(
    composerSkillDisplay(
      "$unknown $plugin-creator build a plugin",
      ["plugin-creator"],
    ),
    {
      content: "$unknown $plugin-creator build a plugin",
      skillNames: [],
    },
  );
  assert.equal(
    composerValueWithSkills("build a plugin", ["plugin-creator"]),
    "$plugin-creator build a plugin",
  );
  assert.equal(
    composerValueWithSkills("", ["plugin-creator"]),
    "$plugin-creator ",
  );
});
