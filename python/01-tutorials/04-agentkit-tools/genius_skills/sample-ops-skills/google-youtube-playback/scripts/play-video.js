import { describe, it, before } from "@pagepass/test";

describe('测试套件 2026/2/12 15:07:47', () => {
  // beforeAll
  before(async ({ page, arete }) => {
    await page.goto("https://www.google.com.hk/");
    await arete.waitForNetworkIdle({ timeout: 5000 });
  });
  it("Skill测试用例 2026/2/12 15:07:47", async ({ page, arete }) => {
    await arete.aiRace(
      page.findByRole('combobox', { name: '搜索' }),
      "Google搜索输入栏 -> 位于Google标志下方，搜索框组件的中间区域，左侧为搜索图标，右侧为语音图标和镜头图标 + 用于输入搜索关键词以进行搜索操作"
    ).click({"waitNetworkIdleAfterStep":false});

    await arete.aiRace(
      page.findByRole('combobox', { name: '搜索' }),
      "Google搜索输入框 -> 位于Google标志下方，左侧为搜索图标，右侧为语音图标和镜头图标 + 用于输入搜索内容以进行搜索操作(备注：优先考虑可输入文本的元素)"
    ).setValue("music Aphrodite's Child Rain and Tears", {"waitNetworkIdleAfterStep":true});

    await arete.aiRace(
      page.element("html > body:nth-of-type(1) > div:nth-of-type(3) > div:nth-of-type(1) > div:nth-of-type(12) > div:nth-of-type(1) > div:nth-of-type(2) > div:nth-of-type(2) > div:nth-of-type(1) > div:nth-of-type(1) > div:nth-of-type(1) > div:nth-of-type(1) > div:nth-of-type(1) > div:nth-of-type(1) > div:nth-of-type(1) > div:nth-of-type(1) > div:nth-of-type(1) > div:nth-of-type(2) > div:nth-of-type(1) > div:nth-of-type(1) > div:nth-of-type(1) > div:nth-of-type(3)"),
      "[带有“ABSOLUTE CHILL”“RAIN AND TEARS”及“3:18”标识的视频缩略图] -> [位于Google搜索结果的第一个YouTube条目区域内] + [用于点击打开并播放对应的Aphrodite's Child的Rain and Tears相关视频]"
    ).click({"waitNetworkIdleAfterStep":true});

    await arete.aiRace(
      "全屏图标按钮 -> 位于YouTube视频播放界面右下角 + 用于将视频切换为全屏播放模式"
    ).click({"waitNetworkIdleAfterStep":true});
  });
});