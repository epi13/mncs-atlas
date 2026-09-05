"""Atlas admission and capability brokerage.

Atlas grants entry, context, discovery, and access to capability requests.
It does not grant trust merely by identity and never duplicates the
authoritative policy logic owned by other MNCS components.
"""

from .bypass import PROTECTED_PATH_PREFIXES, scan
from .denials import build_denial, denial_from_decision
from .model import (
    AdmissionError,
    Grant,
    Participant,
    Session,
    new_outside_session,
)
from .orientation import (
    human_orientation,
    load_admission_map,
    load_atlas_map,
    machine_orientation,
)
from .router import (
    ActionsAdapter,
    AdmissionPostureAdapter,
    AuthorityAdapter,
    AuthorityFinding,
    CommonsAdapter,
    FabricAdapter,
    ForgeAdapter,
    LifecycleAdapter,
    Query,
    RightsAdapter,
    Router,
)
from .vocabulary import (
    ADMISSION_STATES,
    CAPABILITIES,
    LIFECYCLE_GATE,
    LIFECYCLE_STATES,
    RIGHTS_SCOPE_FOR_CAPABILITY,
    SENSITIVITIES,
    SENSITIVITY_LADDER,
    STATUSES,
    VERDICTS,
    VOCABULARY_VERSION,
    UnknownCapabilityError,
    capability_ids,
    describe_capability,
    get_capability,
)

__all__ = [
    "ADMISSION_STATES",
    "CAPABILITIES",
    "LIFECYCLE_GATE",
    "LIFECYCLE_STATES",
    "PROTECTED_PATH_PREFIXES",
    "RIGHTS_SCOPE_FOR_CAPABILITY",
    "SENSITIVITIES",
    "SENSITIVITY_LADDER",
    "STATUSES",
    "VERDICTS",
    "VOCABULARY_VERSION",
    "ActionsAdapter",
    "AdmissionError",
    "AdmissionPostureAdapter",
    "AuthorityAdapter",
    "AuthorityFinding",
    "CommonsAdapter",
    "FabricAdapter",
    "ForgeAdapter",
    "Grant",
    "LifecycleAdapter",
    "Participant",
    "Query",
    "RightsAdapter",
    "Router",
    "Session",
    "UnknownCapabilityError",
    "build_denial",
    "capability_ids",
    "denial_from_decision",
    "describe_capability",
    "get_capability",
    "human_orientation",
    "load_admission_map",
    "load_atlas_map",
    "machine_orientation",
    "new_outside_session",
    "scan",
]
