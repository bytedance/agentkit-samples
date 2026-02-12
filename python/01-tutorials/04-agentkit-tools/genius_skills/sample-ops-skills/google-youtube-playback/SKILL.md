---
name: google-youtube-playback
description: Search for a song on Google, navigate to the YouTube result, and play the video in full screen. Use this skill to automate playing specific YouTube videos via Google search.
---

# Google Youtube Playback

## Overview

This skill automates the process of searching for a specific song on Google, clicking the corresponding YouTube search result, and playing the video in full screen mode. It's useful for quickly accessing and playing music videos without manual browsing.

## Workflow

To execute this task, use the `browser_run_code` tool with the following Playwright script:

```javascript
async (page) => {
  // Navigate to Google
  await page.goto("https://www.google.com.hk/");
  await page.waitForLoadState('networkidle');

  // Click on the search box
  const searchBox = await page.findByRole('combobox', { name: '搜索' });
  await searchBox.click();

  // Enter search query
  await searchBox.fill("music Aphrodite's Child Rain and Tears");
  await page.waitForLoadState('networkidle');

  // Click on the first YouTube result
  const youtubeResult = await page.locator('a:has(div:has-text("YouTube"))').first();
  await youtubeResult.click();
  await page.waitForLoadState('networkidle');

  // Click on the fullscreen button
  const fullscreenButton = await page.locator('button[aria-label="全屏"]').first();
  await fullscreenButton.click();
}
```

## Alternative Step-by-Step Approach

If you prefer to use individual playwright_tools functions, follow these steps:

1. **Navigate to Google**:
   ```
   browser_navigate(url="https://www.google.com.hk/")
   ```

2. **Click on the search box**:
   ```
   browser_click(element="Google搜索输入栏", ref="")  // Note: ref should be obtained from page snapshot
   ```

3. **Enter search query**:
   ```
   browser_type(element="Google搜索输入栏", ref="", text="music Aphrodite's Child Rain and Tears", submit=false)
   ```

4. **Click on the first YouTube result**:
   ```
   browser_click(element="第一个YouTube搜索结果", ref="")
   ```

5. **Click on the fullscreen button**:
   ```
   browser_click(element="全屏图标按钮", ref="")
   ```

## Resources

- `scripts/play-video.js`: Original test script using @pagepass/test framework