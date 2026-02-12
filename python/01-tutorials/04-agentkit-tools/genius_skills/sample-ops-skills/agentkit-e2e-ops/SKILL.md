---
name: agentkit-e2e-ops
description: Deploy and test a stock analysis assistant agent using AgentKit. This skill automates the deployment workflow and verifies the agent's functionality.
---

# AgentKit E2E Ops

## Overview

This skill automates the end-to-end process of deploying a stock analysis assistant agent using AgentKit. It covers searching for the template, deploying it, agreeing to terms, testing the agent, and verifying the results.

## Workflow

To deploy the stock analysis assistant agent, navigate to the AgentKit console at:

```
https://console.volcengine.com/agentkit/region:agentkit+cn-beijing/application
```


To execute this task, use the `browser_run_code` tool with the following Playwright script:

```javascript
async (page) => {
  // Set variables
  const inputMessage = "查询：小米股票 当前价格";
  const sampleName = "股票智能分析助手";

  // Click on the search box in the application marketplace
  const searchBox = await page.findByPlaceholderText(/请输入名称、标签或者描述进行搜索/i);
  await searchBox.click();

  // Enter the sample name
  await searchBox.fill(sampleName);

  // Click on the stock analysis assistant template
  await page.findByText(sampleName).click();
  await page.waitForLoadState('networkidle');

  // Click on the one-click deploy button
  await page.findByRole('button', { name: '一键部署' }).click();
  await page.waitForLoadState('networkidle');

  // Agree to the terms
  await page.findByText('产品处于公测/邀测阶段，我已阅读同意').click();

  // Click on the create button
  await page.findByRole('button', { name: '创建' }).click();
  await page.waitForLoadState('networkidle');

  // Confirm creation with cost awareness
  await page.findByRole('button', { name: '我已知悉，确认创建' }).click();
  await page.waitForLoadState('networkidle');

  // Go to runtime debugging
  await page.findByRole('button', { name: /前往智能体运行时（runtime）调试/i }).click();
  await page.waitForLoadState('networkidle');

  // Wait for deployment to complete
  await page.waitForTimeout(5000);

  // Wait for quick deployment info to appear
  await page.waitForSelector('text="快速调用"');
  await page.waitForSelector('text="公网域名"');
  await page.waitForSelector('text="API key"');

  // Click on online test
  await page.findByRole('button', { name: '在线测试' }).click();
  await page.waitForLoadState('networkidle');

  // Click on the message input box
  const messageInput = await page.findByRole('textbox', { name: /message input/i });
  await messageInput.click();

  // Enter the query
  await messageInput.fill(inputMessage);
  await page.waitForLoadState('networkidle');

  // Send the message
  await page.findByRole('button', { name: /send message/i }).click();
  await page.waitForLoadState('networkidle');

  // Wait for events to appear
  await page.waitForSelector('text="events"');
  await page.waitForSelector('text="0"');

  // Verify no errors and content is returned
  const conversationWindow = await page.locator('div[role="dialog"]');
  await conversationWindow.waitFor({ state: 'visible' });
  const hasError = await conversationWindow.locator('text="报错"').count() > 0;
  if (hasError) {
    throw new Error('Conversation window has errors');
  }
  const hasContent = await conversationWindow.locator('div[aria-label="message"]').count() > 1;
  if (!hasContent) {
    throw new Error('No content returned in conversation');
  }

  // Click on execution process
  await page.click('text="执行过程"');

  // Verify execution process contains web_search and stock price info
  const executionProcess = await page.locator('text="执行过程"');
  await executionProcess.waitFor({ state: 'visible' });
  await page.waitForSelector('text="web_search"');
  const hasStockInfo = await page.locator('text="小米股价"').count() > 0;
  if (!hasStockInfo) {
    throw new Error('Execution process does not contain Xiaomi stock price info');
  }
}
```

## Resources

- `scripts/deploy-stock-assistant.js`: Original test script using @pagepass/test framework