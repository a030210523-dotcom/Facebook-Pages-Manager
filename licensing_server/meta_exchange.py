"""Server-side Meta token exchange (Section 9). The Meta App Secret lives ONLY in the
server environment (META_APP_SECRET) and is never sent to or embedded in the desktop app.
Documented endpoint: GET https://graph.facebook.com/{version}/oauth/access_token
  grant_type=authorization_code, client_id, client_secret, redirect_uri, code
Then a long-lived token is requested with grant_type=fb_exchange_token (documented)."""
import os

GRAPH_BASE = "https://graph.facebook.com"

def exchange_code(code, redirect_uri, http_get=None, api_version=None):
    app_id = os.environ.get("META_APP_ID", "")
    app_secret = os.environ.get("META_APP_SECRET", "")
    version = api_version or os.environ.get("META_API_VERSION", "v21.0")
    if not app_id or not app_secret:
        raise RuntimeError("Meta app is not configured on the server (META_APP_ID / META_APP_SECRET missing)")
    if http_get is None:
        import requests; http_get = requests.get
    resp = http_get(f"{GRAPH_BASE}/{version}/oauth/access_token", params={
        "client_id": app_id, "client_secret": app_secret,
        "redirect_uri": redirect_uri, "code": code}, timeout=30)
    data = resp.json()
    if "access_token" not in data:
        raise RuntimeError(f"Meta token exchange failed: {data.get('error', {}).get('message', 'unknown error')}")
    short_token = data["access_token"]
    # Long-lived token (documented fb_exchange_token grant). Failure is not fatal:
    # return the short-lived token with its expiry so the desktop can re-auth in time.
    try:
        resp2 = http_get(f"{GRAPH_BASE}/{version}/oauth/access_token", params={
            "grant_type": "fb_exchange_token", "client_id": app_id,
            "client_secret": app_secret, "fb_exchange_token": short_token}, timeout=30)
        data2 = resp2.json()
        if "access_token" in data2: return data2
    except Exception:
        pass
    return data

def fetch_profile_and_pages(access_token, http_get=None, api_version=None):
    """Fetches the just-authorized user's profile + Pages with their own token.
    Documented endpoints only: GET /me and GET /me/accounts (same fields the
    desktop sync engine uses). Used by the invite /connect callback."""
    version = api_version or os.environ.get("META_API_VERSION", "v21.0")
    if http_get is None:
        import requests; http_get = requests.get
    headers = {"Authorization": f"Bearer {access_token}"}
    me = http_get(f"{GRAPH_BASE}/{version}/me", params={"fields": "id,name"},
                  headers=headers, timeout=30).json()
    if "id" not in me:
        raise RuntimeError(f"Meta profile fetch failed: {me.get('error', {}).get('message', 'unknown error')}")
    pages, url = [], f"{GRAPH_BASE}/{version}/me/accounts"
    params = {"fields": "id,name,category,link,tasks,fan_count,access_token", "limit": 100}
    while url:
        resp = http_get(url, params=params, headers=headers, timeout=30).json()
        if "error" in resp:
            raise RuntimeError(f"Meta Pages fetch failed: {resp['error'].get('message', 'unknown error')}")
        pages.extend(resp.get("data", []))
        url = (resp.get("paging") or {}).get("next")
        params = None  # paging.next is a full URL with its own query string
    return {"profile": me, "pages": pages}
