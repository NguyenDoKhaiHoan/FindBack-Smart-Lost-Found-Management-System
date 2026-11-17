from pathlib import Path

from dotenv import load_dotenv

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def load_environment() -> None:
    load_dotenv(REPOSITORY_ROOT / ".env", override=False)
