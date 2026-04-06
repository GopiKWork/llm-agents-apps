"""Single source of truth for research agent defaults."""

DEFAULT_PROVIDER = "ollama"
DEFAULT_OLLAMA_MODEL = "qwen3.5:0.8b"
DEFAULT_BEDROCK_MODEL = "global.anthropic.claude-sonnet-4-5-20250929-v1:0"


def default_model_for(provider: str) -> str:
    if provider == "ollama":
        return DEFAULT_OLLAMA_MODEL
    return DEFAULT_BEDROCK_MODEL
