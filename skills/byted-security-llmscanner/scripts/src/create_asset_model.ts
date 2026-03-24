import axios from 'axios';
import * as fs from 'fs';
import * as https from 'https';
import { loadConfig, getToken, clearCache, ASSET_CACHE_FILE } from './common';

interface AssetCache {
  data?: {
    Result?: {
      Data?: Array<{
        ModelID?: string;
        Name: string;
      }>;
    };
  };
}

function checkAssetExists(modelId: string): [boolean, string | null] {
  if (!fs.existsSync(ASSET_CACHE_FILE)) {
    return [false, null];
  }

  try {
    const cacheContent = fs.readFileSync(ASSET_CACHE_FILE, 'utf-8');
    const cache: AssetCache = JSON.parse(cacheContent);

    const assets = cache.data?.Result?.Data || [];
    for (const asset of assets) {
      if (asset.ModelID === modelId) {
        return [true, asset.Name || null];
      }
    }
    return [false, null];
  } catch {
    return [false, null];
  }
}

async function createAssetModel(
  token: string,
  name: string,
  modelId: string,
  baseUrl: string,
  apiKey: string,
  modalTypes: string[],
  config: any,
  maxRetries: number = 3
): Promise<boolean> {
  let lastError: any = null;

  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      if (attempt > 1) {
        console.log(`INFO: 第 ${attempt} 次尝试创建资产...`);
      }

      console.log('INFO: 正在调用创建资产接口...');

      const response = await axios.post(
        `${config.host}${config.api_prefix}/CreateModel`,
        {
          Name: name,
          Implement: 'openai',
          ModelID: modelId,
          BaseUrl: baseUrl,
          ApiKey: apiKey,
          ModalTypes: modalTypes,
        },
        {
          headers: {
            Authorization: `Bearer ${token}`,
            'Content-Type': 'application/json; charset=UTF-8',
          },
          timeout: 300000, // 5分钟超时
          proxy: false,
          httpsAgent: new https.Agent({ rejectUnauthorized: false }),
        }
      );

      console.log('INFO: 接口调用成功，正在解析响应...');

      if (response.data.ResponseMetadata?.Error) {
        const errMsg = response.data.ResponseMetadata.Error.Message || '未知错误';
        console.error(`ERROR: 创建资产失败：${errMsg}`);
        process.exit(1);
      }

      const result = response.data.Result?.Data;
      if (result === 'success') {
        console.log('INFO: 资产资产创建成功');
        return true;
      } else {
        console.error('ERROR: 创建资产失败，返回结果不正确');
        process.exit(1);
      }
    } catch (error: any) {
      lastError = error;

      // 判断是否为超时错误
      const isTimeout = error.code === 'ECONNABORTED' || error.message?.includes('timeout');

      if (isTimeout && attempt < maxRetries) {
        console.warn(`WARN: 请求超时，将在3秒后重试 (${attempt}/${maxRetries})...`);
        await new Promise(resolve => setTimeout(resolve, 3000));
        continue;
      }

      if (attempt < maxRetries) {
        console.warn(`WARN: 请求失败，将在3秒后重试 (${attempt}/${maxRetries})...`);
        console.warn(`WARN: 错误信息：${error.message}`);
        await new Promise(resolve => setTimeout(resolve, 3000));
        continue;
      }
    }
  }

  // 所有重试都失败
  console.error(`ERROR: 创建资产异常（已重试 ${maxRetries} 次）：${lastError}`);
  if (lastError.response) {
    console.error(`ERROR: 响应状态码：${lastError.response.status}`);
    console.error(`ERROR: 响应数据：${JSON.stringify(lastError.response.data)}`);
  }
  process.exit(1);
}

async function main() {
  const args = process.argv.slice(2);
  if (args.length !== 4 && args.length !== 5) {
    console.log('用法：npx ts-node src/create_asset_model.ts <Name> <ModelID> <BaseUrl> <ApiKey> [ModalTypes]');
    console.log('\n参数说明：');
    console.log('  Name       : 资产名称，例如 ark_deepseek-v3_1');
    console.log('  ModelID    : 模型的唯一标识符，例如 ep-20250325142301-ljxar');
    console.log('  BaseUrl    : 模型API地址，例如 https://ark-cn-beijing.bytedance.net/api/v3');
    console.log('  ApiKey     : 模型的API密钥');
    console.log('  ModalTypes : 模态类型（可选，默认为 text2text），多个用逗号分隔');
    console.log('                - text2text  : 文生文');
    console.log('                - image2text : 图文生文');
    console.log('                - text2image : 文生图');
    console.log('\n示例：');
    console.log('  npx ts-node src/create_asset_model.ts my-model ep-xxx https://api.xxx.com sk-xxx');
    console.log('  npx ts-node src/create_asset_model.ts my-model ep-xxx https://api.xxx.com sk-xxx text2text,image2text');
    process.exit(1);
  }

  const [name, modelId, baseUrl, apiKey, modalTypesStr] = args.map(arg => arg.trim());

  if (!name || !modelId || !baseUrl || !apiKey) {
    console.error('ERROR: Name、ModelID、BaseUrl、ApiKey 不能为空');
    process.exit(1);
  }

  // 解析 ModalTypes，默认为 ['text2text']
  const modalTypes = modalTypesStr
    ? modalTypesStr.split(',').map(m => m.trim())
    : ['text2text'];

  // 验证 ModalTypes
  const validModalTypes = ['text2text', 'image2text', 'text2image'];
  for (const mt of modalTypes) {
    if (!validModalTypes.includes(mt)) {
      console.error(`ERROR: 无效的模态类型 '${mt}'，有效值为：${validModalTypes.join(', ')}`);
      process.exit(1);
    }
  }

  console.log('='.repeat(50));
  console.log('大模型测评资产创建工具');
  console.log('='.repeat(50));
  console.log(`\n【Step 1】资产信息`);
  console.log(`  Name       ：${name}`);
  console.log(`  ModelID    ：${modelId}`);
  console.log(`  BaseUrl    ：${baseUrl}`);
  console.log(`  ApiKey     ：${'*'.repeat(apiKey.length)}`);
  console.log(`  ModalTypes ：${modalTypes.join(', ')}`);

  const config = loadConfig();

  console.log('\n【Step 2】检查资产缓存...');
  const [exists, existingName] = checkAssetExists(modelId);
  if (exists) {
    console.log(`INFO: 模型ID '${modelId}' 的资产已存在，资产名称：${existingName}`);
    console.log('无需重复创建');
    process.exit(0);
  }
  console.log('INFO: 未发现相同模型ID的资产，继续创建...');

  console.log('\n【Step 3】获取鉴权Token...');
  const token = await getToken(config);
  console.log('INFO: Token获取成功');

  console.log('\n【Step 4】创建测评资产...');
  await createAssetModel(token, name, modelId, baseUrl, apiKey, modalTypes, config);
  console.log('INFO: 资产创建成功');

  console.log('\n【Step 5】清除资产缓存...');
  clearCache(ASSET_CACHE_FILE);
  console.log('INFO: 缓存已清除');

  console.log('\n' + '='.repeat(50));
  console.log('✅ 资产创建完成！');
  console.log('='.repeat(50));
}

main().catch(error => {
  console.error(`ERROR: ${error}`);
  process.exit(1);
});
