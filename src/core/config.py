from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Anthropic Claude
    anthropic_api_key: str
    claude_model_heavy: str = "claude-sonnet-4-6"   # Sonnet 4.6 : 1.7× moins cher qu'Opus
    claude_model_light: str = "claude-haiku-4-5-20251001"

    # Google Gemini (vision — gratuit jusqu'à 1 M tokens/jour)
    google_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"
    # "gemini" = Gemini Flash pour transcription | "claude" = Claude pour tout
    vision_provider: str = "claude"

    # DeepSeek (correction V3 + diagnostic R1)
    deepseek_api_key: str = ""
    deepseek_model_v3: str = "deepseek-chat"       # DeepSeek V3 — correction
    deepseek_model_r1: str = "deepseek-reasoner"   # DeepSeek R1 — diagnostic

    # Mistral (remédiation — français académique natif)
    mistral_api_key: str = ""
    mistral_model: str = "mistral-small-latest"

    # Seuils pipeline
    confidence_review_threshold: float = 0.75
    image_min_resolution: int = 1000
    image_blur_threshold: float = 100.0

    # Stockage
    runs_dir: str = "./runs"
    subject: str = "mathematics"


settings = Settings()
