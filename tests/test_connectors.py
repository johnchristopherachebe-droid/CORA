import os
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from unittest.mock import patch
import cora_connectors

class ConnectorSafetyTests(unittest.TestCase):
    def test_home_assistant_rejects_http(self):
        with patch.dict(os.environ, {"HOME_ASSISTANT_URL":"http://ha.local:8123", "HOME_ASSISTANT_TOKEN":"x"}):
            with self.assertRaises(cora_connectors.ConnectorError):
                cora_connectors.home_assistant_state()

    def test_home_assistant_rejects_unsupported_domain(self):
        with patch.dict(os.environ, {"HOME_ASSISTANT_URL":"https://ha.example", "HOME_ASSISTANT_TOKEN":"x"}):
            with self.assertRaises(cora_connectors.ConnectorError):
                cora_connectors.home_assistant_service("lock", "unlock", "lock.front_door")

    def test_home_assistant_entity_domain_must_match(self):
        with patch.dict(os.environ, {"HOME_ASSISTANT_URL":"https://ha.example", "HOME_ASSISTANT_TOKEN":"x"}):
            with self.assertRaises(cora_connectors.ConnectorError):
                cora_connectors.home_assistant_service("light", "turn_on", "switch.kitchen")

    def test_whatsapp_requires_credentials(self):
        with patch.dict(os.environ, {"WHATSAPP_ACCESS_TOKEN":"", "WHATSAPP_PHONE_NUMBER_ID":""}, clear=False):
            with self.assertRaises(cora_connectors.ConnectorError):
                cora_connectors.whatsapp_send_text("+2348012345678", "Hello")

    def test_whatsapp_validates_recipient(self):
        with patch.dict(os.environ, {"WHATSAPP_ACCESS_TOKEN":"token", "WHATSAPP_PHONE_NUMBER_ID":"123"}):
            with self.assertRaises(cora_connectors.ConnectorError):
                cora_connectors.whatsapp_send_text("not-a-number", "Hello")

class EmailAndTelephonyTests(unittest.TestCase):
    def test_gmail_send_requires_valid_address(self):
        with self.assertRaises(cora_connectors.ConnectorError):
            cora_connectors.gmail_send_message("not-an-email", "Subject", "Body")

    def test_gmail_send_encodes_message_and_uses_gmail_api(self):
        import base64
        with patch.object(cora_connectors, "_gmail_access_token", return_value="token"), \
             patch.object(cora_connectors, "_gmail_request", return_value={"id":"msg-1"}) as call:
            result = cora_connectors.gmail_send_message("person@example.com", "Hello", "Test body")
        self.assertEqual(result["id"], "msg-1")
        raw = call.call_args.args[2]["raw"]
        decoded = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)).decode()
        self.assertIn("To: person@example.com", decoded)
        self.assertIn("Test body", decoded)

    def test_twilio_signature_validation(self):
        import base64, hashlib, hmac
        url = "https://example.com/webhooks/twilio/voice"
        params = {"CallSid":"CA123", "From":"+10000000000"}
        token = "secret"
        canonical = url + "".join(k + params[k] for k in sorted(params))
        signature = base64.b64encode(hmac.new(token.encode(), canonical.encode(), hashlib.sha1).digest()).decode()
        self.assertTrue(cora_connectors.validate_twilio_signature(url, params, signature, token))
        self.assertFalse(cora_connectors.validate_twilio_signature(url, params, "bad", token))


if __name__ == "__main__":
    unittest.main()
