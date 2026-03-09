"use strict";

module.exports = {
  names: ["required-headers"],
  description: "Ensure README contains specific required headers",
  tags: ["structure"],

  function: function rule(params, onError) {
    const requiredHeaders = [
      "## 概述",
      "## 核心功能",
      "## Agent 能力",
      "## 目录结构说明",
      "## 本地运行",
      "## AgentKit 部署",
      "## 示例提示词",
      "## 效果展示",
      "## 常见问题",
      "## 代码许可"
    ];

    const content = params.lines.join("\n");

    requiredHeaders.forEach((header) => {
      if (!content.includes(header)) {
        onError({
          lineNumber: 1,
          detail: `Missing required header: "${header}"`
        });
      }
    });
  }
};