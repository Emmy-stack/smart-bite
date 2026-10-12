from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    APP_NAME: str = "SmartBite API"
    APP_ENV: str = "development"
    DATABASE_URL: str = ""
    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173"
    
    # Clerk configuration
    CLERK_PUBLISHABLE_KEY: Optional[str] = Field(default=None, alias="CLERK_PUBLISHABLE_KEY")
    NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY: Optional[str] = Field(default=None, alias="NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY")
    CLERK_SECRET_KEY: Optional[str] = Field(default=None, alias="CLERK_SECRET_KEY")
    CLERK_JWKS_URL: Optional[str] = Field(default=None, alias="CLERK_JWKS_URL")
    CLERK_ISSUER: Optional[str] = Field(default=None, alias="CLERK_ISSUER")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @property
    def publishable_key(self) -> Optional[str]:
        return self.CLERK_PUBLISHABLE_KEY or self.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY

    @property
    def jwks_url(self) -> Optional[str]:
        if self.CLERK_JWKS_URL:
            return self.CLERK_JWKS_URL
        if self.CLERK_ISSUER:
            return f"{self.CLERK_ISSUER.rstrip('/')}/.well-known/jwks.json"
        return None

    @property
    def issuer(self) -> Optional[str]:
        if self.CLERK_ISSUER:
            return self.CLERK_ISSUER.rstrip('/')
        return None

    def validate_auth_config(self) -> None:
        """Fails clearly if mandatory Clerk verification configuration is missing."""
        if not self.jwks_url or not self.issuer:
            raise RuntimeError(
                "Clerk authentication configuration is missing or incomplete! "
                "Both CLERK_JWKS_URL (or CLERK_ISSUER) and CLERK_ISSUER must be set in environment variables. "
                "Authentication cannot be silently disabled."
            )

settings = Settings()
