# 漫剧制作使用示例

## 示例1：中国神话题材（1分钟，6个分镜，智能时长）

**用户输入**：
```
请制作一个关于"孙悟空大战二郎神"的漫剧视频，国漫3D写实风格
```

**执行流程**：

### 1. 读取配置
```bash
python scripts/app_config.py
# 输出: {"video_duration_minutes": 1, "total_seconds": 60, "smart_duration": true, "duration_range": {"min": 4, "max": 15}, "duration_options": "4s ~ 15s 动态分配", "scene_count_range": {"min": 4, "max": 15}, "recommended_scene_count": 6}
```

### 2. 初始化任务
```bash
python scripts/task_manager.py init "孙悟空大战二郎神"
# 输出: {"task_folder": "{COMIC_DRAMA_OUTPUT_DIR}/task_20260222_143000_孙悟空大战二郎神/", ...}
```

### 3. 内容安全预审
- 评估风险等级：**中风险**（武侠打斗）
- 应对策略：使用委婉替代词（`spiritual energy clash` 代替 `bloody battle`）
- 告知用户后继续

### 4. 剧本生成（含智能时长分配）
- web_search: "孙悟空大战二郎神原著情节"、"二郎神杨戬能力法宝"、"西游记经典台词"
- 创作 requirements.md、plot.md、script.md
- **时长分配**（4s ~ 15s 动态范围）：

```
第一章：天宫震怒（6秒）— 花果山巅，天兵压境  ← 紧张快切，快速建立氛围
第二章：初次交锋（8秒）— 悟空与杨戬首次对决  ← 标准叙事节奏
第三章：七十二变（12秒）— 变化斗法，精彩纷呈  ← 高潮铺垫，需要更多对白
第四章：真身对决（14秒）— 以力破巧，终极交锋  ← 核心高潮，密集对白
第五章：三尖两刃（11秒）— 最终一击，胜负将分  ← 情绪高潮延续
第六章：英雄相惜（9秒）— 余韵收场，各自离去

scene_durations = [6, 8, 12, 14, 11, 9]
总时长 = 60秒
```

### 5. 角色设计
角色提示词示例：
```
Sun Wukong: male, ageless immortal monkey king, wild golden fur, golden eyes with vertical pupils, wearing golden chainmail armor with tiger-skin kilt, muscular compact build, holding golden Ruyi Jingu Bang staff, blazing golden aura, Chinese fantasy 3D animation art style
```

使用 image-generate 技能生成立绘：
```bash
# 使用内置 image_generate tool 生成角色立绘，提示词示例：
# "Chinese fantasy 3D animation, character portrait, male ageless immortal monkey king, wild golden fur, golden eyes with vertical pupils, wearing golden chainmail armor with tiger-skin kilt, muscular compact build, holding golden Ruyi Jingu Bang staff, blazing golden aura, full body standing pose, simple gradient background, character design reference sheet, professional illustration, high detail, 4K"
```

### 6. 场景美术
分镜图提示词示例（场景4 - 高潮对决，14秒场景）：
```
Chinese fantasy 3D animation, cinematic quality, on a crumbling mountain peak under blood-red sky with dark clouds swirling, Sun Wukong wild golden fur golden eyes wearing golden chainmail armor, leaping high in the air with Ruyi Jingu Bang raised overhead about to strike down, dynamic action angle, explosion bloom shockwave distortion, cinematic composition, high detail, 4K quality
```

### 7. 分镜视频（智能时长提交）

视频提示词示例（场景4，14秒高潮对决）：
```
Chinese fantasy 3D animation, cinematic quality, ultra-high detail, dramatic color grading, on a crumbling mountain peak under blood-red sky dark clouds swirling lightning cracking, Sun Wukong wild golden fur golden eyes wearing golden chainmail armor with tiger-skin kilt, leaps into the air spinning Ruyi Jingu Bang overhead then slams it down with earth-shattering force, face contorted with wild battle joy eyes blazing with fighting spirit teeth bared in a fierce grin, Sun Wukong laughs wildly in Chinese: "二郎神，你这点本事还不够看！", Yang Jian grits teeth and shouts defiantly in Chinese: "泼猴休狂！看我三尖两刃刀！", Sun Wukong roars in Chinese: "哈哈，来得好！", Yang Jian growls in Chinese: "今日定要擒你！", Sun Wukong shouts in Chinese: "做梦！", dynamic tracking shot racing alongside the action camera tilting 45 degrees then ultra-slow motion 0.2x on moment of impact, epic battle orchestra with war drums and brass fanfare sword clashing metal SFX shockwave boom spiritual energy resonance hum
```

完整 JSON 文件示例：

**prompts.json**（⚠️ 纯字符串数组，不是对象数组）：
```json
[
  "Chinese fantasy 3D animation, cinematic quality, on flower fruit mountain peak under twilight sky..., Sun Wukong wild golden fur..., stands with arms crossed surveying the battlefield..., sweeping cinematic orchestral score...",
  "Chinese fantasy 3D animation, cinematic quality, on a vast battlefield clouds swirling..., Sun Wukong leaps forward with Ruyi Jingu Bang..., Yang Jian raises three-pointed blade to block..., epic battle orchestra...",
  "Chinese fantasy 3D animation, cinematic quality, in a whirlwind of golden and silver energy..., Sun Wukong transforms rapidly between forms..., dynamic tracking shot..., high-pitched power surge SFX...",
  "Chinese fantasy 3D animation, cinematic quality, on a crumbling mountain peak under blood-red sky..., Sun Wukong leaps into the air spinning Ruyi Jingu Bang..., Sun Wukong laughs wildly in Chinese: '二郎神，你这点本事还不够看！'...",
  "Chinese fantasy 3D animation, cinematic quality, amid settling dust and fading energy..., Sun Wukong and Yang Jian face each other..., slow pull-back from close-up to wide shot..., triumphant fanfare gradually transitioning to peaceful melody...",
  "Chinese fantasy 3D animation, cinematic quality, on a restored mountain peak under golden sunset..., Sun Wukong turns and walks away..., static locked-off camera holds still for 6 seconds gentle fade..., solo flute melody fading to silence..."
]
```

**frames.json**：
```json
[
  "https://tos-cn-beijing.volces.com/.../scene_01.jpg?X-Tos-Security-Token=...",
  "https://tos-cn-beijing.volces.com/.../scene_02.jpg?X-Tos-Security-Token=...",
  "https://tos-cn-beijing.volces.com/.../scene_03.jpg?X-Tos-Security-Token=...",
  "https://tos-cn-beijing.volces.com/.../scene_04.jpg?X-Tos-Security-Token=...",
  "https://tos-cn-beijing.volces.com/.../scene_05.jpg?X-Tos-Security-Token=...",
  "https://tos-cn-beijing.volces.com/.../scene_06.jpg?X-Tos-Security-Token=..."
]
```

**durations.json**：
```json
[6, 8, 12, 14, 11, 9]
```

提交命令（使用 --durations-file）：
```bash
python scripts/batch_video.py submit \
  --prompts-file prompts.json \
  --first-frames-file frames.json \
  --durations-file durations.json
```

submit 返回后，将 `submitted` 字段保存为 **task_ids.json**：
```json
{"scene_01": "vid_abc123", "scene_02": "vid_def456", "scene_03": "vid_ghi789", "scene_04": "vid_jkl012", "scene_05": "vid_mno345", "scene_06": "vid_pqr678"}
```

然后轮询：
```bash
python scripts/batch_video.py poll --task-ids-file task_ids.json --interval 30
```

### 8. 视频合成
```bash
python scripts/video_merge.py --input-dir "{COMIC_DRAMA_OUTPUT_DIR}/task_.../videos" --output "{COMIC_DRAMA_OUTPUT_DIR}/task_.../final/孙悟空大战二郎神_final.mp4" --scene-count 6
python scripts/tos_upload.py "{COMIC_DRAMA_OUTPUT_DIR}/task_.../final/孙悟空大战二郎神_final.mp4"
```

---

## 示例2：修仙题材（2分钟，12个分镜，智能时长）

**用户输入**：
```
凡人修仙传韩立大战极阴老祖，视频时长2分钟
```

**启动前设置**：
```bash
export VIDEO_DURATION_MINUTES=2
```

**关键差异**：
- scene_count = 10~13（取决于智能时长分配）
- 时长分配示例：`[6, 8, 5, 10, 12, 14, 15, 14, 12, 8, 6, 10]`（总 120 秒）
- 故事弧线更长：开端3章 → 发展3章 → 高潮4章 → 结局2章
- 对白更丰富，角色发展更细腻
- 11~15秒场景用于核心对决，4~6秒快切用于紧张过渡

---

## 示例3：现代都市题材

**用户输入**：
```
职场风云：实习生逆袭大厂CEO，日漫2D风格
```

**视觉风格调整**：
- visual_style = `anime style, cel-shaded, vibrant colors, expressive faces`
- 场景：办公室、会议室、城市天际线
- 运镜：更多特写和中景，减少大场面
- **时长分配特点**：都市题材以对话为主，高潮章节（关键谈判/对质）使用 11~15 秒以容纳密集对白，日常对话场景可用 4~8 秒快节奏推进

---

## 示例提示词库

| 题材     | 示例提示词                                   |
|---------|---------------------------------------------|
| 中国成语 | "后羿射日嫦娥奔月吴刚伐木"                    |
| 经典故事 | "愚公移山与精卫填海绘本故事"                    |
| 武侠小说 | "射雕英雄传，郭靖大战欧阳锋，真人版"            |
| 玄幻修仙 | "凡人修仙传韩立结婴"                          |
| 赛博朋克 | "赛博朋克废土猎人追杀机械龙"                    |
| 历史题材 | "荆轲刺秦王最后一夜"                          |
| 奇幻冒险 | "小镇女孩误入精灵王国"                        |
| 科幻     | "星际特工拯救地球"                            |
| 都市     | "职场风云实习生逆袭大厂CEO"                    |
| 儿童     | "小狐狸寻找星星碎片"                          |

---

## 产物目录结构

每个任务完成后，`COMIC_DRAMA_OUTPUT_DIR`（默认为项目目录下的 `output/`）下会有如下结构：

```
{COMIC_DRAMA_OUTPUT_DIR}/
└── task_20260222_143000_孙悟空大战二郎神/
    ├── requirements.md   # 需求文档（含 web_search 调研摘要）
    ├── plot.md           # 章节式剧情大纲（含智能时长分配）
    ├── script.md         # 完整对白剧本（含逐秒时间戳 + 每章独立时长）
    ├── characters.md     # 角色设计（含英文提示词 + 立绘图片）
    ├── cover.jpg         # 封面图
    ├── cover.md          # 封面信息
    ├── final_video.md    # 最终交付文档（含 TOS 链接）
    ├── storyboard/       # 分镜图（scene_01.jpg ~ scene_06.jpg）
    ├── characters/       # 角色立绘（char_sunwukong.jpg 等）
    ├── videos/           # 分镜视频（scene_01.mp4 ~ scene_06.mp4，智能时长 4~15s）
    └── final/            # 合成漫剧（孙悟空大战二郎神_final.mp4）
```
