# 计费说明（价格参考）

| 支持的地域           | 算子服务 & 模型名称                       | 条件                                                                     | 单价       |
| :-------------- | :-------------------------------- | :--------------------------------------------------------------------- | :------- |
| 华北2（北京） 华东2（上海） | \* 算子服务：视频修复（`las_video_inpaint`） | 普通检测模式-pixel_replace修复模式，即:`inpainting_backend=pixel_replace` 且 `detection_precise_mode=false`    | 1.2 元/分钟 |
| <br />          | <br />                            | 普通检测模式-pixel_generate修复模式，即:`inpainting_backend=inpaint_generate` 且 `detection_precise_mode=false` | 1.6 元/分钟 |
| <br />          | <br />                            | 精准检测模式-pixel_replace修复模式，即:`inpainting_backend=pixel_replace` 且 `detection_precise_mode=true`     | 2.8 元/分钟 |
| <br />          | <br />                            | 精准检测模式-pixel_generate修复模式，即`inpainting_backend=inpaint_generate` 且 `detection_precise_mode=true`  | 3.2 元/分钟 |

