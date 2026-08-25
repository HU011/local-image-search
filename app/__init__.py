"""Local image search application package."""

from pathlib import Path
import sys


vendor_dir = Path(__file__).resolve().parents[1] / "vendor"
if vendor_dir.is_dir() and str(vendor_dir) not in sys.path:
    sys.path.insert(0, str(vendor_dir))
