#!/usr/bin/env python3
# Copyright (c) 2025 Beijing Volcano Engine Technology Co., Ltd. and/or its affiliates. 
# 
# Licensed under the Apache License, Version 2.0 (the "License"); 
# you may not use this file except in compliance with the License. 
# You may obtain a copy of the License at 
# 
#     `http://www.apache.org/licenses/LICENSE-2.0` 
# 
# Unless required by applicable law or agreed to in writing, software 
# distributed under the License is distributed on an "AS IS" BASIS, 
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. 
# See the License for the specific language governing permissions and 
# limitations under the License.

from __future__ import annotations
"""
解析弹幕 XML 和字幕文件，输出带时间轴的 JSON 摘要。

弹幕按时间区间（默认 5s）分组汇总，每个区间只保留出现频次最高的 top N 条
及总弹幕数/密度，不输出完整弹幕列表，大幅压缩输出体积。

支持：
- 弹幕：Bilibili XML 格式 (<i><d p="...">text</d></i>)
- 字幕：SRT、ASS、JSON（B站下载的 JSON 格式）
"""

import argparse
import json
import re
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path


def parse_bilibili_danmaku(xml_path: str) -> list[dict]:
    """解析 Bilibili XML 弹幕文件，返回弹幕列表。"""
    danmaku_list = []
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        for d in root.findall('d'):
            p = d.get('p', '')
            text = d.text or ''
            parts = p.split(',')
            if len(parts) < 1:
                continue
            try:
                time = float(parts[0])
                danmaku_list.append({
                    'time': time,
                    'type': 'danmaku',
                    'text': text.strip(),
                })
            except (ValueError, IndexError):
                continue
    except ET.ParseError as e:
        print(f"[警告] 弹幕文件解析失败: {e}")
    return sorted(danmaku_list, key=lambda x: x['time'])


def summarize_danmaku_by_interval(
    danmaku_list: list[dict],
    interval: float = 5.0,
    top_n: int = 10,
    video_file: str = '',
) -> list[dict]:
    """将弹幕按时间区间分组，每个区间保留出现频次最高的 top_n 条及总密度。

    返回的每条记录格式：
    {
        "time": <区间起始秒，用于排序>,
        "time_start": <区间起始秒>,
        "time_end": <区间结束秒>,
        "type": "danmaku_summary",
        "total_count": <该区间弹幕总条数>,
        "density": <条/分钟>,
        "top_danmaku": [{"text": "...", "count": N}, ...],
        "video_file": "..."   # 仅多视频时存在
    }
    """
    buckets: dict[int, list[str]] = defaultdict(list)
    for d in danmaku_list:
        bucket_idx = int(d['time'] / interval)
        buckets[bucket_idx].append(d['text'])

    summaries = []
    for bucket_idx in sorted(buckets.keys()):
        texts = buckets[bucket_idx]
        top = [{'text': t, 'count': c} for t, c in Counter(texts).most_common(top_n)]
        time_start = round(bucket_idx * interval, 3)
        time_end = round(time_start + interval, 3)
        entry: dict = {
            'time': time_start,
            'time_start': time_start,
            'time_end': time_end,
            'type': 'danmaku_summary',
            'total_count': len(texts),
            'density': round(len(texts) / interval * 60, 1),
            'top_danmaku': top,
        }
        if video_file:
            entry['video_file'] = video_file
        summaries.append(entry)

    return summaries


def parse_srt(srt_path: str) -> list[dict]:
    """解析 SRT 字幕文件。"""
    subtitles = []
    content = Path(srt_path).read_text(encoding='utf-8', errors='replace')
    blocks = re.split(r'\n\s*\n', content.strip())
    for block in blocks:
        lines = block.strip().splitlines()
        if len(lines) < 3:
            continue
        # 时间轴行: 00:00:01,234 --> 00:00:03,456
        time_match = re.match(
            r'(\d{2}):(\d{2}):(\d{2})[,.](\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2})[,.](\d{3})',
            lines[1] if len(lines) > 1 else ''
        )
        if not time_match:
            continue
        h, m, s, ms = int(time_match.group(1)), int(time_match.group(2)), \
                       int(time_match.group(3)), int(time_match.group(4))
        eh, em, es, ems = int(time_match.group(5)), int(time_match.group(6)), \
                          int(time_match.group(7)), int(time_match.group(8))
        start_time = h * 3600 + m * 60 + s + ms / 1000
        end_time = eh * 3600 + em * 60 + es + ems / 1000
        text = ' '.join(lines[2:]).strip()
        # 去除 HTML 标签
        text = re.sub(r'<[^>]+>', '', text)
        if text:
            subtitles.append({'time': start_time, 'end_time': end_time, 'type': 'subtitle', 'text': text})
    return subtitles


def parse_ass(ass_path: str) -> list[dict]:
    """解析 ASS/SSA 字幕文件，提取纯文本。"""
    subtitles = []
    content = Path(ass_path).read_text(encoding='utf-8', errors='replace')
    # 找到 [Events] 段
    in_events = False
    format_fields = []
    for line in content.splitlines():
        line = line.strip()
        if line.startswith('[Events]'):
            in_events = True
            continue
        if in_events and line.startswith('['):
            break
        if in_events and line.startswith('Format:'):
            format_fields = [f.strip() for f in line[7:].split(',')]
        elif in_events and line.startswith('Dialogue:'):
            parts = line[9:].split(',', len(format_fields) - 1)
            if len(parts) < len(format_fields):
                continue
            data = dict(zip(format_fields, parts))
            start_str = data.get('Start', '0:00:00.00')
            end_str = data.get('End', '0:00:00.00')
            # 解析 h:mm:ss.cs 格式
            m = re.match(r'(\d+):(\d{2}):(\d{2})\.(\d{2})', start_str)
            me = re.match(r'(\d+):(\d{2}):(\d{2})\.(\d{2})', end_str)
            if not m:
                continue
            time = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + \
                   int(m.group(3)) + int(m.group(4)) / 100
            end_time = (int(me.group(1)) * 3600 + int(me.group(2)) * 60 +
                        int(me.group(3)) + int(me.group(4)) / 100) if me else time + 2.0
            text = data.get('Text', '')
            # 去除 ASS 特效标签 {\...}
            text = re.sub(r'\{[^}]*\}', '', text).replace('\\N', ' ').strip()
            if text:
                subtitles.append({'time': time, 'end_time': end_time, 'type': 'subtitle', 'text': text})
    return sorted(subtitles, key=lambda x: x['time'])


def parse_bilibili_json_subtitle(json_path: str) -> list[dict]:
    """解析 B站 JSON 字幕文件格式。"""
    subtitles = []
    data = json.loads(Path(json_path).read_text(encoding='utf-8'))
    # B站格式: {"body": [{"from": 0.0, "to": 2.5, "content": "..."}, ...]}
    body = data.get('body', [])
    for item in body:
        time = float(item.get('from', 0))
        end_time = float(item.get('to', time + 2.0))
        text = item.get('content', '').strip()
        if text:
            subtitles.append({'time': time, 'end_time': end_time, 'type': 'subtitle', 'text': text})
    return sorted(subtitles, key=lambda x: x['time'])


def parse_subtitle(subtitle_path: str) -> list[dict]:
    """根据扩展名自动选择字幕解析器。"""
    ext = Path(subtitle_path).suffix.lower()
    if ext == '.srt':
        return parse_srt(subtitle_path)
    elif ext in ('.ass', '.ssa'):
        return parse_ass(subtitle_path)
    elif ext == '.json':
        return parse_bilibili_json_subtitle(subtitle_path)
    else:
        print(f"[警告] 不支持的字幕格式: {ext}，跳过")
        return []


def find_density_peaks(timeline: list[dict], top_n: int = 10, min_gap: float = 10.0) -> list[dict]:
    """找到弹幕密度最高的区间（高能时刻候选）。

    基于 danmaku_summary 条目的 density 字段排序，
    相邻峰值时间差小于 min_gap 秒时只保留密度更高的那个。
    """
    danmaku_items = [x for x in timeline if x['type'] == 'danmaku_summary']
    if not danmaku_items:
        return []
    sorted_items = sorted(danmaku_items, key=lambda x: x.get('density', 0), reverse=True)
    peaks = []
    for item in sorted_items:
        if len(peaks) >= top_n:
            break
        if all(abs(item['time'] - p['time']) > min_gap for p in peaks):
            peaks.append(item)
    return peaks


def main():
    parser = argparse.ArgumentParser(
        description='解析弹幕和字幕，生成时间轴 JSON。支持多个视频各自对应的弹幕和字幕文件。',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例（单视频）:
  %(prog)s --video ep1.mp4 --danmaku ep1.xml --subtitle ep1.srt --output /tmp/timeline.json

示例（多视频）:
  %(prog)s \\
    --video ep1.mp4 --danmaku ep1.xml --subtitle ep1.srt \\
    --video ep2.mp4 --danmaku ep2.xml \\
    --output /tmp/timeline.json
        """
    )
    parser.add_argument('--video', action='append', dest='videos', default=[],
                        help='视频文件路径，可重复传入多次')
    parser.add_argument('--danmaku', action='append', dest='danmakus', required=True,
                        help='Bilibili XML 弹幕文件路径，可重复传入多次，与 --video 按顺序对应')
    parser.add_argument('--subtitle', action='append', dest='subtitles', default=[],
                        help='字幕文件路径（SRT/ASS/JSON，可选），可重复传入多次，与 --video 按顺序对应')
    parser.add_argument('--output', required=True, help='输出 JSON 文件路径')
    parser.add_argument('--interval', type=float, default=5.0,
                        help='弹幕汇总的时间区间大小（秒），默认 5')
    parser.add_argument('--top-danmaku', type=int, default=10,
                        help='每个时间区间保留频次最高的弹幕条数，默认 10')
    parser.add_argument('--include-danmaku', action='store_true', default=False,
                        help='强制在输出中包含弹幕摘要（即使有字幕文件）；对应用户明确要求参考弹幕的场景')
    args = parser.parse_args()

    danmakus = args.danmakus
    # 未传 --video 时用弹幕路径的 stem 作为占位标识
    videos = args.videos if args.videos else [Path(d).stem for d in danmakus]
    subtitles = args.subtitles + [None] * (len(danmakus) - len(args.subtitles))

    if len(videos) != len(danmakus):
        print(f"[错误] --video 数量({len(videos)})与 --danmaku 数量({len(danmakus)})不一致")
        raise SystemExit(1)

    all_timeline = []
    video_stats = []
    total_danmaku = 0
    total_subtitles = 0

    for idx, (video_file, danmaku_path, subtitle_path) in enumerate(zip(videos, danmakus, subtitles), 1):
        prefix = f"[视频{idx}/{len(danmakus)}]"
        print(f"{prefix} 视频: {video_file}")

        # 始终解析弹幕用于统计，是否写入输出由下方规则决定
        print(f"{prefix} 解析弹幕: {danmaku_path}")
        danmaku_list = parse_bilibili_danmaku(danmaku_path)
        print(f"  → 共 {len(danmaku_list)} 条弹幕")

        subtitle_list = []
        if subtitle_path:
            print(f"{prefix} 解析字幕: {subtitle_path}")
            subtitle_list = parse_subtitle(subtitle_path)
            print(f"  → 共 {len(subtitle_list)} 条字幕")
            for item in subtitle_list:
                item['video_file'] = video_file
        else:
            print(f"{prefix} 未提供字幕文件，跳过")

        # 决定是否将弹幕摘要写入输出：
        #   有字幕 且 未指定 --include-danmaku → 只写字幕，弹幕不写入
        #   无字幕                             → 只写弹幕摘要
        #   --include-danmaku                  → 两者都写
        has_subtitle = bool(subtitle_list)
        write_danmaku = args.include_danmaku or not has_subtitle

        if write_danmaku:
            danmaku_summaries = summarize_danmaku_by_interval(
                danmaku_list,
                interval=args.interval,
                top_n=args.top_danmaku,
                video_file=video_file,
            )
            print(f"  → 弹幕按 {args.interval}s 区间汇总，生成 {len(danmaku_summaries)} 个摘要，写入输出")
        else:
            danmaku_summaries = []
            print(f"  → 已有字幕，弹幕摘要不写入输出（使用 --include-danmaku 可强制包含）")

        if has_subtitle and not write_danmaku:
            content_mode = 'subtitle_only'
        elif write_danmaku and not has_subtitle:
            content_mode = 'danmaku_only'
        else:
            content_mode = 'subtitle_and_danmaku'

        video_timeline = sorted(danmaku_summaries + subtitle_list, key=lambda x: x['time'])
        peaks = find_density_peaks(video_timeline, min_gap=args.interval * 2)

        stat: dict = {
            'video_file': video_file,
            'danmaku_file': danmaku_path,
            'subtitle_file': subtitle_path,
            'total_danmaku': len(danmaku_list),
            'total_subtitles': len(subtitle_list),
            'content_mode': content_mode,
        }
        if write_danmaku:
            stat['interval_seconds'] = args.interval
            stat['density_peaks'] = peaks
        video_stats.append(stat)

        all_timeline.extend(video_timeline)
        total_danmaku += len(danmaku_list)
        total_subtitles += len(subtitle_list)

    # 全局高能峰值（仅当输出中有弹幕摘要时才计算）
    danmaku_in_output = [x for x in all_timeline if x['type'] == 'danmaku_summary']
    global_peaks = find_density_peaks(danmaku_in_output, min_gap=args.interval * 2)

    # 整体输出模式
    modes = {s['content_mode'] for s in video_stats}
    if modes == {'subtitle_only'}:
        overall_mode = 'subtitle_only'
    elif modes == {'danmaku_only'}:
        overall_mode = 'danmaku_only'
    else:
        overall_mode = 'mixed'

    result: dict = {
        'content_mode': overall_mode,
        'total_danmaku': total_danmaku,
        'total_subtitles': total_subtitles,
        'videos': video_stats,
        'timeline': all_timeline,
        'summary': {'total_videos': len(videos)},
    }

    if global_peaks:
        result['density_peaks'] = global_peaks
        result['interval_seconds'] = args.interval
        result['summary']['max_density'] = max(
            (x.get('density', 0) for x in danmaku_in_output), default=0
        )
        result['summary']['peak_times'] = [
            {
                'video_file': p.get('video_file', videos[0]),
                'time_start': p['time_start'],
                'time_end': p['time_end'],
                'density': p['density'],
                'top_danmaku': p['top_danmaku'][:3],
            }
            for p in global_peaks[:5]
        ]

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')

    file_size_kb = output_path.stat().st_size / 1024
    print(f"\n时间轴已保存到: {args.output}（{file_size_kb:.1f} KB）")
    print(f"  输出模式: {overall_mode}")
    print(f"  共 {len(videos)} 个视频，{total_danmaku} 条弹幕，{total_subtitles} 条字幕")
    if global_peaks:
        peak_summary = [(p.get('video_file', ''), f"{p['time_start']:.0f}s") for p in global_peaks[:5]]
        print(f"  区间大小: {args.interval}s，全局高能峰值（前5）: {peak_summary}")


if __name__ == '__main__':
    main()
