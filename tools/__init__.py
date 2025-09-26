"""Tooling namespace package bridging src/tools runtime helpers."""

from pkgutil import extend_path
from pathlib import Path

__path__ = extend_path(__path__, __name__)
_shadow_tools = Path(__file__).resolve().parents[1] / "src" / "tools"
if _shadow_tools.exists():
    __path__.append(str(_shadow_tools))
