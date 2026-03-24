import axios from 'axios';
import * as https from 'https';
import { loadConfig, getToken, clearCache, ASSET_CACHE_FILE } from './common';

interface QueryAssetResponse {
  Result?: {
    Data?: Array<{
      AssetID?: string;
      Name?: string;
      ModelID?: string;
    }>;
  };
}

async function queryAssetByModelId(token: string, modelId: string, name: string, config: any): Promise<string | null> {
  try {
    const response = await axios.post(
      `${config.host}${config.api_prefix}/ListModelApplication`,
      {
        PageNumber: 1,
        PageSize: 100,
        Filter: { ModalTypes: ['text2text'] },
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

    const data: QueryAssetResponse = response.data;
    const assets = data.Result?.Data || [];

    const matched = assets.find(
      asset => asset.ModelID === modelId && asset.Name === name
    );

    if (!matched) {
      return null;
    }

    return matched.AssetID || null;
  } catch (error) {
    console.error(`ERROR: 查询资产异常：${error}`);
    process.exit(1);
  }
}

async function updateAssetModel(
  token: string,
  assetId: string,
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
        console.log(`INFO: 第 ${attempt} 次尝试更新资产...`);
      }

      console.log('INFO: 正在调用更新资产接口...');

      const response = await axios.post(
        `${config.host}${config.api_prefix}/UpdateModel`,
        {
          Name: name,
          Implement: 'openai',
          ModelID: modelId,
          BaseUrl: baseUrl,
          ApiKey: apiKey,
          ModalTypes: modalTypes,
          Param: '',
          AppRole: '',
          Remark: '',
          AssetID: assetId,
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
        console.error(`ERROR: 更新资产失败：${errMsg}`);
        process.exit(1);
      }

      const result = response.data.Result?.Data;
      if (result === 'success') {
        console.log('INFO: 资产更新成功');
        return true;
      } else {
        console.error('ERROR: 更新资产失败，返回结果不正确');
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
        continue
      }
    }
  }

  // 所有重试都失败
  console.error(`ERROR: 更新资产异常（已重试 ${maxRetries} 次）：${lastError}`);
  if (lastError.response) {
    console.error(`ERROR: 响应状态码：${lastError.response.status}`);
    console.error(`ERROR: 响应数据：${JSON.stringify(lastError.response.data)}`);
  }
  process.exit(1);
}

async function main() {
  const args = process.argv.slice(2);
  if (args.length !== 4 && args.length !== 5) {
    console.log('用法：npx ts-node src/update_asset_model.ts <Name> <ModelID> <BaseUrl> <ApiKey> [ModalTypes]');
    console.log('\n参数说明：');
    console.log('  Name       : 资产名称，例如 ark_deepseek-v3_1');
    console.log('  ModelID    : 模型的唯一标识符，例如 ep-20250325142301-ljxvm');
    console.log('  BaseUrl    : 模型API地址，例如 https://ark-cn-beijing.bytedance.net/api/v3');
    console.log('  ApiKey     : 模型的API密钥');
    console.log('  ModalTypes : 模态类型（可选，默认为 text2text），多个用逗号分隔');
    console.log('                - text2text  : 文生文');
    console.log('                - image2text : 图文生文');
    console.log('                - text2image : 文生图');
    console.log('\n示例：');
    console.log('  npx ts-node src/update_asset_model.ts my-model ep-xxx https://api.xxx.com sk-xxx');
    console.log('  npx ts-node src/update_asset_model.ts my-model ep-xxx https://api.xxx.com sk-xxx text2text,image2text');
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
  console.log('大模型测评资产更新工具');
  console.log('='.repeat(50));
  console.log(`\n【Step 1】资产信息`);
  console.log(`  Name       ：${name}`);
  console.log(`  ModelID    ：${modelId}`);
  console.log(`  BaseUrl    ：${baseUrl}`);
  console.log(`  ApiKey     ：${'*'.repeat(apiKey.length)}`);
  console.log(`  ModalTypes ：${modalTypes.join(', ')}`);

  const config = loadConfig();

  console.log('\n【Step 2】获取鉴权Token...');
  const token = await getToken(config);
  console.log('INFO: Token获取成功');

  console.log('\n【Step 3】查询资产ID...');
  const assetId = await queryAssetByModelId(token, modelId, name, config);
  if (!assetId) {
    console.error(`ERROR: 未找到匹配的资产（Name: ${name}, ModelID: ${modelId}）`);
    console.error('💡 提示：请先创建资产：npx ts-node src/create_asset_model.ts <Name> <ModelID> <BaseUrl> <ApiKey> [ModalTypes]');
    process.exit(1);
  }
  console.log(`INFO: 找到资产ID：${assetId}`);

  console.log('\n【Step 4】更新资产...');
  await updateAssetModel(token, assetId, name, modelId, baseUrl, apiKey, modalTypes, config);
  console.log('INFO: 资产更新成功');

  console.log('\n【Step 5】清除资产缓存...');
  clearCache(ASSET_CACHE_FILE);
  console.log('INFO: 缓存已清除');

  console.log('\n' + '='.repeat(50));
  console.log('✅ 资产更新完成！');
  console.log('='.repeat(50));
}

main().catch(error => {
  console.error(`ERROR: ${error}`);
  process.exit(1);
});
