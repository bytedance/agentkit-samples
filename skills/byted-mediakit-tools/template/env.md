# 火山引擎 AI MediaKit（AMK）与方舟 ARK

# AMK 访问密钥（云端能力需要；裁剪/拼接/提取/合成可在缺失时自动走本地 FFmpeg）

AMK_API_KEY=

# AMK 服务端环境：仅支持 prod（生产）

AMK_ENV=prod

# 是否为除「视频理解」外的异步请求自动注入 8 位 client_token（幂等）；仅支持 true 或 false

AMK_ENABLE_CLIENT_TOKEN=false

# 方舟 OpenAPI 密钥（可选；使用 understand_video_content 视频理解时必填）

ARK_API_KEY=

# 方舟模型 ID（可选；使用 understand_video_content 视频理解时必填，对应请求体 model 字段）

ARK_MODEL_ID=

# 控制台参考（勿将真实密钥提交到仓库）

# AI MediaKit：https://console.volcengine.com/imp/ai-mediakit/

# 方舟模型与密钥：https://console.volcengine.com/ark/region:ark+cn-beijing/model/detail?Id=doubao-seed-1-8
