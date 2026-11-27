"""Owner approval primitives. The host app must authenticate the owner before calling these."""
from __future__ import annotations
import hashlib, hmac, os, secrets, time
from dataclasses import dataclass

@dataclass(frozen=True)
class Approval:
    action_id: str
    actor_id: str
    issued_at: int
    nonce: str
    signature: str

class ApprovalAuthority:
    def __init__(self, secret: str | None = None, max_age_seconds: int = 300):
        self._secret = (secret or os.getenv("CORA_APPROVAL_SECRET", "")).encode()
        if len(self._secret) < 32:
            raise ValueError("CORA_APPROVAL_SECRET must contain at least 32 characters.")
        self.max_age_seconds = max_age_seconds

    def issue(self, action_id: str, authenticated_owner_id: str) -> Approval:
        if not action_id or not authenticated_owner_id:
            raise ValueError("action_id and authenticated owner identity are required")
        issued = int(time.time())
        nonce = secrets.token_urlsafe(18)
        payload = f"{action_id}|{authenticated_owner_id}|{issued}|{nonce}".encode()
        sig = hmac.new(self._secret, payload, hashlib.sha256).hexdigest()
        return Approval(action_id, authenticated_owner_id, issued, nonce, sig)

    def verify(self, approval: Approval, expected_action_id: str, authenticated_owner_id: str) -> bool:
        if not approval or approval.action_id != expected_action_id:
            return False
        if not authenticated_owner_id or approval.actor_id != authenticated_owner_id:
            return False
        now = int(time.time())
        if approval.issued_at > now or now - approval.issued_at > self.max_age_seconds:
            return False
        payload = f"{approval.action_id}|{approval.actor_id}|{approval.issued_at}|{approval.nonce}".encode()
        expected = hmac.new(self._secret, payload, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, approval.signature)
