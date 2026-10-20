"""Keep all generated artifacts isolated; verify unchanged upstream sources."""
import hashlib
import json
import os
from pathlib import Path
import sys
import sklearn

PACKAGE = Path(__file__).resolve().parents[1]
SOURCE = PACKAGE.parents[1]
ROOT = PACKAGE / 'work' / ('sklearn-' + sklearn.__version__)
for folder in ['data/derived', 'data/network', 'data/abs', 'results/baseline_investigation',
               'tmp', '.cache/matplotlib']:
    (ROOT / folder).mkdir(parents=True, exist_ok=True)
os.environ['MPLCONFIGDIR'] = str(ROOT / '.cache/matplotlib')
sys.dont_write_bytecode = True


def check_source():
    manifest = json.loads((PACKAGE / 'provenance/source.json').read_text())
    for name, expected in manifest['files'].items():
        if hashlib.sha256((SOURCE / name).read_bytes()).hexdigest() != expected:
            raise RuntimeError(f'Upstream source differs from {manifest["commit"]}: {name}')
    return manifest['commit']


check_source()
