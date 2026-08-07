import { Agent } from '@mastra/core/agent';
import { mockBeijingTravelSearchTool } from '../tools/beijing-travel-search';

const arkModel = {
  id: 'ark/ep-20260721114242-nwzds',
  url: 'https://ark.cn-beijing.volces.com/api/v3',
  apiKey: process.env.ARK_API_KEY,
} as const;

export const travelAgent = new Agent({
  id: 'travel-agent',
  name: 'Travel Agent',
  description: 'A simple conversational travel planning agent.',
  metadata: {
    suggestedPrompts: [
      '我想带父母去北京玩 3 天，预算 3000 元，帮我安排轻松一点的路线',
      '我想去日本玩 5 天，帮我安排轻松一点的行程',
      '带父母去云南旅行，有什么路线建议？',
      '第一次去欧洲，预算有限，怎么规划？',
    ],
  },
  instructions: `你是一个中文旅游规划助手，通过对话帮助用户做旅行规划。

你有一个 mockBeijingTravelSearchTool 工具，只能检索内置的北京旅游 mock 静态资料。用户询问北京旅行、北京景点、北京美食、北京交通或北京预算时，优先调用这个工具，再基于工具结果组织回答。

能力边界：
- 不调用真实联网能力，也不要声称查询了实时航班、酒店、天气、门票、预约或新闻。
- 使用 mockBeijingTravelSearchTool 时，必须说明资料来自内置 mock 静态数据，不是实时搜索结果。
- 对非北京目的地，只能基于常识给规划建议，不要假装调用了北京 mock 工具。

你的回答风格：
- 先用 1-3 个问题确认目的地、天数、预算、出行人群、偏好；信息足够时直接给方案。
- 给行程时按天拆分，包含上午、下午、晚上，以及交通和节奏建议。
- 明确标注哪些内容是常识性建议或示例价格，提醒用户出行前自行核验实时信息。
- 方案要实用、简洁，优先考虑动线顺、少折腾、安全和预算。
- 如果用户只是在闲聊，也自然地引导到旅行偏好。`,
  model: arkModel,
  defaultOptions: {
    maxSteps: 3,
  },
  tools: {
    mockBeijingTravelSearchTool,
  },
});
