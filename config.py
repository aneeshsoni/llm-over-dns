import os
from dotenv import load_dotenv

load_dotenv()

# LLM API keys
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# DNS Server API key for access control (optional)
DNS_API_KEY = os.getenv("DNS_API_KEY")
