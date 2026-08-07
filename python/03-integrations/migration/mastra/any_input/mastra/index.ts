import { Mastra } from '@mastra/core/mastra';
import { travelAgent } from './agents/agent';

export const mastra = new Mastra({
  agents: {
    travelAgent,
  },
});
