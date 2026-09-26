"""Deterministic Atlas projector: canonical state -> public dashboard projection.

Atlas is non-normative orientation infrastructure.  This package never
decides family membership, authority, pressure state, or verification
results: it projects already-declared machine-readable state (repository
manifests, Commons family records, the Atlas orientation catalog) into a
bounded, schema-validated, provenance-bearing static artifact.

Pipeline::

    discover (host I/O) -> project (pure) -> validate/sanitize (pure)
        -> render (host I/O)

Only ``discover`` and ``render`` touch the filesystem.  Everything between
them is a deterministic function of the discovered source bundle, so the
same meaningful inputs always yield byte-identical semantic output.
"""

PROJECTOR_ID = "mncs-atlas.projector"
PROJECTOR_VERSION = "1"
PROJECTION_SCHEMA = "mncs-atlas.dashboard-projection/v1"
