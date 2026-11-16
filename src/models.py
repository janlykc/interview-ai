"""Request, response, policy and gate result contracts."""

from dataclasses import dataclass
from enum import Enum, auto


@dataclass(frozen=True)
class TenantPolicy:
    tenant_id: str
    rate_limit: float  # Tokens per second.
    burst_limit: int  # Extra tokens above one second of the rate allowance.


@dataclass(frozen=True)
class Request:
    # Assumes the transport adapter has extracted/validated the hostname.
    hostname: str


@dataclass(frozen=True)
class Response:
    status_code: int
    body: str = ""


class GateResult(Enum):
    SUCCESS = auto()
    RATE_LIMITED = auto()


