"""Evidence gathering adapters.

Preferred order is owning repositories, experiments, Commons, previous journal
entries, then optional conversation hints. Missing sources are recorded as
gaps. They are never filled with invented facts.
"""

from .gather import gather_evidence

__all__ = ["gather_evidence"]
