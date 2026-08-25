"""Keep the portable service isolated from bundled base-Python site packages."""

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent
BASE_SITE_PACKAGES = (ROOT / "python" / "Lib" / "site-packages").resolve()


def _under_path(left: str, right: Path) -> bool:
    try:
        resolved = Path(left).resolve()
    except OSError:
        return False
    return resolved == right or right in resolved.parents


sys.path[:] = [
    item for item in sys.path if not _under_path(item, BASE_SITE_PACKAGES)
]
