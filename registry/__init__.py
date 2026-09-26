"""Atlas family-registry compiler and query model.

The package is intentionally dependency-free.  JSON is a boundary format for
the registry; the compiled artifact is deterministic and is suitable for
local orientation without a network request. Authoritative family preflight
belongs to Language Service.
"""

from .model import RegistryError, build_registry, load_registry, validate_registry

__all__ = [
    "RegistryError",
    "build_registry",
    "load_registry",
    "validate_registry",
]
