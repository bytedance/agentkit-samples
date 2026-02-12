import { describe, it, before } from "@pagepass/test";

describe('demo', () => {
  // beforeAll
  before(async ({ page, arete }) => {

  });
  it("股票智能分析助手 2026/01/21", async ({ page, arete }) => {
    arete.updateVariables({"input_message":"查询：小米股票 当前价格","sample_name":"股票智能分析助手"}, { renderTemplateStr: true });
    await arete.aiRace(
      page.findByPlaceholderText(/请输入名称、标签或者描述进行搜索/i),
      "搜索框 -> 位于“应用广场”页面中央 + 用于输入名称、标签或者描述进行搜索"
    ).click({"waitNetworkIdleAfterStep":false});

    await arete.aiRace(
      page.findByPlaceholderText(/请输入名称、标签或者描述进行搜索/i),
      "搜索框 -> 位于“应用广场”页面中部 + 用于输入名称、标签或者描述进行搜索(备注：优先考虑可输入文本的元素)"
    ).setValue("${sample_name}", {"waitNetworkIdleAfterStep":false});

    await arete.aiRace(
      page.findByText('股票智能分析助手'),
      "股票智能分析助手 -> 位于场景模板卡片中 + 用于标识该模板的名称"
    ).click({"waitNetworkIdleAfterStep":true});

    await arete.aiRace(
      page.findByRole('button', { name: '一键部署' }),
      "一键部署按钮 -> 位于模板简介下方 + 用于一键部署股票智能分析助手"
    ).click({"waitNetworkIdleAfterStep":true});

    await arete.aiRace(
      page.findByText('产品处于公测/邀测阶段，我已阅读同意'),
      "产品处于公测/邀测阶段，我已阅读同意《产品和服务测试协议》 -> 位于页面底部 + 用于确认用户已阅读并同意相关协议"
    ).click();

    await arete.aiRace(
      page.findByRole('button', { name: '创建' }),
      "创建按钮 -> 位于页面右下角 + 用于确认创建Agent应用部署"
    ).click({"waitNetworkIdleAfterStep":true});

    await arete.aiRace(
      page.findByRole('button', { name: '我已知悉，确认创建' }),
      "我已知悉，确认创建 -> 位于费用提示弹窗底部 + 用于确认创建智能体并知晓费用"
    ).click({"waitNetworkIdleAfterStep":true});

    await arete.aiRace(
      page.findByRole('button', { name: /前往智能体运行时（runtime）调试/i }),
      "前往智能体运行时（Runtime）调试按钮 -> 位于页面中间偏下位置 + 用于进行智能体运行时调试"
    ).click({"waitNetworkIdleAfterStep":true});

    await page.wait(5000)

    await arete.aiRace(
      "\"快速调用\"出现在配置信息栏下边，并且有 公网域名 和 API key"
    ).waitForVisible({"timeout":500000});

    await arete.aiRace(
      page.findByRole('button', { name: '在线测试' }),
      "在线测试按钮 -> 位于页面右上角 + 用于进行在线测试"
    ).click({"waitNetworkIdleAfterStep":true});

    await arete.aiRace(
      page.findByRole('textbox', { name: /message input/i }),
      "请输入内容 -> 位于界面底部 + 用于输入对话内容"
    ).click({"waitNetworkIdleAfterStep":false});

    await arete.aiRace(
      page.findByRole('textbox', { name: /message input/i }),
      "[请输入内容] -> 位于界面底部输入区域 + 用于输入对话内容(备注：优先考虑可输入文本的元素)"
    ).setValue("${input_message}", {"waitNetworkIdleAfterStep":true});

    await arete.aiRace(
      page.findByRole('button', { name: /send message/i }),
      "发送按钮 -> 位于输入框右侧 + 用于发送消息"
    ).click({"waitNetworkIdleAfterStep":true});

    await arete.aiWaitFor("events 那一栏有内容，序号是 0 1 2等", {"timeout":500000});

    await arete.aiAssert("对话窗口没有报错，并且有内容返回")

    await arete.aiRace(
      "点击页面的 “执行过程” 按钮"
    ).click();

    await arete.aiAssert("执行过程，有\"执行”子项目，并且 包含 “web_search\" , 然后问题的答案是 关于小米股价的")
  });
});