"""Atlas family-registry compiler and query model.

The package is intentionally dependency-free.  JSON is a boundary format for
the registry; the compiled artifact is deterministic and is suitable for
local agent preflight without a network request.
"""

from .model import RegistryError, build_registry, load_registry, validate_registry

__all__ = [
    "RegistryError",
    "build_registry",
    "load_registry",
    "validate_registry",
]
