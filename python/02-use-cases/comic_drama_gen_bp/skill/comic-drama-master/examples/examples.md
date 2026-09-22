# Comic Drama Production Usage Examples

## Example 1: Chinese Mythology (1 minute, 6 storyboard scenes, smart duration)

**User input**:
```
Please create a comic drama video about "Sun Wukong battles Erlang Shen", in guoman (Chinese-style animation) 3D realistic style
```

**Execution flow**:

### 1. Read configuration
```bash
python scripts/app_config.py
# Output: {"video_duration_minutes": 1, "total_seconds": 60, "smart_duration": true, "duration_range": {"min": 4, "max": 30}, "duration_options": "4s ~ 30s dynamic allocation", "scene_count_range": {"min": 4, "max": 30}, "recommended_scene_count": 6}
```

### 2. Initialize the task
```bash
python scripts/task_manager.py init "Sun Wukong vs Erlang Shen"
# Output: {"task_folder": "{COMIC_DRAMA_OUTPUT_DIR}/task_20260222_143000_Sun_Wukong_vs_Erlang/", ...}
```

### 3. Content safety pre-review
- Assess risk level: **medium risk** (wuxia-style combat)
- Mitigation strategy: use euphemistic substitutes (`spiritual energy clash` instead of `bloody battle`)
- Inform the user, then continue

### 4. Script generation (with smart duration allocation)
- WORKING_LANGUAGE = English and DIALOGUE_LANGUAGE = English (the user wrote in English, so the default applies) — recorded at the top of requirements.md and plot.md; every dialogue line in script.md is written in English, even though the story is drawn from Chinese mythology
- web_search: "Sun Wukong battles Erlang Shen original storyline", "Erlang Shen Yang Jian abilities and magic weapons", "Journey to the West classic quotes"
- Write requirements.md, plot.md, script.md
- **Duration allocation** (4s ~ 30s dynamic range):

```
Chapter 1: Wrath of the Heavenly Court (6s) — Atop Flower Fruit Mountain, heavenly troops close in  <- tense quick cuts, rapidly establish the atmosphere
Chapter 2: First Clash (8s) — Wukong and Yang Jian's first duel  <- standard narrative pacing
Chapter 3: Seventy-Two Transformations (12s) — a dazzling shape-shifting duel  <- climax build-up, needs more dialogue
Chapter 4: True-Form Showdown (14s) — raw power against finesse, the ultimate confrontation  <- core climax, dense dialogue
Chapter 5: Three-Pointed Double-Edged Blade (11s) — the final strike, victory hangs in the balance  <- emotional climax continues
Chapter 6: Heroes' Mutual Respect (9s) — lingering aftermath, each goes his own way

scene_durations = [6, 8, 12, 14, 11, 9]
Total duration = 60 seconds
```

### 5. Character design
Example character prompt:
```
Sun Wukong: male, ageless immortal monkey king, wild golden fur, golden eyes with vertical pupils, wearing golden chainmail armor with tiger-skin kilt, muscular compact build, holding golden Ruyi Jingu Bang staff, blazing golden aura, Chinese fantasy 3D animation art style
```

Use the image-generate skill to create character portraits:
```bash
# Use the built-in image_generate tool to generate character portraits. Example prompt:
# "Chinese fantasy 3D animation, character portrait, male ageless immortal monkey king, wild golden fur, golden eyes with vertical pupils, wearing golden chainmail armor with tiger-skin kilt, muscular compact build, holding golden Ruyi Jingu Bang staff, blazing golden aura, full body standing pose, simple gradient background, character design reference sheet, professional illustration, high detail, 4K"
```

### 6. Scene art
Example storyboard image prompt (Scene 4 — climactic duel, 14-second scene):
```
Chinese fantasy 3D animation, cinematic quality, on a crumbling mountain peak under blood-red sky with dark clouds swirling, Sun Wukong wild golden fur golden eyes wearing golden chainmail armor, leaping high in the air with Ruyi Jingu Bang raised overhead about to strike down, dynamic action angle, explosion bloom shockwave distortion, cinematic composition, high detail, 4K quality
```

### 7. Storyboard videos (smart-duration submission)

Example video prompt (Scene 4, 14-second climactic duel; DIALOGUE_LANGUAGE is English here, so every quoted line is English and every speech tag reads `in English`, and the characters speak English on screen):
```
Chinese fantasy 3D animation, cinematic quality, ultra-high detail, dramatic color grading, on a crumbling mountain peak under blood-red sky dark clouds swirling lightning cracking, Sun Wukong wild golden fur golden eyes wearing golden chainmail armor with tiger-skin kilt, leaps into the air spinning Ruyi Jingu Bang overhead then slams it down with earth-shattering force, face contorted with wild battle joy eyes blazing with fighting spirit teeth bared in a fierce grin, Sun Wukong laughs wildly in English: "Erlang Shen, this little trick of yours is nowhere near enough!", Yang Jian grits teeth and shouts defiantly in English: "Enough of your swagger, monkey! Taste my three-pointed blade!", Sun Wukong roars in English: "Ha! Now that is more like it!", Yang Jian growls in English: "Today I take you in!", Sun Wukong shouts in English: "Keep dreaming!", dynamic tracking shot racing alongside the action camera tilting 45 degrees then ultra-slow motion 0.2x on moment of impact, epic battle orchestra with war drums and brass fanfare sword clashing metal SFX shockwave boom spiritual energy resonance hum
```

Complete example JSON files:

**prompts.json** (⚠️ a plain array of strings, NOT an array of objects):
```json
[
  "Chinese fantasy 3D animation, cinematic quality, on flower fruit mountain peak under twilight sky..., Sun Wukong wild golden fur..., stands with arms crossed surveying the battlefield..., sweeping cinematic orchestral score...",
  "Chinese fantasy 3D animation, cinematic quality, on a vast battlefield clouds swirling..., Sun Wukong leaps forward with Ruyi Jingu Bang..., Yang Jian raises three-pointed blade to block..., epic battle orchestra...",
  "Chinese fantasy 3D animation, cinematic quality, in a whirlwind of golden and silver energy..., Sun Wukong transforms rapidly between forms..., dynamic tracking shot..., high-pitched power surge SFX...",
  "Chinese fantasy 3D animation, cinematic quality, on a crumbling mountain peak under blood-red sky..., Sun Wukong leaps into the air spinning Ruyi Jingu Bang..., Sun Wukong laughs wildly in English: 'Erlang Shen, this little trick of yours is nowhere near enough!'...",
  "Chinese fantasy 3D animation, cinematic quality, amid settling dust and fading energy..., Sun Wukong and Yang Jian face each other..., slow pull-back from close-up to wide shot..., triumphant fanfare gradually transitioning to peaceful melody...",
  "Chinese fantasy 3D animation, cinematic quality, on a restored mountain peak under golden sunset..., Sun Wukong turns and walks away..., static locked-off camera holds still for 6 seconds gentle fade..., solo flute melody fading to silence..."
]
```

**frames.json**:
```json
[
  "https://tos-ap-southeast-1.bytepluses.com/.../scene_01.jpg?X-Tos-Security-Token=...",
  "https://tos-ap-southeast-1.bytepluses.com/.../scene_02.jpg?X-Tos-Security-Token=...",
  "https://tos-ap-southeast-1.bytepluses.com/.../scene_03.jpg?X-Tos-Security-Token=...",
  "https://tos-ap-southeast-1.bytepluses.com/.../scene_04.jpg?X-Tos-Security-Token=...",
  "https://tos-ap-southeast-1.bytepluses.com/.../scene_05.jpg?X-Tos-Security-Token=...",
  "https://tos-ap-southeast-1.bytepluses.com/.../scene_06.jpg?X-Tos-Security-Token=..."
]
```

**durations.json**:
```json
[6, 8, 12, 14, 11, 9]
```

Submit command (using --durations-file):
```bash
python scripts/batch_video.py submit \
  --prompts-file prompts.json \
  --first-frames-file frames.json \
  --durations-file durations.json
```

After submit returns, save the `submitted` field as **task_ids.json**:
```json
{"scene_01": "vid_abc123", "scene_02": "vid_def456", "scene_03": "vid_ghi789", "scene_04": "vid_jkl012", "scene_05": "vid_mno345", "scene_06": "vid_pqr678"}
```

Then poll:
```bash
python scripts/batch_video.py poll --task-ids-file task_ids.json --interval 30
```

### 8. Video merging
```bash
python scripts/video_merge.py --input-dir "{COMIC_DRAMA_OUTPUT_DIR}/task_.../videos" --output "{COMIC_DRAMA_OUTPUT_DIR}/task_.../final/Sun_Wukong_vs_Erlang_Shen_final.mp4" --scene-count 6
python scripts/tos_upload.py "{COMIC_DRAMA_OUTPUT_DIR}/task_.../final/Sun_Wukong_vs_Erlang_Shen_final.mp4"
```

---

## Example 2: Xianxia Cultivation Theme (2 minutes, 12 storyboard scenes, smart duration)

**User input**:
```
Han Li battles the Patriarch of Extreme Yin, from A Record of a Mortal's Journey to Immortality, video duration 2 minutes
```

**Setup before launch**:
```bash
export VIDEO_DURATION_MINUTES=2
```

**Key differences**:
- scene_count = 10~13 (depends on smart duration allocation)
- Example duration allocation: `[6, 8, 5, 10, 12, 14, 15, 14, 12, 8, 6, 10]` (120 seconds total)
- Longer story arc: opening 3 chapters → development 3 chapters → climax 4 chapters → ending 2 chapters
- Richer dialogue and more nuanced character development
- 11~15-second scenes for core showdowns (16~30-second epic long takes for the final showdown), 4~6-second quick cuts for tense transitions

---

## Example 3: Modern Urban Theme

**User input**:
```
Workplace drama: an intern's underdog rise to CEO of a tech giant, in Japanese 2D anime style
```

**Visual style adjustments**:
- visual_style = `anime style, cel-shaded, vibrant colors, expressive faces`
- Settings: offices, meeting rooms, city skylines
- Camera work: more close-ups and medium shots, fewer sweeping vistas
- **Duration allocation notes**: urban stories are dialogue-driven — climax chapters (key negotiations/confrontations) use 11~15 seconds (or 16~30 seconds for an epic finale) to fit dense dialogue, while everyday conversation scenes can move at a fast 4~8-second pace

---

## Example Prompt Library

| Genre             | Example prompt                                                                          |
|-------------------|-----------------------------------------------------------------------------------------|
| Chinese idioms    | "Hou Yi shoots down the suns, Chang'e flies to the moon, Wu Gang fells the tree"          |
| Classic tales     | "Yu Gong moves the mountains and Jingwei fills the sea, picture-book story"               |
| Wuxia novels      | "Legend of the Condor Heroes: Guo Jing battles Ouyang Feng, live-action style"            |
| Xianxia fantasy   | "Han Li forms his Nascent Soul, from A Record of a Mortal's Journey to Immortality"       |
| Cyberpunk         | "A cyberpunk wasteland hunter chases down a mechanical dragon"                            |
| Historical        | "Jing Ke's last night before assassinating the King of Qin"                               |
| Fantasy adventure | "A small-town girl stumbles into the elven kingdom"                                       |
| Sci-fi            | "Interstellar agents save the Earth"                                                      |
| Urban             | "Workplace drama: an intern's underdog rise to CEO of a tech giant"                       |
| Children's        | "A little fox searches for star fragments"                                                |

> Every one of these produces an **English** comic drama by default: English documents, English prompts, and characters speaking English on screen — whatever the story's origin. If the user writes their request in another language (for example 《孙悟空大战二郎神》 in Chinese), the whole production — replies, documents, prompts, and the spoken dialogue — is done in that language instead.

---

## Output Directory Structure

After each task completes, `COMIC_DRAMA_OUTPUT_DIR` (defaults to `output/` under the project directory) will contain the following structure:

```
{COMIC_DRAMA_OUTPUT_DIR}/
└── task_20260222_143000_Sun_Wukong_vs_Erlang/
    ├── requirements.md   # Requirements document (with web_search research summary)
    ├── plot.md           # Chapter-based plot outline (with smart duration allocation)
    ├── script.md         # Full dialogue script (with second-by-second timestamps + per-chapter durations)
    ├── characters.md     # Character designs (with character prompts + character portrait images)
    ├── cover.jpg         # Cover image
    ├── cover.md          # Cover info
    ├── final_video.md    # Final delivery document (with TOS links)
    ├── storyboard/       # Storyboard images (scene_01.jpg ~ scene_06.jpg)
    ├── characters/       # Character portraits (char_sunwukong.jpg, etc.)
    ├── videos/           # Storyboard videos (scene_01.mp4 ~ scene_06.mp4, smart duration 4~30s)
    └── final/            # Merged comic drama (Sun_Wukong_vs_Erlang_Shen_final.mp4)
```
