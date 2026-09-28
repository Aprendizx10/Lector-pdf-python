import json
from pathlib import Path

CONFIG = json.loads((Path(__file__).parent / 'plantillas' / 'unimos_v1.json').read_text(encoding='utf-8'))
