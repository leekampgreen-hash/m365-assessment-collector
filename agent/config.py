"""Configuration for the operational assistant."""
import os

MODEL = os.getenv("MODEL", "kl/gpt-5.4")
ANALYST_MODEL = os.getenv("ANALYST_MODEL", "kl/gpt-5.6-luna")
OPENAI_BASE_URL = "https://api.kryptonlab.id/v1"
KRYPTONLAB_API_KEY = os.getenv("KRYPTONLAB_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
MAX_ITERATIONS = 5
AGENT_MODE = os.getenv("AGENT_MODE", "mock")
INTERNAL_API_PORT = os.getenv("INTERNAL_API_PORT", os.getenv("API_PORT", "8080"))
INTERNAL_API_KEY = os.getenv("API_KEY", "")
