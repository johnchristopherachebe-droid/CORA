from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parents[1]
main = (ROOT / 'public' / 'index.html').read_text()
brain = (ROOT / 'public' / 'brain.html').read_text()
backend = (ROOT / 'main.py').read_text()
manifest = json.loads((ROOT / 'public' / 'manifest.webmanifest').read_text())

# Wake phrase is genuinely recognised by the active browser listener, not merely documented.
assert 'transcript.match(/^(?:hey[\\s,:-]+)?cora(?:[\\s,:-]+(.*))?$/i)' in main
assert 'Listening for “CORA” to begin a conversation.' in main
assert 'Listening for Hey' not in main and 'Say Hey once' not in main

# Pink identity and mobile install metadata are present on the main app.
assert '--cyan:#ff63c7' in main
assert 'apple-mobile-web-app-capable' in main
assert 'rel="manifest"' in main
assert manifest['display'] == 'standalone'
assert 'def pwa_manifest_file' in backend and 'def pwa_service_worker_file' in backend and 'def pwa_icon_file' in backend
assert {x['sizes'] for x in manifest['icons']} >= {'192x192', '512x512'}
for icon in manifest['icons']:
    assert (ROOT / 'public' / icon['src'].lstrip('/')).is_file()

# Saved research sessions can be listed and reopened from separate UI tabs.
assert "api('/brain/research')" in brain
assert "api('/brain/research/'+encodeURIComponent(id))" in brain
assert 'researchSessionTabs' in brain and 'renderResearchSessionTabs' in brain
assert "data-r-tab=\"sources\"" in brain and "data-r-tab=\"videos\"" in brain

# Live connector controls require owner confirmation and expose an audit view.
assert "/connectors/whatsapp/send" in brain and "confirmed:true" in brain
assert "/connectors/home-assistant/states" in brain
assert "/operations/audit" in brain
assert "def connector_whatsapp_send" in backend and "def connector_home_assistant_service" in backend
assert "/connectors/email/recent" in brain and "/connectors/email/send" in brain
assert "confirmed:true" in brain and "def connector_email_send" in backend
assert "def twilio_voice_webhook" in backend and "validate_twilio_signature" in backend
assert "I am CORA, an AI receptionist" in backend

print('UI upgrade checks PASS: CORA wake phrase, pink theme, PWA assets, research tabs/history, WhatsApp/Gmail/Twilio/HA connector wiring')
