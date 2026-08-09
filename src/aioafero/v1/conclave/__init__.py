"""Conclave push-event client for the Afero IoT API.

Conclave is Afero's account-scoped TLS push channel. After a short-lived
``conclaveAccess`` token is minted via REST, the client opens a long-lived TLS
connection to ``conclave-stream1.afero.net:443`` and receives ``private``
(``attr_change`` / ``status_change``) and ``public`` (``invalidate`` inventory)
frames whenever devices on the account change — regardless of which client
(app, hub, automation) triggered it.

The Conclave socket is **subscribe-only**: writes still go through REST.
See ``docs/user/conclave.rst`` for setup, lifecycle, and limitations.
"""

__all__ = [
    "FRAME_LOGGER",
    "ConclaveAccess",
    "ConclaveClient",
    "ConclaveFrameDecoder",
    "ConclaveFrameFileHandler",
    "ConclaveStatus",
    "apply_attr_change",
    "apply_invalidate_add",
    "apply_invalidate_remove",
    "apply_public_invalidate",
    "apply_status_change",
    "attach_frame_capture",
    "build_attribute_index",
    "request_conclave_access",
]

from .access import ConclaveAccess, request_conclave_access
from .client import FRAME_LOGGER, ConclaveClient, ConclaveStatus
from .events import (
    apply_attr_change,
    apply_invalidate_add,
    apply_invalidate_remove,
    apply_public_invalidate,
    apply_status_change,
)
from .frame_capture import ConclaveFrameFileHandler, attach_frame_capture
from .frames import ConclaveFrameDecoder
from .semantics import build_attribute_index
