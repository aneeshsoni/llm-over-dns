from typing import Optional
from openai import OpenAI
import anthropic
from utils.logger import get_logger
from config import OPENAI_API_KEY, ANTHROPIC_API_KEY

# Set up logging
logger = get_logger()

# Initialize LLM clients
openai_client = OpenAI(api_key=OPENAI_API_KEY)
openai_model = "gpt-4.1-mini"  # faster models gpt-4.1-mini

anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
anthropic_model = "claude-sonnet-4-20250514"


def generate_with_openai(prompt: str, model: Optional[str] = None) -> str:
    """Generate response using OpenAI API"""
    model_to_use = model or openai_model
    try:
        response = openai_client.responses.create(
            model=model_to_use,
            instructions="Give me back text only, no markdown or other formatting",
            input=prompt,
        )

        result = response.output_text.strip()

        return result
    except Exception as e:
        logger.error(f"OpenAI API error: {e}")
        raise e


def generate_with_anthropic(
    prompt: str, model: Optional[str] = None, response_schema: Optional[type] = None
) -> str:
    """Generate response using Anthropic Claude API"""
    model_to_use = model or anthropic_model
    try:
        if response_schema:
            # Use structured output with Claude
            response = anthropic_client.messages.create(
                model=model_to_use,
                max_tokens=5000,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
            )
            result = response.content[0].text
        else:
            # Use regular text output
            response = anthropic_client.messages.create(
                model=model_to_use,
                max_tokens=5000,
                messages=[{"role": "user", "content": prompt}],
            )
            result = response.content[0].text

        return result
    except Exception as e:
        logger.error(f"Anthropic API error: {e}")
        raise e


def generate_with_provider(
    prompt: str,
    provider: str = "openai",
    model: Optional[str] = None,
    response_schema: Optional[type] = None,
) -> str:
    """Generate response using specified AI provider"""
    if provider.lower() == "openai":
        return generate_with_openai(prompt, model)
    elif provider.lower() == "anthropic":
        return generate_with_anthropic(prompt, model, response_schema)
    else:
        error_msg = f"Unknown provider: {provider}. Supported providers: openai, gemini, anthropic"
        raise ValueError(error_msg)
