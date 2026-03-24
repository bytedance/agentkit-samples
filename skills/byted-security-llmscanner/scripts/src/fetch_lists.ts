import * as https from 'https';
import axios from 'axios';
import { loadConfig, getToken, getCachedData, saveCachedData, SUITE_CACHE_FILE, ASSET_CACHE_FILE, AGENT_CACHE_FILE, OPENCLAW_CACHE_FILE } from './common';

// 模态类型中文映射
const MODAL_TYPE_MAP: Record<string, string> = {
  'text2text': '文生文',
  'image2text': '图文生文',
  'text2image': '文生图',
};

// 将模态类型数组转换为中文描述
function formatModalTypes(modalTypes: string[]): string {
  if (!modalTypes || modalTypes.length === 0) {
    return '';
  }
  return modalTypes.map(mt => MODAL_TYPE_MAP[mt] || mt).join('、');
}

interface Suite {
  EvalSuiteID?: string;
  EvalSuiteName?: string;
  QuestionCount?: number;
  Description?: string;
  ModalTypes?: string[];
}

interface ModelAsset {
  AssetID?: string;
  Name?: string;
  ModelID?: string;
  ModalTypes?: string[];
}

interface AgentAsset {
  ID?: string;
  Name?: string;
  Platform?: string;
  ModalTypes?: string[];
}

interface OpenClawAsset {
  ID?: string;
  Name?: string;
  PlatformType?: string;
  ModalTypes?: string[];
}

async function fetchSuites(token: string, config: any, modalTypes?: string[]): Promise<any> {
  const cacheTtl = parseInt(config.cache_ttl || '3600', 10);

  // 使用固定的缓存文件
  const cached = getCachedData<any>(SUITE_CACHE_FILE, cacheTtl);
  if (cached) {
    // 如果有缓存，在内存中过滤
    if (modalTypes && modalTypes.length > 0) {
      const allData = cached.Result?.Data || [];
      const filteredData = allData.filter((item: any) => {
        const itemModalTypes = item.ModalTypes || [];
        return modalTypes.some(mt => itemModalTypes.includes(mt));
      });
      return {
        ...cached,
        Result: {
          ...cached.Result,
          TotalCount: filteredData.length,
          PageSize: filteredData.length,
          Data: filteredData,
        },
      };
    }
    return cached;
  }

  try {
    const allData: any[] = [];
    let pageNumber = 1;
    const pageSize = 100;
    let totalCount = 0;
    let responseMetadata: any = {};

    // 总是查询所有模态类型，然后在客户端进行过滤
    const filterModalTypes = ['text2text', 'image2text', 'text2image'];

    while (true) {
      const response = await axios.post(
        `${config.host}${config.api_prefix}/ListEvalSuite`,
        {
          PageNumber: pageNumber,
          PageSize: pageSize,
          Filter: { ModalTypes: filterModalTypes },
        },
        {
        proxy: false,
          headers: {
            Authorization: `Bearer ${token}`,
            'Content-Type': 'application/json; charset=UTF-8',
          },
          timeout: 10000,
          httpsAgent: new https.Agent({ rejectUnauthorized: false }),
        }
      );

      responseMetadata = response.data.ResponseMetadata;
      const result = response.data.Result || {};
      const pageData = result.Data || [];
      totalCount = result.TotalCount || 0;

      if (!pageData || pageData.length === 0) {
        break;
      }

      allData.push(...pageData);

      if (allData.length >= totalCount) {
        break;
      }

      pageNumber++;
    }

    if (allData.length === 0) {
      console.error('ERROR: 未查询到可用测评集');
      process.exit(1);
    }

    // 保存完整数据到缓存
    const fullResultData = {
      ResponseMetadata: responseMetadata,
      Result: {
        TotalCount: allData.length,
        PageNumber: 1,
        PageSize: allData.length,
        Data: allData,
      },
    };

    saveCachedData(SUITE_CACHE_FILE, fullResultData);

    // 如果指定了模态类型，在内存中过滤后返回
    if (modalTypes && modalTypes.length > 0) {
      const filteredData = allData.filter((item: any) => {
        const itemModalTypes = item.ModalTypes || [];
        return modalTypes.some(mt => itemModalTypes.includes(mt));
      });
      return {
        ResponseMetadata: responseMetadata,
        Result: {
          TotalCount: filteredData.length,
          PageNumber: 1,
          PageSize: filteredData.length,
          Data: filteredData,
        },
      };
    }

    return fullResultData;
  } catch (error) {
    console.error(`ERROR: 获取测评集异常：${error}`);
    process.exit(1);
  }
}

async function fetchModels(token: string, config: any, modalTypes?: string[]): Promise<any> {
  const cacheTtl = parseInt(config.cache_ttl || '3600', 10);

  // 使用固定的缓存文件
  const cached = getCachedData<any>(ASSET_CACHE_FILE, cacheTtl);
  if (cached) {
    // 如果有缓存，在内存中过滤
    if (modalTypes && modalTypes.length > 0) {
      const allData = cached.Result?.Data || [];
      const filteredData = allData.filter((item: any) => {
        const itemModalTypes = item.ModalTypes || [];
        return modalTypes.some(mt => itemModalTypes.includes(mt));
      });
      return {
        ...cached,
        Result: {
          ...cached.Result,
          TotalCount: filteredData.length,
          PageSize: filteredData.length,
          Data: filteredData,
        },
      };
    }
    return cached;
  }

  try {
    const allData: any[] = [];
    let pageNumber = 1;
    const pageSize = 100;
    let totalCount = 0;
    let responseMetadata: any = {};

    // API 不支持 ModalTypes 过滤，使用空 Filter
    while (true) {
      const response = await axios.post(
        `${config.host}${config.api_prefix}/ListModelApplication`,
        {
          PageNumber: pageNumber,
          PageSize: pageSize,
          Filter: {},
        },
        {
        proxy: false,
          headers: {
            Authorization: `Bearer ${token}`,
            'Content-Type': 'application/json; charset=UTF-8',
          },
          timeout: 10000,
          httpsAgent: new https.Agent({ rejectUnauthorized: false }),
        }
      );

      responseMetadata = response.data.ResponseMetadata;
      const result = response.data.Result || {};
      const pageData = result.Data || [];
      totalCount = result.TotalCount || 0;

      if (!pageData || pageData.length === 0) {
        break;
      }

      allData.push(...pageData);

      if (allData.length >= totalCount) {
        break;
      }

      pageNumber++;
    }

    if (allData.length === 0) {
      console.warn('WARN: 未查询到可用模型资产');
    }

    // 保存完整数据到缓存
    const fullResultData = {
      ResponseMetadata: responseMetadata,
      Result: {
        TotalCount: allData.length,
        PageNumber: 1,
        PageSize: allData.length,
        Data: allData,
      },
    };

    saveCachedData(ASSET_CACHE_FILE, fullResultData);

    // 如果指定了模态类型，在内存中过滤后返回
    if (modalTypes && modalTypes.length > 0) {
      const filteredData = allData.filter((item: any) => {
        const itemModalTypes = item.ModalTypes || [];
        return modalTypes.some(mt => itemModalTypes.includes(mt));
      });
      return {
        ResponseMetadata: responseMetadata,
        Result: {
          TotalCount: filteredData.length,
          PageNumber: 1,
          PageSize: filteredData.length,
          Data: filteredData,
        },
      };
    }

    return fullResultData;
  } catch (error) {
    console.error(`ERROR: 获取模型资产异常：${error}`);
    process.exit(1);
  }
}

async function fetchAgents(token: string, config: any, modalTypes?: string[]): Promise<any> {
  const cacheTtl = parseInt(config.cache_ttl || '3600', 10);

  // 使用固定的缓存文件
  const cached = getCachedData<any>(AGENT_CACHE_FILE, cacheTtl);
  if (cached) {
    // 如果有缓存，在内存中过滤
    if (modalTypes && modalTypes.length > 0) {
      const allData = cached.Result?.Data || [];
      const filteredData = allData.filter((item: any) => {
        const itemModalTypes = item.ModalTypes || [];
        return modalTypes.some(mt => itemModalTypes.includes(mt));
      });
      return {
        ...cached,
        Result: {
          ...cached.Result,
          TotalCount: filteredData.length,
          PageSize: filteredData.length,
          Data: filteredData,
        },
      };
    }
    return cached;
  }

  try {
    const allData: any[] = [];
    let pageNumber = 1;
    const pageSize = 100;
    let totalCount = 0;
    let responseMetadata: any = {};

    while (true) {
      const response = await axios.post(
        `${config.host}${config.api_prefix}/ListAgent`,
        {
          PageNumber: pageNumber,
          PageSize: pageSize,
          Filter: {},
        },
        {
        proxy: false,
          headers: {
            Authorization: `Bearer ${token}`,
            'Content-Type': 'application/json; charset=UTF-8',
          },
          timeout: 10000,
          httpsAgent: new https.Agent({ rejectUnauthorized: false }),
        }
      );

      responseMetadata = response.data.ResponseMetadata;
      const result = response.data.Result || {};
      const pageData = result.Data || [];
      totalCount = result.TotalCount || 0;

      if (!pageData || pageData.length === 0) {
        break;
      }

      allData.push(...pageData);

      if (allData.length >= totalCount) {
        break;
      }

      pageNumber++;
    }

    if (allData.length === 0) {
      console.warn('WARN: 未查询到可用智能体资产');
    }

    // 保存完整数据到缓存
    const fullResultData = {
      ResponseMetadata: responseMetadata,
      Result: {
        TotalCount: allData.length,
        PageNumber: 1,
        PageSize: allData.length,
        Data: allData,
      },
    };

    saveCachedData(AGENT_CACHE_FILE, fullResultData);

    // 如果指定了模态类型，在内存中过滤后返回
    if (modalTypes && modalTypes.length > 0) {
      const filteredData = allData.filter((item: any) => {
        const itemModalTypes = item.ModalTypes || [];
        return modalTypes.some(mt => itemModalTypes.includes(mt));
      });
      return {
        ResponseMetadata: responseMetadata,
        Result: {
          TotalCount: filteredData.length,
          PageNumber: 1,
          PageSize: filteredData.length,
          Data: filteredData,
        },
      };
    }

    return fullResultData;
  } catch (error) {
    console.error(`ERROR: 获取智能体资产异常：${error}`);
    process.exit(1);
  }
}

async function fetchOpenClaws(token: string, config: any, modalTypes?: string[]): Promise<any> {
  const cacheTtl = parseInt(config.cache_ttl || '3600', 10);

  // 使用固定的缓存文件
  const cached = getCachedData<any>(OPENCLAW_CACHE_FILE, cacheTtl);
  if (cached) {
    // 如果有缓存，在内存中过滤
    if (modalTypes && modalTypes.length > 0) {
      const allData = cached.Result?.Data || [];
      const filteredData = allData.filter((item: any) => {
        const itemModalTypes = item.ModalTypes || [];
        return modalTypes.some(mt => itemModalTypes.includes(mt));
      });
      return {
        ...cached,
        Result: {
          ...cached.Result,
          TotalCount: filteredData.length,
          PageSize: filteredData.length,
          Data: filteredData,
        },
      };
    }
    return cached;
  }

  try {
    const allData: any[] = [];
    let pageNumber = 1;
    const pageSize = 100;
    let totalCount = 0;
    let responseMetadata: any = {};

    while (true) {
      const response = await axios.post(
        `${config.host}${config.api_prefix}/ListOpenClaw`,
        {
          PageNumber: pageNumber,
          PageSize: pageSize,
          Filter: {},
        },
        {
        proxy: false,
          headers: {
            Authorization: `Bearer ${token}`,
            'Content-Type': 'application/json; charset=UTF-8',
          },
          timeout: 10000,
          httpsAgent: new https.Agent({ rejectUnauthorized: false }),
        }
      );

      responseMetadata = response.data.ResponseMetadata;
      const result = response.data.Result || {};
      const pageData = result.Data || [];
      totalCount = result.TotalCount || 0;

      if (!pageData || pageData.length === 0) {
        break;
      }

      allData.push(...pageData);

      if (allData.length >= totalCount) {
        break;
      }

      pageNumber++;
    }

    if (allData.length === 0) {
      console.warn('WARN: 未查询到可用OpenClaw资产');
    }

    // 保存完整数据到缓存
    const fullResultData = {
      ResponseMetadata: responseMetadata,
      Result: {
        TotalCount: allData.length,
        PageNumber: 1,
        PageSize: allData.length,
        Data: allData,
      },
    };

    saveCachedData(OPENCLAW_CACHE_FILE, fullResultData);

    // 如果指定了模态类型，在内存中过滤后返回
    if (modalTypes && modalTypes.length > 0) {
      const filteredData = allData.filter((item: any) => {
        const itemModalTypes = item.ModalTypes || [];
        return modalTypes.some(mt => itemModalTypes.includes(mt));
      });
      return {
        ResponseMetadata: responseMetadata,
        Result: {
          TotalCount: filteredData.length,
          PageNumber: 1,
          PageSize: filteredData.length,
          Data: filteredData,
        },
      };
    }

    return fullResultData;
  } catch (error) {
    console.error(`ERROR: 获取OpenClaw资产异常：${error}`);
    process.exit(1);
  }
}

function formatSuites(suitesData: any): Array<{ ID: string; Name: string; QuestionCount: number; Description: string; ModalTypes: string }> {
  const suites: Suite[] = suitesData.Result?.Data || [];

  return suites.map(suite => ({
    ID: suite.EvalSuiteID || '',
    Name: suite.EvalSuiteName || '',
    QuestionCount: suite.QuestionCount || 0,
    Description: suite.Description || '',
    ModalTypes: formatModalTypes(suite.ModalTypes || []),
  }));
}

function formatModels(assetsData: any): Array<{ ID: string; Name: string; ModelID: string; Description: string; ModalTypes: string }> {
  const assets: ModelAsset[] = assetsData.Result?.Data || [];

  return assets.map(asset => ({
    ID: asset.AssetID || '',
    Name: asset.Name || '',
    ModelID: asset.ModelID || '',
    Description: '',
    ModalTypes: formatModalTypes(asset.ModalTypes || []),
  }));
}

function formatAgents(agentsData: any): Array<{ ID: string; Name: string; Platform: string; Description: string; ModalTypes: string }> {
  const agents: AgentAsset[] = agentsData.Result?.Data || [];

  return agents.map(agent => ({
    ID: agent.ID || '',
    Name: agent.Name || '',
    Platform: agent.Platform || '',
    Description: '',
    ModalTypes: formatModalTypes(agent.ModalTypes || []),
  }));
}

function formatOpenClaws(openClawsData: any): Array<{ ID: string; Name: string; Platform: string; Description: string; ModalTypes: string }> {
  const openClaws: OpenClawAsset[] = openClawsData.Result?.Data || [];

  return openClaws.map(oc => ({
    ID: oc.ID || '',
    Name: oc.Name || '',
    Platform: oc.PlatformType || '',
    Description: '',
    ModalTypes: formatModalTypes(oc.ModalTypes || []),
  }));
}

async function main() {
  const args = process.argv.slice(2);
  let taskType = 'compliance'; // 默认为合规测评
  let modalTypes: string[] | undefined;

  // 解析参数
  if (args.length > 0) {
    const firstArg = args[0].trim();

    // 检查是否为任务类型
    if (firstArg === 'compliance' || firstArg === 'security') {
      taskType = firstArg;
      if (args.length > 1) {
        const modalTypesStr = args[1].trim();
        if (modalTypesStr) {
          modalTypes = modalTypesStr.split(',').map(m => m.trim());

          // 验证 ModalTypes
          const validModalTypes = ['text2text', 'image2text', 'text2image'];
          for (const mt of modalTypes) {
            if (!validModalTypes.includes(mt)) {
              console.error(`ERROR: 无效的模态类型 '${mt}'，有效值为：${validModalTypes.join(', ')}`);
              process.exit(1);
            }
          }
        }
      }
    } else {
      // 不是任务类型，当作模态类型处理
      modalTypes = firstArg.split(',').map(m => m.trim());

      // 验证 ModalTypes
      const validModalTypes = ['text2text', 'image2text', 'text2image'];
      for (const mt of modalTypes) {
        if (!validModalTypes.includes(mt)) {
          console.error(`ERROR: 无效的模态类型 '${mt}'，有效值为：${validModalTypes.join(', ')}`);
          process.exit(1);
        }
      }
    }
  }

  const config = loadConfig();
  const token = await getToken(config);

  const suitesData = await fetchSuites(token, config, modalTypes);
  const modelsData = await fetchModels(token, config, modalTypes);
  const agentsData = await fetchAgents(token, config, modalTypes);
  const openClawsData = await fetchOpenClaws(token, config, modalTypes);

  const suites = formatSuites(suitesData);
  const models = formatModels(modelsData);
  const agents = formatAgents(agentsData);
  const openClaws = formatOpenClaws(openClawsData);

  if (taskType === 'compliance') {
    // 合规测评：返回所有资源
    const result = {
      suites,
      models,
      agents,
      openClaws,
    };
    console.log(JSON.stringify(result, null, 2));
  } else if (taskType === 'security') {
    // 安全测评：只返回测评对象（models, agents, openClaws）
    const result = {
      models,
      agents,
      openClaws,
    };
    console.log(JSON.stringify(result, null, 2));
  }
}

main().catch(error => {
  console.error(`ERROR: ${error}`);
  process.exit(1);
});
