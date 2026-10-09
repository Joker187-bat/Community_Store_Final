# ---The configuration centre. Every value can be overridden with an environment value
import os
from dataclasses import dataclass, field
from pathlib import Path

def _load_dotenv() -> None:
    """.env reader (backend/ .env) so no extra dependencies needed 'yet'. """
    path = Path(__file__).resolve().parents[1] / ".env"
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

_load_dotenv()
_DEFAULT_SECRET = "change-password-during-production-and-use-long-strings"

def _bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in{"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    app_env: str = os.getenv("APP_ENV", "development")
    database_url: str = os.getenv(
        "DATABASE_URL",
        "YOUR_DATABASE_URL"
    )
    jwt_secret: str = os.getenv("JWT_SECRET", _DEFAULT_SECRET)
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = int(os.getenv("ACCESS_TOKEN_ MINUTES", "680"))
    
    #Separated list of origins is allowed to call the API from the browser
    cors_origins: tuple = tuple(
        o.strip()
        for o in os.getenv(
            "CORS_ORIGINS", "http://localhost:8000, http://127.0.0.1:8000, http://localost:5500"
        ).split(",")
        if o.strip()
    )
    
    # email domains treated as institutional (auto-verification on student/faculty)
    institutional_domains: tuple = tuple (
        d.strip().lower()for d in os.getenv("INSTITUTIONAL_DOMAINS", "mycput.ac.za, cput.ac.za").split(",")
    )
    flag_threshold: int = int(os.getenv("FLAG_THRESH(OLD", "3"))
    require_booking_for_review: bool = _bool("REQUIRE_BOOKING_FOR_REVIEW", False)
    seed_demo: bool = _bool("DEMO_SEED", True)
    admin_email: str = os.getenv("ADMIN_EMAIL", "admin@mycput.ac.za")
    admin_password: str = os.getenv("ADMIN_PASSWORD", "ChangeMe123!")
    frontend_dir: str = os.getenv(
        "FRONTEND_DIR", str(Path(__file__).resolve().parents[2] / "frontend")
    )
    
    def validate(self)-> None:
        """ Fail fast on unsafe production configuration"""
        if self.app_env == "production" and self.jwt_secret == _DEFAULT_SECRET:
            raise RuntimeError("JWT_SECRET is not strong enough, please set a strong random value in production")
        if self.app_env == "production" and self.admin_password == "ChangeMe123!":
            raise RuntimeError("ADMIN_PASSWORD must be changed in production.")

settings = Settings()