"""Configuration for the operational assistant."""
import os

MODEL = os.getenv("MODEL", "kl/claude-sonnet-4-6")
OPENAI_BASE_URL = "https://api.kryptonlab.id/v1"
KRYPTONLAB_API_KEY = os.getenv("KRYPTONLAB_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
MAX_ITERATIONS = 5
AGENT_MODE = os.getenv("AGENT_MODE", "mock")
INTERNAL_API_PORT = os.getenv("INTERNAL_API_PORT", os.getenv("API_PORT", "8080"))
INTERNAL_API_KEY = os.getenv("API_KEY", "")
