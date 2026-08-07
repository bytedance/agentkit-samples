import { createTool } from '@mastra/core/tools';
import { z } from 'zod';

const BEIJING_TRAVEL_DATA = {
  attractions: [
    {
      name: '故宫博物院',
      area: '东城区',
      tags: ['历史文化', '博物馆', '经典景点'],
      tip: '适合上午安排，参观前需要自行核验开放日和预约要求。',
    },
    {
      name: '天坛公园',
      area: '东城区',
      tags: ['历史文化', '公园', '轻松步行'],
      tip: '适合和前门、东城餐饮串联，步行量可控。',
    },
    {
      name: '什刹海胡同',
      area: '西城区',
      tags: ['胡同', '散步', '夜景'],
      tip: '适合下午到傍晚慢走，带长辈时减少骑行和长距离折返。',
    },
    {
      name: '国家博物馆',
      area: '东城区',
      tags: ['博物馆', '历史文化', '室内'],
      tip: '适合天气不好或想降低体力消耗时安排。',
    },
    {
      name: '颐和园',
      area: '海淀区',
      tags: ['皇家园林', '湖景', '经典景点'],
      tip: '园区较大，轻松玩法建议只选核心路线。',
    },
  ],
  foods: [
    {
      name: '北京烤鸭',
      scene: '正餐',
      tip: '适合安排在行程第一晚或最后一晚，价格以到店为准。',
    },
    {
      name: '炸酱面',
      scene: '午餐',
      tip: '适合穿插在东城、西城胡同行程中，节省时间。',
    },
    {
      name: '铜锅涮肉',
      scene: '晚餐',
      tip: '适合秋冬或长辈同行，注意排队和口味偏好。',
    },
    {
      name: '豆汁/焦圈',
      scene: '小吃',
      tip: '地域特色强，建议作为体验项，不要强行安排为正餐。',
    },
  ],
  itineraryHints: [
    '第1天：天安门周边 + 故宫博物院 + 什刹海胡同，晚上安排北京烤鸭或铜锅涮肉。',
    '第2天：天坛公园 + 前门/大栅栏 + 国家博物馆，节奏偏文化和室内。',
    '第3天：颐和园半日 + 海淀或西城轻松餐饮，下午预留返程缓冲。',
  ],
  transportTips: [
    '核心城区优先地铁，跨城区行程尽量减少来回折返。',
    '带父母或长辈时，每天安排 1-2 个核心区域，并预留午休。',
    '热门景点周边打车上下车点可能绕行，建议预留步行和安检时间。',
  ],
  budgetNotes: [
    '常规舒适型玩法可按住宿、餐饮、门票/预约、交通四类拆分预算。',
    '示例价格只能作为常识性估算，真实价格、门票、开放时间和预约规则需要出行前核验。',
  ],
};

export const mockBeijingTravelSearchTool = createTool({
  id: 'mock_beijing_travel_search',
  description:
    'Search a static mock dataset for Beijing travel planning. It does not access the internet or real-time booking, weather, ticket, hotel, or traffic data.',
  inputSchema: z.object({
    query: z.string().describe('User travel-planning question or search query.'),
    focus: z
      .enum(['general', 'attractions', 'food', 'transport', 'budget', 'itinerary'])
      .optional()
      .describe('Optional focus area for the mock Beijing travel search.'),
  }),
  outputSchema: z.object({
    query: z.string(),
    focus: z.string(),
    source: z.literal('mock_static_beijing_travel_dataset'),
    summary: z.string(),
    attractions: z.array(
      z.object({
        name: z.string(),
        area: z.string(),
        tags: z.array(z.string()),
        tip: z.string(),
      }),
    ),
    foods: z.array(
      z.object({
        name: z.string(),
        scene: z.string(),
        tip: z.string(),
      }),
    ),
    itineraryHints: z.array(z.string()),
    transportTips: z.array(z.string()),
    budgetNotes: z.array(z.string()),
    caveats: z.array(z.string()),
  }),
  execute: async ({ query, focus = 'general' }) => ({
    query,
    focus,
    source: 'mock_static_beijing_travel_dataset' as const,
    summary:
      '这是一个仅用于迁移实验的北京旅游 mock 搜索结果，覆盖经典景点、餐饮、交通节奏和预算提醒。',
    attractions: [...BEIJING_TRAVEL_DATA.attractions],
    foods: [...BEIJING_TRAVEL_DATA.foods],
    itineraryHints: [...BEIJING_TRAVEL_DATA.itineraryHints],
    transportTips: [...BEIJING_TRAVEL_DATA.transportTips],
    budgetNotes: [...BEIJING_TRAVEL_DATA.budgetNotes],
    caveats: [
      '本工具不联网，不查询实时航班、酒店、天气、门票、预约或新闻。',
      '输出中的价格和开放信息只能作为规划提示，不能视为实时事实。',
    ],
  }),
});
