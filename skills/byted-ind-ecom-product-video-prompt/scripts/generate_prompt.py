#!/usr/bin/env python3
"""
Product Video Prompt Generator

This script generates video generation prompts for e-commerce products
using the Seedance 2.0 "Three-Layer Skeleton" methodology.

Usage:
    python generate_prompt.py --product "White Sneakers" --images img1.jpg --category footwear
"""

import argparse
import json
from typing import List, Optional
from dataclasses import dataclass, asdict
from enum import Enum

class Category(Enum):
    FOOTWEAR = "footwear"
    APPAREL = "apparel"
    BAGS = "bags"
    BEAUTY = "beauty"
    ACCESSORIES_3C = "3c_accessories"
    GENERAL = "general"

@dataclass
class GlobalSetup:
    """Layer 1: Global Setup - Worldview of the video"""
    product: str
    reference_images: List[str]
    character: str
    scene: str
    composition: str
    lighting: str
    style: str = "Realistic style, authentic filming, cinematic quality"
    
    def to_prompt(self) -> str:
        refs = ", ".join([f"[Image{i+1}]" for i in range(len(self.reference_images))])
        return f"""## Global Setup
- **Product**: {self.product} (Reference {refs})
- **Character**: {self.character}
- **Scene**: {self.scene}
- **Composition**: {self.composition}
- **Lighting**: {self.lighting}
- **Style**: {self.style}"""

@dataclass
class Shot:
    """Individual shot in the timeline"""
    start_time: int
    end_time: int
    goal: str
    shot_type: str
    content: str
    camera_move: str
    visual_effect: str
    reference_image: Optional[str] = None
    
    def to_prompt(self) -> str:
        ref = f" (Reference {self.reference_image})" if self.reference_image else ""
        return f'    **{self.start_time}s-{self.end_time}s ({self.goal})**: {self.shot_type} displays {self.content}{ref}, camera {self.camera_move}, {self.visual_effect}.'

@dataclass
class ShotTimeline:
    """Layer 2: Shot List Timeline - Story rhythm"""
    shots: List[Shot]
    
    def to_prompt(self) -> str:
        shots_text = "\n".join([shot.to_prompt() for shot in self.shots])
        return f"""## Shot Timeline Script
{shots_text}"""

@dataclass
class Constraints:
    """Layer 3: Constraints & Output Specs - Quality assurance"""
    consistency: str
    character_stability: Optional[str]
    aesthetic: str
    duration: str = "15s"
    aspect_ratio: str = "16:9"
    style_intensity: str = "Medium"
    rhythm: str = "Relaxed"
    
    def to_prompt(self) -> str:
        char_stab = f"- **Character Stability**: {self.character_stability}\n" if self.character_stability else ""
        return f"""## Constraints & Output Specifications
- **Consistency**: {self.consistency}
{char_stab}- **Aesthetic Requirements**: {self.aesthetic}
- **Seedance 2.0 Parameters**: Duration [{self.duration}], Aspect Ratio [{self.aspect_ratio}], Style Intensity [{self.style_intensity}], Rhythm [{self.rhythm}]."""

@dataclass
class VideoPrompt:
    """Complete video generation prompt"""
    global_setup: GlobalSetup
    shot_timeline: ShotTimeline
    constraints: Constraints
    
    def to_prompt(self) -> str:
        return f"""{self.global_setup.to_prompt()}

{self.shot_timeline.to_prompt()}

{self.constraints.to_prompt()}
"""


def get_category_defaults(category: Category) -> dict:
    """Get default values for specific categories"""
    defaults = {
        Category.FOOTWEAR: {
            "scene": "Minimalist modern urban industrial showroom with geometric display platforms",
            "composition": "Center composition with stable balanced composition",
            "lighting": "Transparent natural soft light with delicate rim light",
            "character": "A sunny, energetic, fashion-sporty male model",
        },
        Category.APPAREL: {
            "scene": "Minimalist bright indoor studio with soft background",
            "composition": "Center composition with stable balanced composition",
            "lighting": "Natural soft light with subtle rim light",
            "character": "A fashionable young model with natural styling",
        },
        Category.BAGS: {
            "scene": "Minimalist modern warm sunshine terrace with wooden coffee table and green plants",
            "composition": "Classic balanced center composition",
            "lighting": "Natural bright side-back soft light",
            "character": "No character",
        },
        Category.BEAUTY: {
            "scene": "Soft light photography studio with pure flesh pink background",
            "composition": "Center composition emphasizing product details",
            "lighting": "Clean and soft studio lighting with no obvious shadows",
            "character": "Clean and elegant female hand close-ups only",
        },
        Category.ACCESSORIES_3C: {
            "scene": "Cyberpunk-style urban night scene full of neon light and metal texture",
            "composition": "Center composition with dramatic lighting",
            "lighting": "High-contrast dramatic lighting with sharp rim light",
            "character": "Clean and elegant hand close-ups only",
        },
        Category.GENERAL: {
            "scene": "Clean minimalist studio environment",
            "composition": "Center composition with balanced framing",
            "lighting": "Natural soft lighting",
            "character": "No character",
        },
    }
    return defaults.get(category, defaults[Category.GENERAL])


def create_five_shot_timeline(product: str, ref_images: List[str], category: Category) -> ShotTimeline:
    """Create standard 5-shot timeline (0-15s)"""
    
    # Map category to shot content patterns
    shot_patterns = {
        Category.FOOTWEAR: {
            "intro": f"Full shot displays {product} placed on minimalist geometric display platform, with smooth camera pull-back, demonstrating product and space openness",
            "core": f"Medium shot side-films model walking steadily wearing {product}, camera pan following, emphasizing thick sole silhouette and stable support feeling on landing",
            "interaction": f"Medium shot captures model standing still by window, natural afternoon light/shadow slowly shifting on shoe surface, mapping out shoe material layer changes",
            "multi_angle": f"Uses medium-long shot surround camera movement, as camera smoothly moves right, comprehensively displays {product}'s spatial stereoscopic contour and movement lines",
            "closing": f"Under full shot lens, {product} freezes in elegant light/shadow environment, background blur processing, creating high-end minimalist fashion casual atmosphere"
        },
        Category.BAGS: {
            "intro": f"Full shot lens, multiple {product} arranged staggered on pure stone steps, with smooth camera push-in, demonstrating product overall shape and scene harmonious beauty",
            "core": f"Medium shot, {product} quietly placed on wooden coffee table, breeze blows, light/shadow moves on canvas material, demonstrating its firmness and soft texture",
            "interaction": f"Close-up lens, focus transitions from background blurred green plants to {product}'s handle part, demonstrating its leather stitching details",
            "multi_angle": f"Full shot surround lens, smoothly arcs from side-back to front, demonstrating different color {product} in space's stereoscopic silhouette and color layers",
            "closing": f"Medium shot freeze-frame, multiple {product} in soft afternoon light/shadow quietly placed, through stable camera pull-back, creating high-end minimalist fashion brand mood"
        },
        "default": {
            "intro": f"Full shot displays {product} in clean environment, with smooth camera movement, establishing overall visual impression",
            "core": f"Medium/close-up shot focuses on {product}'s key features and textures, demonstrating core selling points",
            "interaction": f"Medium shot captures {product} with environmental elements interaction, creating authentic atmosphere",
            "multi_angle": f"Dynamic camera movement shows {product} from multiple angles, satisfying exploration desire",
            "closing": f"Full/medium shot freeze frame with elegant lighting, completing brand tonality transmission"
        }
    }
    
    patterns = shot_patterns.get(category, shot_patterns["default"])
    
    shots = [
        Shot(0, 3, "Introduce Subject", "Full shot/Full shot", patterns["intro"], "smooth pull-back/push-in", "establishing overall visual impression"),
        Shot(3, 6, "Core Texture", "Medium shot/Close-up", patterns["core"], "fixed camera/slow push", "demonstrating key selling points"),
        Shot(6, 9, "Scene Interaction", "Medium shot/Full shot", patterns["interaction"], "follow/pan", "creating authentic atmosphere"),
        Shot(9, 12, "Multi-Angle Display", "Medium shot/Close-up", patterns["multi_angle"], "surround/rotate/arc", "showing from multiple angles"),
        Shot(12, 15, "Brand Closing", "Full shot/Medium shot", patterns["closing"], "freeze frame with elegant lighting", "completing brand transmission")
    ]
    
    return ShotTimeline(shots)


def main():
    parser = argparse.ArgumentParser(
        description="Generate video generation prompts for e-commerce products using Seedance 2.0 methodology"
    )
    parser.add_argument("--product", "-p", required=True, help="Product name/description")
    parser.add_argument("--images", "-i", nargs="+", required=True, help="Reference image paths/URLs")
    parser.add_argument("--category", "-c", type=Category, default=Category.GENERAL,
                      choices=list(Category), help="Product category")
    parser.add_argument("--character", help="Character description (auto-selected by category if not provided)")
    parser.add_argument("--aspect-ratio", "-ar", default="16:9", choices=["16:9", "9:16", "1:1", "4:3"],
                      help="Video aspect ratio")
    parser.add_argument("--duration", "-d", default="15s", help="Video duration")
    parser.add_argument("--output", "-o", help="Output file path (default: print to stdout)")
    
    args = parser.parse_args()
    
    # Get category defaults
    defaults = get_category_defaults(args.category)
    
    # Build Global Setup
    global_setup = GlobalSetup(
        product=args.product,
        reference_images=args.images,
        character=args.character or defaults["character"],
        scene=defaults["scene"],
        composition=defaults["composition"],
        lighting=defaults["lighting"]
    )
    
    # Build Shot Timeline
    shot_timeline = create_five_shot_timeline(args.product, args.images, args.category)
    
    # Build Constraints
    constraints = Constraints(
        consistency=f"{args.product} must strictly match reference image(s), no deformation, no clipping",
        character_stability="Actions authentic and normal, facial features stable and clear, no hand distortion" if "No character" not in (args.character or defaults["character"]) else None,
        aesthetic="Ultra-clear 8K quality, natural transparent light/shadow, authentic colors, appropriate background blur",
        duration=args.duration,
        aspect_ratio=args.aspect_ratio
    )
    
    # Build complete prompt
    video_prompt = VideoPrompt(global_setup, shot_timeline, constraints)
    final_prompt = video_prompt.to_prompt()
    
    # Output
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(final_prompt)
        print(f"Prompt saved to: {args.output}")
    else:
        print(final_prompt)


if __name__ == "__main__":
    main()
