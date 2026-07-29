# 评测模块验证记录

评测模块采用“评测集 + Runtime 评测对象 + LLM 评估器 + Code 评估器 + 实验”的组合进行验证。完整操作、字段映射、可复制代码和验收结果见 [evaluation/README.md](../evaluation/README.md)。

核心结论：实验 `jilidemo` 已成功驱动主 Runtime 执行 4 条样例；Runtime 成功率 4/4，确定性 Code 评估器通过 4/4，LLM 评估器通过 3/4。Sandbox 样例的 LLM 评分为 0 属于语义评估器误判，确定性计算结果已由 Code 评估器验证通过。
