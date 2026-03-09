"""
视频复刻Callback钩子
"""

from .format_hook import fix_prompt_output, fix_video_output
from .selection_hook import hook_segment_selection
from .cost_calculator_hook import hook_cost_calculator

__all__ = [
    "fix_prompt_output",
    "fix_video_output",
    "hook_segment_selection",
    "hook_cost_calculator",
]
