"""Meta Graph API client — ONLY documented endpoints/fields (Section 9).

Endpoints used (Graph API, version from config, default v21.0):
  GET /me            fields=id,name
  GET /me/accounts   fields=id,name,category,link,tasks,fan_count,access_token
                     (Page access tokens are kept only in the encrypted token store;
                      never logged, never displayed in full, never exported)
  GET /{page-id}     fields=id,name,category,link,fan_count
Documented error mapping: 190 -> token expired/invalid; 10/200 -> permission missing;
4/17/32/613 -> rate limit (limited retries with backoff).
Transport is injectable (object with .get(url, params, timeout)) so automated tests
run on mocked responses — no real Facebook credentials needed (Section 28)."""
import time

GRAPH_BASE = "https://graph.facebook.com"

class MetaAPIError(Exception):
    def __init__(self, message, code=None, http_status=None):
        super().__init__(message); self.code = code; self.http_status = http_status
class TokenExpiredError(MetaAPIError): pass
class PermissionMissingError(MetaAPIError): pass
class RateLimitError(MetaAPIError): pass

RATE_LIMIT_CODES = {4, 17, 32, 613}

class MetaAPIClient:
    def __init__(self, access_token, api_version="v21.0", session=None, max_retries=3, backoff_seconds=1.0):
        if not access_token: raise ValueError("Access token is required")
        self._token = access_token; self.version = api_version
        self.max_retries = max_retries; self.backoff = backoff_seconds
        if session is None:
            import requests; session = requests.Session()
        self.session = session

    def _mask(self, text): return str(text).replace(self._token, "***TOKEN***")

    def _handle(self, resp):
        try: data = resp.json()
        except Exception: data = {}
        if resp.status_code == 200 and "error" not in data: return data
        err = data.get("error", {}) if isinstance(data, dict) else {}
        return err, resp.status_code

    def _raise_for(self, err, status):
        code = err.get("code"); msg = self._mask(err.get("message", f"HTTP {status}"))
        if code == 190: raise TokenExpiredError(msg, code, status)
        if code in (10, 200): raise PermissionMissingError(msg, code, status)
        if code in RATE_LIMIT_CODES: raise RateLimitError(msg, code, status)
        raise MetaAPIError(msg, code, status)

    def _request(self, path, params=None):
        url = f"{GRAPH_BASE}/{self.version}/{path.lstrip('/')}"
        params = {**(params or {}), "access_token": self._token}
        attempt = 0
        while True:
            attempt += 1
            resp = self.session.get(url, params=params, timeout=30)
            out = self._handle(resp)
            if isinstance(out, dict): return out
            err, status = out
            if err.get("code") in RATE_LIMIT_CODES and attempt <= self.max_retries:
                time.sleep(self.backoff * attempt); continue
            self._raise_for(err, status)

    def _request_full_url(self, url):
        resp = self.session.get(url, timeout=30)
        out = self._handle(resp)
        if isinstance(out, dict): return out
        err, status = out; self._raise_for(err, status)

    def get_me(self):
        return self._request("me", {"fields": "id,name"})

    def get_my_pages(self):
        pages = []
        data = self._request("me/accounts",
            {"fields": "id,name,category,link,tasks,fan_count,access_token", "limit": 100})
        while True:
            pages.extend(data.get("data", []))
            nxt = (data.get("paging") or {}).get("next")
            if not nxt: return pages
            data = self._request_full_url(nxt)

    def get_page(self, page_id):
        return self._request(str(page_id), {"fields": "id,name,category,link,fan_count"})
