"""Official Meta OAuth for desktop (Section 9) — Facebook Login dialog + loopback redirect.

Flow implemented:
 1. Build dialog URL at facebook.com/{version}/dialog/oauth with a random `state` (CSRF).
 2. Open it in the user's default browser (we NEVER ask for a Facebook password).
 3. A tiny HTTP server on 127.0.0.1 captures the redirect `code` and verifies `state`.
 4. The code is exchanged for a token by the LICENSING SERVER (server holds the App Secret
    in its environment — the secret is never embedded in or sent from this desktop app),
    via POST {server}/api/meta/token-exchange. A long-lived token is requested by the server.
Permissions requested (least privilege): public_profile, pages_show_list, pages_read_engagement.
For your own Pages these work in Development mode; managing other people's Pages requires
Meta App Review + Advanced Access — the app surfaces 'Permission Missing' until granted."""
import secrets, threading, urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

DEFAULT_SCOPES = ["public_profile", "pages_show_list", "pages_read_engagement"]
REDIRECT_PATH = "/oauth/callback"

def build_oauth_url(app_id, redirect_uri, api_version="v21.0", scopes=None, state=None):
    if not app_id: raise ValueError("Meta App ID is not configured")
    state = state or secrets.token_urlsafe(24)
    q = urllib.parse.urlencode({
        "client_id": app_id, "redirect_uri": redirect_uri, "state": state,
        "scope": ",".join(scopes or DEFAULT_SCOPES), "response_type": "code"})
    return f"https://www.facebook.com/{api_version}/dialog/oauth?{q}", state

def verify_state(returned_state, expected_state):
    import hmac
    return bool(returned_state) and bool(expected_state) and hmac.compare_digest(returned_state, expected_state)

class CallbackResult:
    def __init__(self): self.code = None; self.error = None; self.state = None

def start_callback_server(port=0):
    """Returns (server, result, redirect_uri). Caller waits for result via server.handle_request()."""
    result = CallbackResult()
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            qs = urllib.parse.parse_qs(parsed.query)
            result.code = (qs.get("code") or [None])[0]
            result.state = (qs.get("state") or [None])[0]
            result.error = (qs.get("error_description") or qs.get("error") or [None])[0]
            body = (b"<html><body><h3>Facebook Pages Manager</h3>"
                    b"<p>Authorization received. You can close this tab and return to the app.</p></body></html>")
            self.send_response(200); self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
        def log_message(self, *a): pass  # never log query strings: they carry auth codes
    server = HTTPServer(("127.0.0.1", port), Handler)
    actual_port = server.server_address[1]
    redirect_uri = f"http://127.0.0.1:{actual_port}{REDIRECT_PATH}"
    return server, result, redirect_uri

def exchange_code_via_server(server_url, code, redirect_uri, timeout=30):
    """Desktop sends ONLY the one-time code; the server exchanges it using its env-held App Secret."""
    import requests
    resp = requests.post(f"{server_url.rstrip('/')}/api/meta/token-exchange",
                         json={"code": code, "redirect_uri": redirect_uri}, timeout=timeout)
    data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
    if resp.status_code != 200:
        raise RuntimeError(data.get("detail") or f"Token exchange failed (HTTP {resp.status_code})")
    return data  # {access_token, token_type, expires_in} — caller stores it encrypted immediately
