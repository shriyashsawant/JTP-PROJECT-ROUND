from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    database_url: str = "postgresql://auramatch:auramatch_secret@db:5432/auramatch"
    database_reader_url: str | None = None
    model_name: str = "BAAI/bge-small-en-v1.5"
    # BGE models need a query instruction prefix for optimal retrieval.
    # Automatically set based on model family; can be overridden per-model.
    query_instruction: str = "Represent this sentence for searching relevant passages: "
    app_name: str = "AuraMatch AI"
    debug: bool = True
    # Optional - LLM re-ranking/explanation layer is fully skipped when unset.
    groq_api_key: str = ""
    # Comma-separated allowlist of origins permitted to call the API. No
    # cookies/sessions are used anywhere in this app, so credentials are
    # never sent cross-origin - keep this an explicit allowlist rather than
    # "*" regardless.
    cors_origins: str = "http://localhost:3000"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    # Comma-separated list of enabled flag names (e.g. "new_scoring_v2,dupe_v2") -
    # deliberately just a global on/off switch per flag, not a targeting/
    # experimentation service. Lets a new scoring dimension or endpoint ship
    # disabled by default and be flipped on via env var without a redeploy,
    # rather than every change going live the instant it's merged.
    feature_flags: str = ""

    @property
    def feature_flags_set(self) -> set[str]:
        return {f.strip() for f in self.feature_flags.split(",") if f.strip()}

    def is_feature_enabled(self, name: str) -> bool:
        return name in self.feature_flags_set

settings = Settings()
