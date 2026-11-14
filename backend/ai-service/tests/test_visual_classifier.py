import pytest
from visual.visual_classifier import should_generate_visual
from visual.comic_script_generator import generate_comic_prompt
from visual.relevance_checker import validate_comic_payload


def test_visual_classifier_explicit_keywords():
    assert should_generate_visual("draw a comic about python") is True
    assert should_generate_visual("can you illustrate this concept") is True
    assert should_generate_visual("show an xkcd cartoon about coding") is True


def test_visual_classifier_conceptual_detailed():
    assert should_generate_visual("Explain how an API works", intent="detailed") is True
    assert should_generate_visual("How does a neural network learn?", intent="detailed") is True
    assert should_generate_visual("What is the difference between Git merge and rebase?", intent="coding") is True


def test_visual_classifier_blacklist():
    assert should_generate_visual("hi", intent="greeting") is False
    assert should_generate_visual("hello there", intent="greeting") is False
    assert should_generate_visual("today what day", intent="simple") is False
    assert should_generate_visual("what is the time", intent="simple") is False
    assert should_generate_visual("5 + 5", intent="simple") is False


def test_generate_comic_prompt():
    title, prompt = generate_comic_prompt("Explain how an API works")
    assert "API" in title or "Api" in title
    assert "stick figure" in prompt.lower()
    assert "four-panel" in prompt.lower()


def test_validate_comic_payload():
    assert validate_comic_payload(None) is False
    assert validate_comic_payload({"success": False}) is False
    assert validate_comic_payload({"success": True, "imageUrl": "http://10.32.13.83:8002/images/zero-123.png"}) is True
    assert validate_comic_payload({"success": True, "imageUrl": "/images/zero-123.png"}) is True

