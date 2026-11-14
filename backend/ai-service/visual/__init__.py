"""Visual explanation and XKCD comic generation module for Zuno."""

from visual.visual_classifier import should_generate_visual
from visual.comic_script_generator import generate_comic_prompt
from visual.comic_client import generate_comic, check_comic_service_health
from visual.visual_manager import maybe_generate_visual

__all__ = [
    "should_generate_visual",
    "generate_comic_prompt",
    "generate_comic",
    "check_comic_service_health",
    "maybe_generate_visual",
]

