import json
from pathlib import Path

import yaml


def load_config(path: str) -> dict:
    target = Path(path)
    if target.suffix.lower() in {".yaml", ".yml"}:
        return yaml.safe_load(target.read_text(encoding="utf-8"))
    return json.loads(target.read_text(encoding="utf-8"))
