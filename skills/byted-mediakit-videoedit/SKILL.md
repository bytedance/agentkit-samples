---
name: byted-mediakit-videoedit
description: >
AI Video Intelligent Editing Skill. Input video file paths (supports multiple), optional danmaku file paths, optional subtitle file paths,
combine danmaku and subtitle content to understand video context, automatically extract corresponding time segments based on user editing requests (such as "extract all highlight moments",
"cut out the part explaining xxx"), splice and add transition effects, and finally synthesize the output video using FFmpeg.
When users mention "cut video based on danmaku", "extract danmaku highlight segments", "danmaku analysis editing",
"find highlights from danmaku", "intelligent editing", this Skill must be triggered.
version: v1.0.1
---

# AI Video Intelligent Editing

## Overview

This Skill helps users understand video context by analyzing danmaku and subtitle content, automatically extracts and splices video clips based on editing requests, and uses FFmpeg to complete transition effects and final synthesis.

## Input Specifications

- **Video files** (required, supports multiple): Local video file paths, supports formats like `.mp4`, `.flv`, `.mkv`, etc.
- **Danmaku files** (optional, one per video): XML format danmaku files (supports Bilibili format), corresponding to video files in order one-to-one
- **Subtitle files** (optional, one per video): `.srt` / `.ass` / `.json` format subtitle files, corresponding to video files in order one-to-one; leave empty for videos without subtitles

> **Note:** Subtitles and danmaku are the only basis for understanding video content. If neither is provided for a video, its content cannot be understood, and only explicit time segment instructions from the user can be executed.

## Workflow

### Step 0: Dependency Verification

Before performing any operations, verify that the runtime environment meets the requirements.

**Verification Commands:**

```bash
python --version
ffmpeg -version 2>&1 | head -1
ffprobe -version 2>&1 | head -1
node --version
```

**Acceptance Criteria and Fixing Guidelines:**

| Dependency | Minimum Requirement  | Verification Method | Installation Command When Not Met                                                                                         |
| ---------- | -------------------- | ------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| Python     | 3.9+                 | `python --version`  | See instructions below                                                                                                    |
| ffmpeg     | Any version          | `ffmpeg -version`   | macOS: `brew install ffmpeg` · Linux: `sudo apt install ffmpeg` · Windows: [ffmpeg.org](https://ffmpeg.org/download.html) |
| ffprobe    | Included with ffmpeg | `ffprobe -version`  | Installed with ffmpeg, no separate operation needed                                                                       |
| Node.js    | 18+                  | `node --version`    | macOS: `brew install node` · or [nodejs.org](https://nodejs.org/)                                                         |

**Python Installation Instructions (if version is not met):**

- macOS: `brew install python@3.11`
- Linux: `sudo apt install python3.11`
- Or via [pyenv](https://github.com/pyenv/pyenv): `pyenv install 3.11 && pyenv global 3.11`

**Text Effect Rendering Dependency (Remotion) Installation:**

Check if `byted-mediakit-videoedit/template/node_modules` exists:

```bash
ls byted-mediakit-videoedit/template/node_modules/@remotion/renderer 2>/dev/null && echo "已安装" || echo "需要安装"
```

If not installed, execute:

```bash
cd byted-mediakit-videoedit/template && npm install
```

Installation takes about 1-2 minutes, and `node_modules` will appear in the directory after completion. This step is skipped in subsequent conversations if `node_modules` already exists.

**Processing Rules:**

- All dependencies met → proceed to next step
- Missing or insufficient version → explain to user what is missing, provide installation commands for the corresponding platform, **wait for user to complete installation and re-confirm before continuing**

### Step 1: Check Understandability of Each Video

Before any analysis, confirm individually whether each video has subtitles or danmaku:

| Video       | Has Subtitles | Has Danmaku | Understandability                                                                                                                                        |
| ----------- | ------------- | ----------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| video_A.mp4 | ✅            | —           | **Intelligent Analysis**: Can understand video based on content semantics, supports content requests like "find highlights/find appearance introduction" |
| video_B.mp4 | —             | ✅          | **Intelligent Analysis** (downgraded): Infer content through danmaku, accuracy lower than subtitles                                                      |
| video_C.mp4 | —             | —           | **Only Explicit Commands**: Cannot understand content, can only cut according to precise time segments provided by user                                  |

**Processing Rules for "Only Explicit Commands" Videos:**

1. **User provides explicit time segments** (e.g., "cut video_C from 1:00–2:30"): Use directly, no analysis needed
2. **User provides content requests** (e.g., "find appearance introduction from video_C"): **Immediately inform** user that the video lacks subtitles/danmaku, cannot perform content analysis, please provide:
   - Specific time segments, or
   - Subtitle/danmaku files
3. **Mixed scenarios** (some videos understandable, some not): Normal analysis for understandable videos, separately explain limitations for non-understandable videos, and ask user how to handle

### Step 3: Parse Danmaku and Subtitles

Run the parsing script to convert danmaku and subtitles into timeline-based text summaries for video content analysis.

**Single Video:**

```bash
python byted-mediakit-videoedit/scripts/parse_media_info.py \
  --video ep1.mp4 \
  --danmaku ep1.xml \
  --subtitle ep1.srt \
  --output /tmp/media_timeline.json
```

**Multiple Videos (repeat a set of** **`--video`/`--danmaku`/`--subtitle`** **for each video):**

```bash
python byted-mediakit-videoedit/scripts/parse_media_info.py \
  --video ep1.mp4 --danmaku ep1.xml --subtitle ep1.srt \
  --video ep2.mp4 --danmaku ep2.xml \
  --output /tmp/media_timeline.json
```

**Important: Only run this script for videos with subtitles or danmaku.** Videos without both subtitles and danmaku are not passed to the script, and their segment times are directly provided by the user.

Optional parameters:

- `--interval 5`: Danmaku summary time interval size (seconds), default 5
- `--top-danmaku 10`: Number of most frequent danmaku per interval, default 10
- `--include-danmaku`: Force include danmaku summary in output (even with subtitles); **only add this parameter when user explicitly requests to reference danmaku**
- `--video` can be omitted (only for single video), script uses danmaku filename as placeholder when omitted
- `--subtitle` can be omitted (when the video has no subtitles)

**Script automatically determines what to write based on the following rules (no additional Claude judgment needed):**

| Input Situation                       | Content Written to Timeline     | Output Mode            |
| ------------------------------------- | ------------------------------- | ---------------------- |
| Has subtitles, no `--include-danmaku` | Only subtitle entries           | `subtitle_only`        |
| No subtitles                          | Only danmaku interval summaries | `danmaku_only`         |
| Has subtitles + `--include-danmaku`   | Subtitles + danmaku summaries   | `subtitle_and_danmaku` |

The output file's top-level `content_mode` field indicates the current mode, and Claude can directly confirm which type of content is included in the timeline based on this.

The script outputs a JSON timeline, danmaku are **not written one by one**, but summarized by time intervals. There are two types of records in the timeline:

**Danmaku interval summary (type = danmaku_summary):**

```json
{
  "time": 25.0,
  "time_start": 25.0,
  "time_end": 30.0,
  "type": "danmaku_summary",
  "total_count": 38,
  "density": 456.0,
  "top_danmaku": [
    { "text": "666", "count": 12 },
    { "text": "哈哈哈", "count": 8 }
  ],
  "video_file": "ep1.mp4"
}
```

**Subtitle entry (type = subtitle, fully preserved):**

```json
{
  "time": 27.3,
  "end_time": 30.1,
  "type": "subtitle",
  "text": "这一波操作太丝滑了",
  "video_file": "ep1.mp4"
}
```

Top-level fields:

- `videos`: Statistics for each video and their respective highlight peak lists
- `density_peaks`: Global highlight peaks across all videos (including `video_file` and `top_danmaku` fields)
- `summary.peak_times`: Brief information for the top 5 highlight intervals (including position, density, representative danmaku)

### Step 4: Analyze Video Content, Understand Editing Requests

Read `/tmp/media_timeline.json`, combine with user's editing needs, and infer the list of time segments to be extracted.

**Prerequisite Check: Skip Unanalyzable Videos**

Before content analysis, only process videos determined as "Intelligent Analysis" in Step 0. For "Only Explicit Commands" videos, skip analysis and directly use user-provided time values for clip `start`/`end`.

Analysis Strategy:

**First Priority: Determine Content Understanding Method Based on Subtitles**

| Situation                                | Content Understanding Method                                                                                                    |
| ---------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| Has subtitle files                       | **Read only subtitles** to understand video content, ignore danmaku data (unless user explicitly requests to reference danmaku) |
| No subtitle files                        | **Read only danmaku summaries** (`danmaku_summary`) to understand video content and highlight moments                           |
| User explicitly says "reference danmaku" | **Read both subtitles and danmaku** regardless of whether subtitles exist                                                       |

> Reason: Subtitles are precise records of actual video audio content, directly expressing video semantics; danmaku are audience reactions, with noise such as spamming and irrelevant content. When there are subtitles, the marginal benefit of danmaku information is low, and it consumes a lot of context.

**With Subtitles (Main Path)**

- Understand video content through subtitle text, locate topics, key sentences, paragraphs that users are interested in
- Search keywords directly in subtitles
- Clip boundaries strictly aligned with subtitle sentence boundaries (see "Determine Clip Boundaries" below)

**Without Subtitles (Downgraded Path)**

- Read `type=danmaku_summary` entries, judge popularity by `density` (counts per minute)
- `density_peaks` has already pre-identified intervals with highest density, directly use as highlight candidates
- Infer video content or emotion in the interval through `top_danmaku` list
- Common highlight danmaku words: `"www"`, `"哈哈"`, `"666"`, `"awsl"`, `"绝了"`, `"牛"`, `"真的假的"`, `"名场面"`
- Negative danmaku (such as `"笑死"`, `"可怜"`) need to be judged in context

**Multi-video Analysis Notes**

- Each record in the timeline has a `video_file` field, must distinguish different video timelines during analysis, do not mix time offsets
- When determining clip `start`/`end`, only find boundaries in subtitles/danmaku corresponding to the record's `video_file`
- Each clip's `video_file` field in the final clips JSON must match the timeline source video

**Determine Clip Boundaries**

- **With subtitles**: In and out points must be based on subtitles, ensure each clip is a complete sentence:
  1. **Locate candidate interval**: Determine general range of interest based on subtitle keywords or danmaku density (when user requests)
  2. **Align start time**: Find the `time` of the most recent subtitle **before** the candidate interval start; if the beginning semantics are incomplete (conjunctions like "而且"/"但是" etc.), continue moving forward
  3. **Align end time**: Find the `end_time` of the most recent subtitle **after** the candidate interval end, ensure the last sentence is complete
  4. **Check completeness**: Confirm that the subtitle content covered by the clip has complete semantics (does not end with commas, transition words, or incomplete clauses)
- **Without subtitles**: Center on danmaku highlight intervals, use 1s before and 1.5s after as padding to determine boundaries

> Subtitle records include `time` (start seconds) and `end_time` (end seconds), directly used for boundary alignment.

- Clips are at least 3 seconds long, maximum length determined by content (usually no more than 60 seconds per clip)

Output format (internal reasoning result, JSON):

```json
{
  "clips": [
    {
      "video_file": "/path/to/video.mp4",
      "start": 125.3,
      "end": 142.8,
      "reason": "Danmaku density peak, lots of '666' and '绝了' danmaku, corresponding subtitles show player completed difficult operation"
    }
  ],
  "transition": "fade",
  "normalize_audio": true,
  "output_path": "/tmp/output_cut.mp4"
}
```

> `normalize_audio` defaults to `false`, only executed after explicit user confirmation. For multiple clips, can enable two-pass EBU R128 volume normalization (target -16 LUFS / -1.5 dBTP) to eliminate volume differences between different video sources. Not needed for single clips.

### Step 5: Select Transition Effects

If the user **has explicitly specified** transition effects, use directly. If **not specified**, infer the most appropriate effect based on understanding of danmaku and subtitles, following this logic:

| Content Feature                                                             | Recommended Transition    | Judgment Basis                                                                               |
| --------------------------------------------------------------------------- | ------------------------- | -------------------------------------------------------------------------------------------- |
| Danmaku dominated by excited words like `哈哈`/`666`/`牛`/`绝了`, fast pace | `none`                    | Hard cut better matches the impact of highlight moments                                      |
| Game/sports competition, danmaku with lots of `冲`/`gkd`/`打`               | `wipeleft` or `wiperight` | Horizontal wipe has dynamic feeling and directionality                                       |
| Subtitles for knowledge讲解/tutorial/review, rational content               | `dissolve`                | Dissolve transition is smooth and non-intrusive, suitable for information-dense content      |
| Emotional/vlog/life content, danmaku with `好看`/`感动`/`治愈`              | `fade`                    | Fade in/out is soft, has emotional continuity                                                |
| Subtitles for step-by-step tutorials (Step 1/Step 2...)                     | `slideup` or `slidedown`  | Vertical slide has a sense of progress                                                       |
| High-energy/montage/strong editing feeling, danmaku with `燃`/`热血`/`混剪` | `zoomin`                  | Strong镜头推进感, creates visual impact and rhythm                                           |
| Cinematic/dramatic content, large scene transitions                         | `circleopen`              | Circular opening has film texture, suitable for dramatic scene transitions                   |
| Tech/digital/game highlights, danmaku with `数字`/`代码`/`科技`             | `pixelize`                | Pixelized dissolve has cyberpunk texture, suitable for tech themes                           |
| Events/parties/concerts, quick multi-scene transitions                      | `radial`                  | Radial sweep has stage feeling, suitable for multi-scene transitions                         |
| Travel/landscape/city exploration, scene panning                            | `smoothleft`              | Smooth left slide transition is natural and fluid, suitable for spatial displacement feeling |
| Mixed content or difficult to judge                                         | `fade`                    | Most universal fallback option                                                               |

After inference, inform the user in the reply about the selected transition and its reason, making it easy for the user to confirm or adjust.

### Step 6: Present Editing Plan to User and Wait for Confirmation

After completing analysis and transition selection, **must** present the complete plan to the user in table form, **stop and wait for user's explicit confirmation before continuing execution**. Do not call `cut_and_merge.py` without confirmation.

**Plan Presentation Format:**

> Below is the editing plan organized based on your needs. Please confirm before I start synthesis:
>
> | #   | Video Source | Time Segment  | Duration | Content Description                                                   |
> | --- | ------------ | ------------- | -------- | --------------------------------------------------------------------- |
> | 1   | xxx.mp4      | 01:29 → 01:57 | 28s      | Appearance opening: first talk about appearance + color scheme rating |
> | 2   | yyy.mp4      | 02:46 → 03:03 | 17s      | Border craft change introduction                                      |
> | 3   | zzz.mp4      | 03:01 → 03:19 | 18s      | Three major appearance feel details                                   |
>
> **Transition Effect:** dissolve (溶解) · Duration 0.8s · Reason: Knowledge讲解/review content suitable for smooth transition
> **Estimated Total Duration:** Approximately 63 seconds
>
> **Volume Normalization:** Do you want to enable EBU R128 volume normalization? This step requires two-pass loudness analysis for each clip, **time-consuming** (about 30–60 seconds extra per minute of video), but can eliminate volume differences between different video sources. Please let me know if you want to enable it.
>
> Confirm execution? If you need to adjust the time of a segment, delete or replace a segment, please tell me.

**Supported Modification Types (update plan after user feedback, re-present, wait for confirmation again):**

- Adjust start/end time of a segment (e.g., "extend the end of segment 2 by 5 seconds")
- Delete or replace a segment (e.g., "remove segment 3, replace with a more representative one")
- Adjust segment order (e.g., "put the 16 Pro segment first")
- Change transition effect or duration
- Add new segments

**Confirmation Signal Recognition:** When the user replies with words indicating approval like "好的" (okay), "确认" (confirm), "可以" (can), "执行" (execute), "开始" (start), "没问题" (no problem), it is considered confirmed for the editing plan, **but volume normalization requires separate explicit user reply before execution**.

**Volume Normalization Confirmation Rules:**

- User explicitly says "开启" (enable)/"要" (want)/"需要" (need)/"均衡" (normalize) volume normalization → `normalize_audio: true`, execute normalization
- User explicitly says "跳过" (skip)/"不要" (don't want)/"不用" (no need)/"不需要" (not needed) volume normalization → `normalize_audio: false`, skip
- User directly confirms execution but **does not mention volume normalization** → **must ask**: "Do you need to enable volume normalization? (Time-consuming, adds about 30–60 seconds per minute of video)", wait for user reply before execution

### Step 7: Execute Editing

After user confirms the plan, write the final plan to `/tmp/clips.json`, run the editing script:

```bash
python byted-mediakit-videoedit/scripts/cut_and_merge.py \
  --clips-json /tmp/clips.json \
  --output /path/to/output.mp4
```

Default transition duration is 1 second, can be overridden in clips JSON with `transition_duration` field (unit: seconds).

Script execution order: Extract segments → Volume normalization (two-pass loudnorm, only executed when user confirms enable) → Resolution normalization (add black bars) → Transition merging → Output final video.

### Step 8 (Optional): Add Text Effects

After video editing is complete, ask the user if they need to add text effects:

> Video editing is complete. Do you need to add **text effects** to the final video? (Such as danmaku burst animation, UP master name card, chapter titles, golden sentence cards, etc.)

If the user chooses **not to add**, skip to Step 9 to display results. If the user chooses **to add**, execute the following process:

#### 8.1 Generate Effect Suggestions

Based on the subtitle/danmaku data parsed in Step 3, combined with the clips list, infer effects corresponding to each segment's content.

**Timeline Conversion Rules (Key):**

Effect timestamps are relative to the **final video**, need to convert from original video time:

- Start time of clip N in final video = sum of durations of first N-1 segments (deduct `transition_duration × (N-1)` seconds if there are transitions)
- Original time T belongs to clip N (original start=S) → final video time = `clip_N final video start + (T - S)`

**Effect Type Selection Guide:**

| Trigger Condition                                                    | Recommended Effect      | Description                                                                      |
| -------------------------------------------------------------------- | ----------------------- | -------------------------------------------------------------------------------- |
| Danmaku density peak (highlight interval)                            | `danmakuBursts`         | Use `top_danmaku` for floating danmaku, fill `highlight` with most frequent word |
| Danmaku contains "666"/"绝了"/"牛"/"神操作"                          | `keyPhrases` (emphasis) | Display the word as text at top/bottom                                           |
| Subtitles contain golden sentences                                   | `quotes`                | Display at bottom or side                                                        |
| 0-3s at the beginning of final video or obvious paragraph boundaries | `chapterTitles`         | Display theme, such as "精彩时刻合集"                                            |
| First appearance of UP master/guest                                  | `lowerThirds`           | Display name/identity bar                                                        |

**Effect Configuration Format (time unit: milliseconds, relative to final video):**

```json
{
  "theme": "douyin",
  "videoInfo": { "width": 1920, "height": 1080 },
  "chapterTitles": [
    {
      "title": "精彩时刻",
      "subtitle": "弹幕高能合集",
      "startMs": 0,
      "durationMs": 3000
    }
  ],
  "keyPhrases": [
    {
      "text": "666",
      "style": "emphasis",
      "position": "top",
      "startMs": 8500,
      "endMs": 10500
    }
  ],
  "danmakuBursts": [
    {
      "messages": ["666", "哈哈哈", "绝了", "牛啊", "名场面"],
      "highlight": "名场面",
      "startMs": 12000,
      "durationMs": 3000
    }
  ],
  "lowerThirds": [
    {
      "name": "UP主昵称",
      "role": "游戏区",
      "company": "bilibili",
      "startMs": 500,
      "durationMs": 5000
    }
  ],
  "quotes": [
    {
      "text": "这波操作太丝滑了",
      "author": "— 弹幕金句",
      "position": "bottom",
      "startMs": 25000,
      "durationMs": 4000
    }
  ]
}
```

**Optional Themes:** `douyin` (default, suitable for Bilibili/games), `notion` (knowledge/review), `cyberpunk` (tech/cyber), `aurora` (gradient stream), `apple` (minimalist)

#### 8.2 Present Effect Plan to User and Confirm

Present all suggested effects in table form, **wait for user's explicit confirmation** before rendering:

> | #   | Type          | Final Video Time | Content                       | Theme  |
> | --- | ------------- | ---------------- | ----------------------------- | ------ |
> | 1   | Chapter Title | 0s – 3s          | "精彩时刻"                    | douyin |
> | 2   | Text Effect   | 8.5s – 10.5s     | "666" (emphasis)              | douyin |
> | 3   | Danmaku Burst | 12s – 15s        | 5 danmaku, highlight="名场面" | douyin |
>
> After confirmation, effects will be rendered and synthesized into the video (takes about 1-3 minutes). Confirm?

#### 8.3 Get Final Video Resolution and Write to Configuration

```bash
ffprobe -v quiet -select_streams v:0 \
  -show_entries stream=width,height -of json /path/to/output_cut.mp4
```

Fill `width` / `height` into `videoInfo` field of `effects_config.json`, write to `/tmp/effects_config.json`.

#### 8.4 Render Effects (Remotion)

```bash
# Note: Must cd to template directory first, render.mjs uses relative path to locate entry file
cd byted-mediakit-videoedit/template && node render.mjs \
  --config=/tmp/effects_config.json \
  --out-dir=/tmp/effects
```

After successful rendering, each line prints `✅ xxx-N -> /tmp/effects/xxx-N.mov`.

#### 8.5 Synthesize Effect Video

```bash
python byted-mediakit-videoedit/scripts/video_effects.py \
  /path/to/output_cut.mp4 \
  /tmp/effects_config.json \
  /tmp/effects \
  /path/to/output_final.mp4
```

### Step 9: Display Results

After completion:

1. Inform the user of the final output file path ( `output_final.mp4` with effects, `output_cut.mp4` without effects)
2. Explain which segments were cut (time segments + reasons) and total duration
3. If there are effects, explain which text effects were added
4. If the user is not satisfied with the results, ask if they want to adjust cutting conditions, transition effects, or effect content

## Error Handling

- **Danmaku file parsing failure**: Check if it's standard XML format (supports Bilibili format, `<i>` root node, `<d>` danmaku nodes)
- **Video file not found**: Prompt user to check the path
- **FFmpeg not installed**: Prompt `brew install ffmpeg` (macOS) or `apt install ffmpeg` (Linux)
- **Segment time exceeds video duration**: Automatically crop to video end
- **Remotion rendering failure**: Check if `node_modules` exists (`npm install`), confirm Node.js version ≥ 18
- **Effect synthesis failure**: Check if corresponding `.mov` files exist in `/tmp/effects/` directory, confirm effect rendering step was successfully completed

## Notes

- For multiple videos, each video must have a corresponding `--danmaku` file; `--subtitle` is optional, not passing it means no subtitle-assisted positioning for that video
- Danmaku timeline is based on video playback time (not mount timestamp)
- If subtitle file is `.ass` format, script automatically extracts plain text content and ignores style information
- Output video uses H.264 + AAC encoding by default, compatible with most platforms
