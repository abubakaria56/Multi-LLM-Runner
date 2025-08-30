from pydantic import BaseModel
from dotenv import load_dotenv
import os

load_dotenv()


class Settings(BaseModel):
    kong_api_key: str = os.getenv("KONG_API_KEY", "")
    api_gateway_key: str = os.getenv("API_GATEWAY_KEY", "")
    auth_token: str = os.getenv("AUTH_TOKEN", "")
    base_url: str = os.getenv("KONG_API_BASE_URL", "")

    max_concurrent_evals: int = int(os.getenv("MAX_CONCURRENT_EVALS", "5"))
    enabled_models: list[str] = [
        m.strip() for m in os.getenv("ENABLED_MODELS", "").split(",") if m.strip()
    ]


settings = Settings()
