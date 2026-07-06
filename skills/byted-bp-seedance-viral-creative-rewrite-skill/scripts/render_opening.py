#!/usr/bin/env python3
# Copyright (c) 2026 BytePlus. All rights reserved.
# SPDX-License-Identifier: Proprietary
"""Render the canonical opening prompt."""

from __future__ import annotations

import argparse
from pathlib import Path

from media_links import media_markdown


BASE_DIR = Path(__file__).resolve().parent.parent


def print_template_video_note(language: str) -> None:
    if language == "en":
        print("\nTemplate video:\nThis repository package does not include bundled `.mp4` example videos. Provide a local template video path or an accessible template video URL at runtime.")
        return
    print("\n模板视频（结构参考）：\n当前仓库提交包不包含内置 `.mp4` 示例视频。运行时请提供本地模板视频路径，或提供可访问的视频 URL。")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render viral creative rewrite opening prompt.")
    parser.add_argument("--ui-language", choices=["zh", "en"], default="zh")
    parser.add_argument("--media-style", choices=["codex", "link", "both"], default="codex", help="Media markdown style: codex=![](path) inline (default); link=[](file:// url) clickable; both")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    template = BASE_DIR / "assets" / "examples" / "template_video.mp4"
    product = BASE_DIR / "assets" / "examples" / "source_product.jpg"
    if args.ui_language == "en":
        print("This skill recreates an ad template for a new product: I first understand a reference ad video's hook, shot rhythm, satisfaction moments, and ending structure, then use your product image as the product truth to generate a new short ad video.")
        print("\nThere are two inputs: a template video and a product image.")
        print("\n- Template video: the reference ad structure. I borrow pacing, shot order, camera language, actions, satisfaction points, and CTA function. I do not inherit its product, brand, packaging, claims, subtitles, or selling points.")
        print("- Product image: the source of truth for the generated product identity, appearance, packaging, visible ingredients, and confirmed selling points.")
        if template.exists():
            print(f"\nTemplate video:\n{media_markdown('Template video', template, style=args.media_style)}")
        else:
            print_template_video_note("en")
        print(f"\nDefault product image:\n{media_markdown('Default product image', product, style=args.media_style)}")
        print("\nFor better results, keep the template video and product image close in category or use case. Also avoid product images with recognizable real human faces for real generation.")
        print("\nFlow:\nNo-cost rehearsal, or real analysis preview / real generation.")
        print("\nMedia:\nProvide a local template video path or accessible video URL. Use the default example product image or your own product image?")
        print("\nProduct and generation direction:\nProduct identity / must-keep selling points, target audience, and goal. Default output is 9:16, 720p, with original unrecognizable instrumental background music.")
        print("\nReal generation requires a ModelArk API Key and Seedance 2.0 prepaid resources. In the real analysis/generation flow, I first show the brief, strategy, forbidden carryover, and risk controls; after you approve the direction, we move to the Seedance submission step.")
        return

    print("这个 skill 做的是广告模板复刻：我会先理解一个参考广告视频的开头钩子、镜头节奏、产品爽点和收尾方式，再用你的商品图作为产品真相，生成一条新的商品广告视频。")
    print("\n这里有两个输入：模板视频和商品图。")
    print("\n- 模板视频：只提供广告结构参考，比如节奏、镜头顺序、动作、爽点和 CTA 结构；不会继承里面的商品、品牌、包装、字幕或卖点。")
    print("- 商品图：提供最终视频里的商品身份、外观、包装、可见成分和确认卖点；生成结果要围绕这张图里的商品。")
    if template.exists():
        print(f"\n模板视频（结构参考）：\n{media_markdown('模板视频', template, style=args.media_style)}")
    else:
        print_template_video_note("zh")
    print(f"\n默认商品图（产品真相/彩排示例）：\n{media_markdown('默认商品图', product, style=args.media_style)}")
    print("\n更稳定的组合通常是同品类或相近使用场景，比如饮品配饮品/食品广告模板，美妆配美妆/护肤模板。跨品类也能借节奏和镜头结构，但商品一致性和场景贴合度会弱一些。")
    print("\n另外，真实生成时上传的商品图尽量不要包含可识别真人脸。更推荐商品本体、包装图、手持局部或不可识别身体局部；清晰真人脸可能触发模型风控，也可能让后续人物/脸部生成不稳定。")
    print("\n先走哪种流程：\n无成本彩排 或 真实分析预览/正式生成")
    print("\n媒体选择：\n模板视频用本地路径还是视频 URL？商品图用默认示例还是你自己的商品图？")
    print("\n商品和生成方向：\n商品身份/必须保留卖点、目标人群、目标，比如提高点击率/强化开头；默认输出为 9:16、720p、带原创不可识别无歌词背景音乐。")
    print("\n正式生成需要 ModelArk API Key，并且账号需要有 Seedance 2.0 可用资源包或权益。进入真实分析/生成流程后，我会先给你看 brief、策略、禁止继承项和风险控制；你确认方向后，才会进入提交 Seedance 的下一步。")


if __name__ == "__main__":
    main()
