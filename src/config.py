from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Online Cinema API"
    debug: bool = False

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()