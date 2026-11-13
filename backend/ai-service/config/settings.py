"""Configuration settings and token budget definitions for Zuno AI."""

import os
from pathlib import Path

# Base Paths
BASE_DIR = Path(__file__).resolve().parent.parent

# Model & Server Configuration
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://10.194.51.83:8000").rstrip("/")
LLM_MODEL = os.getenv("LLM_MODEL", "/home/opffarmy/ZERO/models/Qwen3-4B-Q4_K_M.gguf")
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME", "Qwen3-4B-Q4_K_M")

# Active Context Window (Ubuntu llama-server runs with -c 2048)
CONTEXT_SIZE = int(os.getenv("ZUNO_CONTEXT_SIZE", "2048"))
SAFETY_MARGIN = int(os.getenv("ZUNO_SAFETY_MARGIN", "96"))

# Dynamic Output Reserves (Tokens reserved exclusively for model generation)
OUTPUT_BUDGETS = {
    "greeting": 40,
    "simple": 140,
    "simple_english": 140,
    "simple_tamil": 120,
    "detailed": 480,
    "detailed_tamil": 220,
    "debugging": 600,
    "coding": 900,
    "code_generation": 900,
}

# Maximum allowed history turns and char cutoff for conversation handler
MAX_HISTORY_TURNS = int(os.getenv("ZUNO_MAX_HISTORY_TURNS", "10"))
MAX_HISTORY_CHARS = int(os.getenv("ZUNO_MAX_HISTORY_CHARS", "2400"))
