# LAS 视频精细理解（`las_long_video_understand`）计费说明

该算子主要通过底层的豆包视觉模型（如 `doubao-seed-2-0-lite` 等）进行推理，计费基于 Token 消耗。

**主要计费项**：
- 输入 Token (Prompt Tokens)：视频抽帧处理后的图片、音频转文本、以及用户文本 prompt。
- 输出 Token (Completion Tokens)：模型生成的文本结果。

由于视频长度、抽帧率、分析复杂度不同，Token 消耗量差异极大，**无法在提交前精确预估最终费用**。

*请注意：本方式的计费均为预估计费，与实际费用有差距，实际费用以运行后火山引擎产生的账单为准。*
