## 费用说明

volcengine-ai-mediakit 作为 Agent-Skill 不收取额外费用。但在通过该 Skill 驱动音视频加工处理的过程中，会调用火山引擎视频点播后端的各项资源。在使用过程中，产生的费用主要由以下三部分组成：

- **媒资存储费用**：所有通过该 Skill 上传的原始素材，以及处理后生成的成品视频，均存储在您的视频点播空间中，根据存储文件的占用空间（GB）按日计费。详见[媒资存储计费](https://www.volcengine.com/docs/4/76542?lang=zh)。
- **视频处理费用**： 这是费用的核心部分，根据您驱动 Skill 执行的任务类型有所不同：
  - **云剪辑**：根据输出视频的分辨率和时长计费，详见[视频剪辑计费](https://www.volcengine.com/docs/4/1941016?lang=zh)。
  - **单任务处理**：视频超分、插帧等 AI 任务将根据任务的处理规格及时长独立计费，详见[媒体处理计费](https://www.volcengine.com/docs/4/1941013?lang=zh)。
- **流量费用**：当您通过处理产物的播放地址观看或分发视频时，会产生下行流量。
  - 若您在视频点播中[配置加速域名](https://www.volcengine.com/docs/4/177122)，会产生[分发加速计费](https://www.volcengine.com/docs/4/1941015?lang=zh)。
  - 若您未在视频点播中配置加速域名，则会产生[存储流出](https://www.volcengine.com/docs/4/76542?lang=zh#%E5%AD%98%E5%82%A8%E6%B5%81%E5%87%BA)费用。