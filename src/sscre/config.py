import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str | None = None

    @classmethod
    def from_environment(cls) -> "Settings":
        return cls(database_url=os.getenv("SSCRE_DATABASE_URL"))
