import json
from pathlib import Path

from app.main import create_app

path = Path(__file__).resolve().parents[2] / "frontend/openapi.json"
path.write_text(json.dumps(create_app().openapi(), indent=2) + "\n")
