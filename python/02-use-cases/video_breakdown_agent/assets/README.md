# 技术架构图

## Mermaid 流程图代码

您可以使用以下 Mermaid 代码生成技术架构图，或使用绘图工具创建自定义架构图。

### Multi-Agent 架构流程图

```mermaid
graph TD
    User[用户输入视频URL/本地文件] --> RootAgent[Root Agent 主编排器小视]
    
    RootAgent --> BreakdownAgent[Breakdown Agent<br/>分镜拆解]
    RootAgent --> HookAnalyzer[Hook Analyzer Agent<br/>钩子分析]
    RootAgent --> ReportGen[Report Generator Agent<br/>报告生成]
    RootAgent --> SearchAgent[Search Agent<br/>联网搜索]
    
    BreakdownAgent --> ProcessVideo[process_video<br/>FFmpeg预处理+ASR]
    BreakdownAgent --> AnalyzeVision[analyze_segments_vision<br/>LiteLLM视觉分析]
    BreakdownAgent --> AnalyzeBGM[analyze_bgm<br/>背景音乐分析]
    BreakdownAgent --> VideoUpload[video_upload_to_tos<br/>TOS上传]
    
    ProcessVideo --> SessionState[(Session State<br/>breakdown_result)]
    
    SessionState --> HookAnalyzer
    HookAnalyzer --> HookAnalysis[hook_analysis_agent<br/>Vision模型多模态分析]
    HookAnalysis --> HookFormat[hook_format_agent<br/>JSON格式化校验]
    HookFormat --> SessionState2[(Session State<br/>hook_analysis)]
    
    SessionState --> ReportGen
    SessionState2 --> ReportGen
    ReportGen --> GenerateReport[generate_video_report<br/>Markdown报告生成]
    GenerateReport --> FinalReport[(Session State<br/>final_report)]
    
    SearchAgent --> WebSearch[web_search<br/>实时信息搜索]
    
    style RootAgent fill:#e1f5ff
    style BreakdownAgent fill:#fff4e1
    style HookAnalyzer fill:#ffe1f5
    style ReportGen fill:#e1ffe1
    style SearchAgent fill:#f5e1ff
    style SessionState fill:#ffd700
    style SessionState2 fill:#ffd700
    style FinalReport fill:#ffd700
```

### 数据流转图

```mermaid
sequenceDiagram
    participant User as 用户
    participant Root as Root Agent
    participant Breakdown as Breakdown Agent
    participant Hook as Hook Analyzer
    participant Report as Report Generator
    participant State as Session State
    
    User->>Root: 上传视频/提供URL
    Root->>Breakdown: 委派分镜拆解任务
    
    Breakdown->>Breakdown: FFmpeg视频预处理
    Breakdown->>Breakdown: 火山ASR语音识别
    Breakdown->>Breakdown: 提取关键帧
    Breakdown->>Breakdown: LiteLLM视觉分析
    Breakdown->>State: 写入 breakdown_result
    Breakdown->>Root: 返回分镜数据
    
    Root->>Hook: 委派钩子分析任务
    Hook->>State: 读取 breakdown_result
    Hook->>Hook: 提取前3秒分镜
    Hook->>Hook: Vision模型多模态分析
    Hook->>Hook: JSON格式化校验
    Hook->>State: 写入 hook_analysis
    Hook->>Root: 返回钩子评分
    
    Root->>Report: 委派报告生成任务
    Report->>State: 读取 breakdown_result
    Report->>State: 读取 hook_analysis
    Report->>Report: 整合数据生成Markdown
    Report->>State: 写入 final_report
    Report->>Root: 返回完整报告
    
    Root->>User: 展示分析结果
```

### 火山引擎组件集成图

```mermaid
graph LR
    Agent[Video Breakdown Agent] --> Ark[火山方舟模型]
    Agent --> TOS[TOS对象存储]
    Agent --> ASR[火山ASR语音识别]
    Agent --> AgentKit[AgentKit运行时]
    Agent --> WebSearch[Web Search搜索]
    
    Ark --> Model1[doubao-seed-1-6-251015<br/>主推理模型]
    Ark --> Model2[doubao-seed-1-6-vision-250815<br/>视觉分析模型]
    
    TOS --> Upload[视频/图片上传]
    TOS --> Storage[媒体资源存储]
    
    ASR --> SpeechToText[语音转文字]
    ASR --> Timeline[时间轴分段]
    
    AgentKit --> MultiAgent[Multi-Agent编排]
    AgentKit --> Memory[Session State管理]
    
    WebSearch --> Industry[行业资讯]
    WebSearch --> Trends[平台规则]
    
    style Agent fill:#e1f5ff
    style Ark fill:#fff4e1
    style TOS fill:#ffe1f5
    style ASR fill:#e1ffe1
    style AgentKit fill:#f5e1ff
    style WebSearch fill:#ffe1e1
```

## 生成架构图的方法

### 方法1：使用在线 Mermaid 编辑器

1. 访问 [Mermaid Live Editor](https://mermaid.live/)
2. 复制上述任一 Mermaid 代码
3. 粘贴到编辑器中
4. 导出为 PNG/SVG 图片
5. 保存为 `architecture.jpg` 或其他格式

### 方法2：使用绘图工具

使用 Draw.io、Figma、Excalidraw 等工具绘制自定义架构图：

**建议包含的元素：**
- Root Agent 和 4 个子 Agent
- 每个 Agent 的主要工具函数
- Session State 数据流转
- 火山引擎组件（方舟、TOS、ASR）
- 第三方组件（FFmpeg、LiteLLM）

### 方法3：使用 VS Code 插件

1. 安装 VS Code 插件：`Markdown Preview Mermaid Support`
2. 在 Markdown 文件中查看 Mermaid 图表
3. 截图保存

## 架构图说明

架构图应展示以下关键信息：

1. **Multi-Agent 协作关系**：Root Agent 如何协调 4 个子 Agent
2. **数据流转路径**：Session State 如何在 Agent 之间传递数据
3. **工具调用链路**：每个 Agent 调用哪些工具函数
4. **火山引擎集成**：使用了哪些火山产品和服务
5. **优雅降级机制**：TOS/ASR 失败时的回退路径

## 当前状态

> 架构图文件待补充。建议使用上述 Mermaid 代码生成或自行绘制后保存为 `img/architecture.jpg`。
