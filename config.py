"""Application configuration classes.

Usage in factory.py::create_app():
    app.config.from_object(config_for_env())

Each class exposes class-level attributes that Flask reads via app.config.from_object().
All os.getenv() calls for runtime config live here; factory.py stays thin.
"""
import os


class BaseConfig:
    """Shared defaults for all environments."""
    # Flask session
    SESSION_TYPE: str = "cachelib"
    SESSION_PERMANENT: bool = False

    # CSRF (Flask-WTF)
    WTF_CSRF_ENABLED: bool = True
    WTF_CSRF_TIME_LIMIT: int = 3600  # seconds

    # Rate limiting (Flask-Limiter)
    RATELIMIT_DEFAULT: str = "300 per minute"
    RATELIMIT_STORAGE_URI: str = "memory://"

    # Database
    PAM_DB_SERVER: str = os.getenv("PAM_DB_SERVER", "")
    PAM_DB_DATABASE: str = os.getenv("PAM_DB_DATABASE", "")
    PAM_DB_USERNAME: str = os.getenv("PAM_DB_USERNAME", "")
    PAM_DB_PASSWORD: str = os.getenv("PAM_DB_PASSWORD", "")

    ORBIT_DB_SERVER: str = os.getenv("ORBIT_DB_SERVER", "")
    ORBIT_DB_DATABASE: str = os.getenv("ORBIT_DB_DATABASE", "")

    # JIRA integration
    JIRA_URL: str = os.getenv("JIRA_URL", "")
    JIRA_USERNAME: str = os.getenv("JIRA_USERNAME", "")
    JIRA_API_TOKEN: str = os.getenv("JIRA_API_TOKEN", "")
    JIRA_PROJECT: str = os.getenv("JIRA_PROJECT", "")


class DevelopmentConfig(BaseConfig):
    """Local development settings."""
    DEBUG: bool = True
    TESTING: bool = False
    # Allow weaker secret in dev (factory.py falls back to a hardcoded dev key anyway)


class ProductionConfig(BaseConfig):
    """Production / Azure App Service settings."""
    DEBUG: bool = False
    TESTING: bool = False


class TestingConfig(BaseConfig):
    """Automated test settings — CSRF disabled so test clients don't need tokens."""
    TESTING: bool = True
    DEBUG: bool = True
    WTF_CSRF_ENABLED: bool = False
    # Use in-memory storage to avoid touching the filesystem during tests
    SESSION_TYPE: str = "filesystem"


_ENV_MAP = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}


def config_for_env(env: str | None = None) -> type:
    """Return the config class for the given environment name.

    Falls back to DevelopmentConfig when FLASK_ENV / the *env* argument is unset.
    """
    if env is None:
        env = os.getenv("FLASK_ENV", "development")
    return _ENV_MAP.get(env.lower(), DevelopmentConfig)
