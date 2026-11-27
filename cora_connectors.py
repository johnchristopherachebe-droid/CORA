"""Small, permission-gated adapters for CORA's explicitly approved external actions.
Credentials are read from environment variables and are never returned to callers.
"""
from __future__ import annotations
import json, os, re, base64, hmac, hashlib, time
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse

class ConnectorError(RuntimeError):
    pass

def _json_request(url: str, token: str, payload=None, method="GET", timeout=12):
    headers = {"Authorization": "Bearer " + token, "Accept": "application/json"}
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode("utf-8")
    req = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(req, timeout=timeout) as response:
            raw = response.read(1_000_000).decode("utf-8", "replace")
            return json.loads(raw) if raw.strip() else {"ok": True}
    except HTTPError as exc:
        raise ConnectorError(f"Provider rejected the request (HTTP {exc.code}).") from None
    except (URLError, TimeoutError, OSError, ValueError):
        raise ConnectorError("The provider could not be reached or returned an invalid response.") from None

def home_assistant_state():
    base = os.getenv("HOME_ASSISTANT_URL", "").strip().rstrip("/")
    token = os.getenv("HOME_ASSISTANT_TOKEN", "").strip()
    if not base or not token:
        raise ConnectorError("Home Assistant is not configured.")
    parsed = urlparse(base)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ConnectorError("Home Assistant must use a valid HTTPS base URL without embedded credentials.")
    data = _json_request(base + "/api/states", token)
    if not isinstance(data, list):
        raise ConnectorError("Home Assistant returned an unexpected state response.")
    return [{"entity_id": x.get("entity_id"), "state": x.get("state"), "friendly_name": (x.get("attributes") or {}).get("friendly_name", "")}
            for x in data if isinstance(x, dict)][:250]

def home_assistant_service(domain: str, service: str, entity_id: str):
    allowed = {"light": {"turn_on", "turn_off", "toggle"}, "switch": {"turn_on", "turn_off", "toggle"}, "scene": {"turn_on"}}
    if domain not in allowed or service not in allowed[domain]:
        raise ConnectorError("Only approved light, switch and scene actions are supported.")
    if not re.fullmatch(r"[a-z0-9_]+\.[a-z0-9_]+", entity_id or ""):
        raise ConnectorError("A valid Home Assistant entity ID is required.")
    if entity_id.split(".", 1)[0] != domain:
        raise ConnectorError("The entity domain does not match the requested action.")
    base = os.getenv("HOME_ASSISTANT_URL", "").strip().rstrip("/")
    token = os.getenv("HOME_ASSISTANT_TOKEN", "").strip()
    if not base or not token:
        raise ConnectorError("Home Assistant is not configured.")
    parsed = urlparse(base)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ConnectorError("Home Assistant must use a valid HTTPS base URL without embedded credentials.")
    return _json_request(base + f"/api/services/{domain}/{service}", token, {"entity_id": entity_id}, "POST")

def whatsapp_send_text(to: str, message: str):
    token = os.getenv("WHATSAPP_ACCESS_TOKEN", "").strip()
    phone_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "").strip()
    if not token or not phone_id:
        raise ConnectorError("WhatsApp Business Cloud API is not configured.")
    if not re.fullmatch(r"\+[1-9]\d{7,14}", to or ""):
        raise ConnectorError("Recipient must be an international phone number beginning with +.")
    message = (message or "").strip()
    if not message or len(message) > 4000:
        raise ConnectorError("Message must contain 1–4000 characters.")
    version = os.getenv("WHATSAPP_GRAPH_API_VERSION", "v21.0").strip()
    if not re.fullmatch(r"v\d+\.\d+", version):
        raise ConnectorError("The configured WhatsApp API version is invalid.")
    payload = {"messaging_product": "whatsapp", "recipient_type": "individual", "to": to.lstrip("+"),
               "type": "text", "text": {"preview_url": False, "body": message}}
    return _json_request(f"https://graph.facebook.com/{version}/{phone_id}/messages", token, payload, "POST")


# Gmail REST adapter. OAuth refresh tokens are kept only in deployment secrets.
def _gmail_access_token():
    client_id = os.getenv("EMAIL_OAUTH_CLIENT_ID", "").strip()
    client_secret = os.getenv("EMAIL_OAUTH_CLIENT_SECRET", "").strip()
    refresh_token = os.getenv("EMAIL_OAUTH_REFRESH_TOKEN", "").strip()
    if not all((client_id, client_secret, refresh_token)):
        raise ConnectorError("Gmail OAuth is not configured.")
    payload = {"client_id": client_id, "client_secret": client_secret,
               "refresh_token": refresh_token, "grant_type": "refresh_token"}
    data = json.dumps(payload).encode("utf-8")
    req = Request("https://oauth2.googleapis.com/token", data=data,
                  headers={"Content-Type": "application/json", "Accept": "application/json"}, method="POST")
    try:
        with urlopen(req, timeout=12) as response:
            result = json.loads(response.read(200_000).decode("utf-8"))
        token = result.get("access_token")
        if not token:
            raise ConnectorError("Google did not return an access token.")
        return token
    except HTTPError as exc:
        raise ConnectorError(f"Google OAuth rejected the refresh request (HTTP {exc.code}).") from None
    except (URLError, TimeoutError, OSError, ValueError):
        raise ConnectorError("Google OAuth could not be reached or returned an invalid response.") from None

def _gmail_request(path, token, payload=None, method="GET"):
    url = "https://gmail.googleapis.com/gmail/v1/users/me/" + path.lstrip("/")
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Authorization": "Bearer " + token, "Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(req, timeout=15) as response:
            raw = response.read(500_000).decode("utf-8", "replace")
            return json.loads(raw) if raw.strip() else {"ok": True}
    except HTTPError as exc:
        raise ConnectorError(f"Gmail rejected the request (HTTP {exc.code}).") from None
    except (URLError, TimeoutError, OSError, ValueError):
        raise ConnectorError("Gmail could not be reached or returned an invalid response.") from None

def gmail_recent_messages(limit=10):
    token = _gmail_access_token()
    limit = max(1, min(int(limit), 20))
    listing = _gmail_request(f"messages?maxResults={limit}&q=in%3Ainbox", token)
    output = []
    for item in listing.get("messages", [])[:limit]:
        msg = _gmail_request(f"messages/{item['id']}?format=metadata&metadataHeaders=From&metadataHeaders=Subject&metadataHeaders=Date", token)
        headers = {h.get("name", "").lower(): h.get("value", "") for h in msg.get("payload", {}).get("headers", [])}
        output.append({"id": msg.get("id"), "thread_id": msg.get("threadId"),
                       "from": headers.get("from", ""), "subject": headers.get("subject", ""),
                       "date": headers.get("date", ""), "snippet": str(msg.get("snippet", ""))[:400],
                       "unread": "UNREAD" in msg.get("labelIds", [])})
    return output

def gmail_send_message(to, subject, body):
    to = (to or "").strip()
    subject = (subject or "").strip()
    body = (body or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", to):
        raise ConnectorError("A valid recipient email address is required.")
    if not subject or len(subject) > 200 or not body or len(body) > 12000:
        raise ConnectorError("Email subject or body is empty or exceeds its allowed length.")
    raw_message = f"To: {to}\r\nSubject: {subject}\r\nMIME-Version: 1.0\r\nContent-Type: text/plain; charset=UTF-8\r\n\r\n{body}"
    raw = base64.urlsafe_b64encode(raw_message.encode("utf-8")).decode("ascii").rstrip("=")
    return _gmail_request("messages/send", _gmail_access_token(), {"raw": raw}, "POST")


def validate_twilio_signature(url: str, params: dict, signature: str, auth_token: str) -> bool:
    """Validate Twilio's X-Twilio-Signature for form-encoded webhooks."""
    if not all((url, signature, auth_token)):
        return False
    canonical = url + "".join(str(key) + str(params[key]) for key in sorted(params))
    expected = base64.b64encode(hmac.new(auth_token.encode(), canonical.encode(), hashlib.sha1).digest()).decode()
    return hmac.compare_digest(expected, signature)
