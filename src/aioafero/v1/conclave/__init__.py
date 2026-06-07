"""Conclave push-event client for the Afero IoT API.

Conclave is Afero's account-scoped TLS push channel. After a short-lived
``conclaveAccess`` token is minted via REST, the client opens a long-lived TLS
connection to ``conclave-stream1.afero.net:443`` and receives ``private`` /
``attr_change`` / ``status_change`` frames whenever any device on the account
changes state — regardless of which client (app, hub, automation) triggered it.

The Conclave socket is **subscribe-only**: writes still go through REST.
See ``docs/user/conclave.rst`` for setup, lifecycle, and limitations.
"""

__all__ = [
    "ConclaveAccess",
    "ConclaveClient",
    "ConclaveFrameDecoder",
    "ConclaveStatus",
    "apply_attr_change",
    "apply_status_change",
    "build_attribute_index",
    "request_conclave_access",
]

from .access import ConclaveAccess, request_conclave_access
from .client import ConclaveClient, ConclaveStatus
from .events import apply_attr_change, apply_status_change
from .frames import ConclaveFrameDecoder
from .semantics import build_attribute_index
