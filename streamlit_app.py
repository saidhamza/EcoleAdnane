import importlib
import runpy
import sys
from pathlib import Path

# Add project root directory to sys.path so modules like models and services resolve properly
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Clear cached local modules so Git updates are immediately active in persistent runners
importlib.invalidate_caches()
for mod in list(sys.modules.keys()):
    if mod in ("models", "services") or mod.startswith(("models.", "services.")):
        del sys.modules[mod]

runpy.run_path(str(PROJECT_ROOT / "app.py"), run_name="__main__")

