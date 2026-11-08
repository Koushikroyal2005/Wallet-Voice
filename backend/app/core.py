from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    app_env: str = "development"
    demo_mode: bool = True
    demo_auth_mode: bool = True
    demo_wallet_pin: str = "123456"
    authorization_ttl_seconds: int = 180
    pin_max_attempts: int = 5
    pin_lockout_minutes: int = 5
    require_wallet_login: bool = False
    wallet_session_secret: str = ""
    wallet_session_minutes: int = 30
    wallet_cookie_secure: bool = False
    demo_merchant_name: str = "Indian Railways"
    demo_merchant_api_key: str = "change-this-demo-merchant-key"
    database_url: str = "sqlite:///./aiwallet.db"
    web_allowed_origins: str = "http://localhost:5173,http://localhost:8080"
    default_currency: str = "INR"
    default_daily_spending_limit: int = 1_000_000
    default_per_transaction_limit: int = 500_000
    default_minimum_balance: int = 10_000
    app_timezone: str = "Asia/Kolkata"
    nvidia_api_key: str = ""
    paypal_client_id: str = ""
    paypal_client_secret: str = ""
    paypal_enabled: bool = False
    paypal_mode: str = "sandbox"
    paypal_webhook_id: str = ""
    paypal_base_url: str = "https://api-m.sandbox.paypal.com"
    paypal_checkout_currency: str = "USD"
    paypal_application_currency: str = "INR"
    paypal_demo_inr_per_usd: str = "84"
    paypal_http_timeout_seconds: int = 20
    paypal_oauth_refresh_buffer_seconds: int = 120
    nvidia_enabled: bool = False
    nvidia_whisper_server: str = "grpc.nvcf.nvidia.com:443"
    nvidia_whisper_function_id: str = "b702f636-f60c-4a3d-a6f4-f3568c13bd7d"
    nvidia_whisper_language_code: str = "multi"
    nvidia_whisper_task: str = "transcribe"
    nvidia_whisper_timeout: int = 45
    nvidia_nemotron_base_url: str = "https://integrate.api.nvidia.com/v1"
    nvidia_nemotron_model_id: str = "nvidia/nemotron-3.5-bolt-e4b"
    nvidia_nemotron_temperature: float = 0.2
    nvidia_nemotron_max_tokens: int = 300
    nvidia_nemotron_timeout: int = 30
    nvidia_magpie_synthesis_url: str = "https://877104f7-e885-42b9-8de8-f6e4c6303969.invocation.api.nvcf.nvidia.com/v1/audio/synthesize"
    nvidia_magpie_list_voices_url: str = "https://877104f7-e885-42b9-8de8-f6e4c6303969.invocation.api.nvcf.nvidia.com/v1/audio/list_voices"
    nvidia_magpie_language: str = "en-US"
    nvidia_magpie_voice: str = "Magpie-Multilingual.EN-US.Aria"
    nvidia_magpie_encoding: str = "LINEAR_PCM"
    nvidia_magpie_sample_rate: int = 44100
    voice_max_duration_seconds: int = 60
    voice_max_upload_mb: int = 10
    voice_default_language: str = "en-US"
    voice_history_max_turns: int = 6
    voice_browser_tts_fallback: bool = True

@lru_cache
def settings() -> Settings: return Settings()
