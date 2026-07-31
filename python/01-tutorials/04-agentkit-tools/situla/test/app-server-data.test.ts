import test from "node:test";
import assert from "node:assert/strict";
import {
  modelPageFromResult,
  skillsFromResult,
  threadPageFromResult,
  threadSnapshotFromResult,
} from "../src/app-server-data.ts";

test("thread snapshot restores user and assistant history", () => {
  const snapshot = threadSnapshotFromResult("thread/resume", {
    model: "gpt-test",
    cwd: "/workspace",
    approvalPolicy: "on-request",
    approvalsReviewer: "auto_review",
    sandbox: {
      type: "workspaceWrite",
      writableRoots: ["/workspace"],
      networkAccess: true,
      excludeTmpdirEnvVar: false,
      excludeSlashTmp: false,
    },
    thread: {
      id: "thread-1",
      preview: "hello",
      cwd: "/workspace",
      modelProvider: "openai",
      createdAt: 10,
      updatedAt: 20,
      status: { type: "idle" },
      turns: [
        {
          id: "turn-1",
          startedAt: 12,
          items: [
            {
              type: "userMessage",
              id: "user-1",
              content: [
                {
                  type: "text",
                  text: "$review hello, keep middle $review and $HOME unchanged",
                },
                { type: "skill", name: "review", path: "/skills/review/SKILL.md" },
                { type: "localImage", path: "/workspace/image.png" },
              ],
            },
            {
              type: "agentMessage",
              id: "agent-1",
              text: "world",
              phase: "final_answer",
            },
            { type: "reasoning", id: "reasoning-1", summary: ["hidden"] },
          ],
        },
      ],
    },
  });

  assert.deepEqual(snapshot, {
    thread: {
      id: "thread-1",
      preview: "hello",
      cwd: "/workspace",
      modelProvider: "openai",
      createdAt: 10,
      updatedAt: 20,
      status: "idle",
    },
    messages: [
      {
        id: "user-1",
        role: "user",
        content: "hello, keep middle $review and $HOME unchanged\n[本地图片: /workspace/image.png]",
        timestamp: 12_000,
        skillNames: ["review"],
      },
      {
        id: "agent-1",
        role: "assistant",
        content: "world",
        timestamp: 12_001,
      },
    ],
    model: "gpt-test",
    cwd: "/workspace",
    approvalPolicy: "on-request",
    approvalsReviewer: "auto_review",
    sandboxMode: "workspace-write",
    networkAccess: true,
  });
});

test("thread and model pages skip malformed entries and preserve cursors", () => {
  assert.deepEqual(
    threadPageFromResult({
      data: [
        { id: "thread-1", preview: "one", updatedAt: 2 },
        { preview: "missing id" },
      ],
      nextCursor: "next-thread",
    }),
    {
      data: [{
        id: "thread-1",
        preview: "one",
        cwd: "",
        modelProvider: "",
        createdAt: 0,
        updatedAt: 2,
        status: "unknown",
      }],
      nextCursor: "next-thread",
    },
  );

  assert.deepEqual(
    modelPageFromResult({
      data: [
        { id: "catalog-id", model: "gpt-test", displayName: "GPT Test", isDefault: true },
        { nope: true },
      ],
      nextCursor: "next-model",
    }),
    {
      data: [{
        id: "gpt-test",
        displayName: "GPT Test",
        description: "",
        isDefault: true,
      }],
      nextCursor: "next-model",
    },
  );
});

test("skill list keeps enabled path-backed skills for the requested cwd", () => {
  assert.deepEqual(
    skillsFromResult({
      data: [
        {
          cwd: "/workspace",
          skills: [
            {
              name: "review",
              description: "Review the current change",
              path: "/skills/review/SKILL.md",
              enabled: true,
            },
            {
              name: "disabled",
              description: "Do not show",
              path: "/skills/disabled/SKILL.md",
              enabled: false,
            },
            { name: "missing-path", description: "", enabled: true },
          ],
        },
        {
          cwd: "/other",
          skills: [{
            name: "other",
            description: "Wrong cwd",
            path: "/skills/other/SKILL.md",
            enabled: true,
          }],
        },
      ],
    }, "/workspace"),
    [{
      name: "review",
      description: "Review the current change",
      path: "/skills/review/SKILL.md",
    }],
  );
});
