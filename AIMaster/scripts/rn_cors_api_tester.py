#!/usr/bin/env python3
"""
RN-like CORS API Tester (robust single-file version)

Simulates a React Native client calling your API endpoints with appropriate
CORS headers. Includes:
  • Auto port discovery via GET {SCHEME}://HOST:PORT{BASE_PATH}/config
  • Strict CORS validation (ACAO/ACAC/ACAM/ACAH) with clear notes
  • Optional cookie/withCredentials flow checks (--with-cookies)
  • Header and query token auth paths
  • Decks + Routines CRUD flow
  • Robust logging and deterministic exit codes

Exit codes:
  0  all steps OK
  1  could not obtain auth (token/cookie)
  2  some steps failed (functional)
  3  port discovery failed
  4  hard CORS validation failure

Usage examples:
  python endpoints.py --host 161.153.217.110 --port auto --origin http://localhost:8081
  python endpoints.py --host 161.153.217.110 --port 8080 --origin http://localhost:8081 --with-cookies
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from dataclasses import dataclass
from typing import Dict, Optional, Tuple, List

import requests

# ========================
# Defaults (override via CLI or env)
# ========================
SERVER_IP   = os.getenv("API_HOST", "161.153.217.110")
PORT        = int(os.getenv("API_PORT", "8080"))
SCHEME_DEF  = os.getenv("API_SCHEME", "http")           # http | https
BASE_PATH_DEF = os.getenv("API_BASE_PATH", "/api")
ORIGIN_DEF  = os.getenv("API_ORIGIN", "http://localhost:8081")
TIMEOUT_DEF = float(os.getenv("API_TIMEOUT", "30"))

TEST_EMAIL    = os.getenv("API_TEST_EMAIL", "rn.tester@example.com")
TEST_PASSWORD = os.getenv("API_TEST_PASSWORD", "rn_test_pw")

# ========================
# Data structures
# ========================
@dataclass
class Result:
    name: str
    ok: bool
    status: Optional[int] = None
    notes: str = ""

# ========================
# Pretty/Log helpers
# ========================

def pretty_json(data) -> str:
    try:
        return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False)
    except Exception:
        return str(data)


def log_header(title: str) -> None:
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


def print_req(method: str, url: str, headers: Dict[str, str], body: Optional[dict] = None) -> None:
    print(f"Request: {method} {url}")
    hmask = dict(headers)
    if "Authorization" in hmask:
        tok = hmask["Authorization"]
        hmask["Authorization"] = tok[:16] + "…" if isinstance(tok, str) and len(tok) > 16 else tok
    print("Headers:")
    for k, v in hmask.items():
        print(f"  {k}: {v}")
    if body is not None:
        print("Body:")
        print(pretty_json(body))


def print_res(r: requests.Response) -> None:
    print(f"Status: {r.status_code}")
    print("CORS-relevant response headers:")
    for hk in [
        "access-control-allow-origin",
        "access-control-allow-headers",
        "access-control-allow-methods",
        "access-control-allow-credentials",
        "vary",
        "content-type",
        "set-cookie",
    ]:
        if hk in r.headers:
            print(f"  {hk}: {r.headers[hk]}")
    try:
        data = r.json()
        print("JSON:")
        print(pretty_json(data))
    except Exception:
        print("Body:")
        print(r.text[:2000])

# ========================
# HTTP helpers
# ========================

def preflight(sess: requests.Session, origin: str, url: str, method: str, req_headers: Optional[str] = None, timeout: float = TIMEOUT_DEF) -> requests.Response:
    headers = {
        "Origin": origin,
        "Access-Control-Request-Method": method,
    }
    if req_headers:
        headers["Access-Control-Request-Headers"] = req_headers
    print_req("OPTIONS", url, headers)
    r = sess.options(url, headers=headers, timeout=timeout)
    print_res(r)
    return r


def call(sess: requests.Session, origin: str, method: str, url: str, token: Optional[str] = None, body: Optional[dict] = None, timeout: float = TIMEOUT_DEF) -> requests.Response:
    headers = {
        "Origin": origin,
        "Accept": "application/json",
    }
    if body is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = token
    print_req(method, url, headers, body)
    func = getattr(sess, method.lower())
    if body is not None:
        r = func(url, headers=headers, json=body, timeout=timeout)
    else:
        r = func(url, headers=headers, timeout=timeout)
    print_res(r)
    return r

# ========================
# CORS validation helpers
# ========================

def cors_ok_for_simple(r: requests.Response, origin: str, want_credentials: bool = False) -> Tuple[bool, str]:
    """Validate minimal browser CORS rules.
    - ACAO must be '*' or echo the Origin. If want_credentials=True, '*' is invalid.
    - If want_credentials=True, ACAC must be 'true'.
    """
    acao = r.headers.get("Access-Control-Allow-Origin")
    acac = r.headers.get("Access-Control-Allow-Credentials")

    if acao is None:
        return False, "missing Access-Control-Allow-Origin"

    if want_credentials:
        if acao == "*":
            return False, "ACAO '*' not allowed with credentials"
        if acao != origin:
            return False, f"ACAO should echo origin ({origin}), got {acao}"
        if (acac or "").lower() != "true":
            return False, "ACAC must be 'true' with credentials"
    else:
        if acao not in ("*", origin):
            return False, f"ACAO should be '*' or {origin}, got {acao}"
    return True, ""


def cors_ok_for_preflight(r: requests.Response, origin: str, method: str, req_headers: Optional[str], want_credentials: bool = False) -> Tuple[bool, str]:
    ok, note = cors_ok_for_simple(r, origin, want_credentials)
    if not ok:
        return ok, note
    acam = r.headers.get("Access-Control-Allow-Methods", "")
    if method.upper() not in acam.upper():
        return False, f"ACAM does not include {method}"
    if req_headers:
        requested = {h.strip().lower() for h in req_headers.split(',') if h.strip()}
        acah = r.headers.get("Access-Control-Allow-Headers", "").lower()
        missing = [h for h in requested if h not in acah]
        if missing:
            return False, f"ACAH missing: {', '.join(missing)}"
    return True, ""

# ========================
# Discovery
# ========================

def discover_port(host: str, base_path: str, candidates: List[int], scheme: str, origin: str) -> Tuple[Optional[int], List[Tuple[int, str]]]:
    attempts: List[Tuple[int, str]] = []
    sess = requests.Session()
    for p in candidates:
        url = f"{scheme}://{host}:{p}{base_path}/config"
        try:
            r = sess.get(url, headers={"Origin": origin, "Accept": "application/json"}, timeout=3)
            if r.status_code == 200:
                attempts.append((p, "200 OK"))
                return p, attempts
            attempts.append((p, f"HTTP {r.status_code}"))
        except requests.RequestException as e:
            attempts.append((p, f"{type(e).__name__}: {e}"))
    return None, attempts

# ========================
# Summary
# ========================

def print_summary(results: List[Result]):
    print("\n" + "#" * 80)
    print("Summary")
    print("#" * 80)
    width = max(len(r.name) for r in results) if results else 10
    for r in results:
        status = "OK" if r.ok else "FAIL"
        code = r.status if r.status is not None else "-"
        notes = f" ({r.notes})" if r.notes else ""
        print(f"{r.name.ljust(width)}  {status:4}  {str(code):>3}{notes}")

# ========================
# Main
# ========================

def main() -> int:
    parser = argparse.ArgumentParser(description="RN-like CORS API tester")
    parser.add_argument("--host", default=SERVER_IP, help="API host/IP")
    parser.add_argument("--port", default=str(PORT), help="API port or 'auto'")
    parser.add_argument("--origin", default=ORIGIN_DEF, help="Origin header to send")
    parser.add_argument("--scheme", default=SCHEME_DEF, choices=["http", "https"], help="http or https")
    parser.add_argument("--base-path", default=BASE_PATH_DEF, help="API base path (default /api)")
    parser.add_argument("--discover", action="store_true", help="Force port discovery via GET {base}/config")
    parser.add_argument("--with-cookies", action="store_true", help="Verify cookie-based auth CORS rules as well")
    parser.add_argument("--timeout", type=float, default=TIMEOUT_DEF, help="Request timeout seconds")
    args = parser.parse_args()

    host = args.host
    origin = args.origin
    scheme = args.scheme
    base_path = args.base_path
    if not base_path.startswith('/'):
        base_path = '/' + base_path
    base_path = base_path.rstrip('/')

    # Port selection
    port_val = args.port
    auto = args.discover or str(port_val).lower() in ("auto", "0", "none")
    if auto:
        print("Auto-discovering port... candidates: 8080, 5000, 8000, 80")
        port, attempts = discover_port(host, base_path, [8080, 5000, 8000, 80], scheme, origin)
        for p, note in attempts:
            print(f"  Tried {host}:{p} -> {note}")
        if port is None:
            print("Could not discover a working port via /config. Start the server or expose the correct port.")
            return 3
        print(f"Using discovered port: {port}")
    else:
        try:
            port = int(port_val)
        except ValueError:
            print(f"Invalid --port value: {port_val}")
            return 2

    base = f"{scheme}://{host}:{port}{base_path}"
    sess = requests.Session()
    sess.verify = True  # change to False if testing self-signed HTTPS (not recommended)

    results: List[Result] = []
    hard_cors_fail = False

    # Public config
    log_header("GET /config (public)")
    r = call(sess, origin, "GET", f"{base}/config", timeout=args.timeout)
    results.append(Result("config", r.ok, r.status_code))
    ok, note = cors_ok_for_simple(r, origin, want_credentials=False)
    if not ok:
        hard_cors_fail = True
        results[-1].notes = f"CORS: {note}"

    # Register
    log_header("CORS preflight: POST /register")
    r = preflight(sess, origin, f"{base}/register", "POST", req_headers="content-type", timeout=args.timeout)
    results.append(Result("preflight_register", r.status_code in (200, 204), r.status_code))
    ok, note = cors_ok_for_preflight(r, origin, "POST", "content-type", want_credentials=False)
    if not ok:
        hard_cors_fail = True
        results[-1].notes = f"CORS: {note}"

    email = TEST_EMAIL
    reg_body = {"email": email, "password": TEST_PASSWORD}
    log_header("POST /register")
    r = call(sess, origin, "POST", f"{base}/register", body=reg_body, timeout=args.timeout)
    if r.status_code in (400, 409) and r.headers.get("Content-Type", "").lower().startswith("application/json"):
        try:
            err = r.json().get("error", "")
            if "already" in err.lower():
                email = f"{uuid.uuid4().hex[:10]}@example.com"
                print(f"Note: email already registered, retrying with {email}")
                r = call(sess, origin, "POST", f"{base}/register", body={"email": email, "password": TEST_PASSWORD}, timeout=args.timeout)
        except Exception:
            pass
    results.append(Result("register", r.status_code in (201, 200), r.status_code))

    # Login
    log_header("CORS preflight: POST /login")
    r = preflight(sess, origin, f"{base}/login", "POST", req_headers="content-type", timeout=args.timeout)
    results.append(Result("preflight_login", r.status_code in (200, 204), r.status_code))
    ok, note = cors_ok_for_preflight(r, origin, "POST", "content-type", want_credentials=args.with_cookies)
    if not ok:
        hard_cors_fail = True
        results[-1].notes = f"CORS: {note}"

    log_header("POST /login")
    r = call(sess, origin, "POST", f"{base}/login", body={"email": email, "password": TEST_PASSWORD}, timeout=args.timeout)
    token = None
    try:
        token = r.json().get("token") if r.ok else None
    except Exception:
        token = None
    cookie_set = "set-cookie" in r.headers
    results.append(Result("login", bool(token) or cookie_set, r.status_code, notes=("token" if token else ("cookie" if cookie_set else "no auth artifact"))))
    if not token and not cookie_set:
        print("Fatal: could not obtain token or cookie. Aborting.")
        print_summary(results)
        return 1

    # Authenticated calls (token header path)
    if token:
        log_header("GET /user with Authorization header")
        r = call(sess, origin, "GET", f"{base}/user", token=token, timeout=args.timeout)
        results.append(Result("user_header", r.ok, r.status_code))
        ok, note = cors_ok_for_simple(r, origin, want_credentials=False)
        if not ok:
            hard_cors_fail = True
            results[-1].notes = f"CORS: {note}"

    # Actuar flow (save text, public JSON, static HTML)
    log_header("CORS preflight: POST /actuar")
    r = preflight(sess, origin, f"{base}/actuar", "POST", req_headers="content-type, authorization", timeout=args.timeout)
    results.append(Result("preflight_actuar_post", r.status_code in (200, 204), r.status_code))
    ok, note = cors_ok_for_preflight(r, origin, "POST", "content-type, authorization", want_credentials=False)
    if not ok:
        hard_cors_fail = True
        results[-1].notes = f"CORS: {note}"

    # POST /actuar with first text
    text1 = f"Hello RN tester {uuid.uuid4().hex[:8]}"
    log_header("POST /actuar (create/update)")
    r = call(sess, origin, "POST", f"{base}/actuar", token=token, body={"text": text1}, timeout=args.timeout)
    results.append(Result("actuar_post", r.ok, r.status_code))
    static_url = None
    try:
        data = r.json()
        static_rel = (data.get("static") or {}).get("url")
        if isinstance(static_rel, str) and static_rel.startswith("/static/"):
            static_url = f"{scheme}://{host}:{port}{static_rel}"
    except Exception:
        static_url = None

    # GET static HTML and check content
    if static_url:
        log_header("GET static actuar HTML")
        print_req("GET", static_url, {"Origin": origin, "Accept": "text/html"})
        sr = sess.get(static_url, headers={"Origin": origin, "Accept": "text/html"}, timeout=args.timeout)
        print_res(sr)
        ok_html = sr.status_code == 200 and text1 in sr.text
        results.append(Result("actuar_static", ok_html, sr.status_code))
    else:
        results.append(Result("actuar_static", False, None, notes="no static url"))

    # Public JSON by username (email)
    log_header("GET /actuar/<username> (public JSON)")
    pr = call(sess, origin, "GET", f"{base}/actuar/{email}", timeout=args.timeout)
    p_ok = False
    try:
        pj = pr.json()
        p_ok = pr.status_code == 200 and pj.get("username") == email and pj.get("text") == text1
    except Exception:
        p_ok = False
    results.append(Result("actuar_public", p_ok, pr.status_code))

    # Update text and verify static updates
    text2 = f"Updated RN {uuid.uuid4().hex[:6]}"
    log_header("POST /actuar (update)")
    r2 = call(sess, origin, "POST", f"{base}/actuar", token=token, body={"text": text2}, timeout=args.timeout)
    results.append(Result("actuar_update", r2.ok, r2.status_code))
    if static_url:
        log_header("GET static actuar HTML (updated)")
        sr2 = sess.get(static_url, headers={"Origin": origin, "Accept": "text/html"}, timeout=args.timeout)
        print_res(sr2)
        ok_html2 = sr2.status_code == 200 and (text2 in sr2.text) and (text1 not in sr2.text)
        results.append(Result("actuar_static_updated", ok_html2, sr2.status_code))
    else:
        results.append(Result("actuar_static_updated", False, None, notes="no static url"))

        log_header("GET /user with ?token=")
        r = call(sess, origin, "GET", f"{base}/user?token={token}", timeout=args.timeout)
        results.append(Result("user_query", r.ok, r.status_code))
        ok, note = cors_ok_for_simple(r, origin, want_credentials=False)
        if not ok:
            hard_cors_fail = True
            results[-1].notes = f"CORS: {note}"

    # Cookie-based call (if requested and cookie present)
    if args.with_cookies and cookie_set:
        log_header("GET /user via session cookie (simulated with requests session)")
        r = call(sess, origin, "GET", f"{base}/user", timeout=args.timeout)
        results.append(Result("user_cookie", r.ok, r.status_code))
        ok, note = cors_ok_for_simple(r, origin, want_credentials=True)
        if not ok:
            hard_cors_fail = True
            results[-1].notes = f"CORS: {note}"

    # Credits
    log_header("GET /user/credits")
    r = call(sess, origin, "GET", f"{base}/user/credits", token=token, timeout=args.timeout)
    results.append(Result("credits_get", r.ok, r.status_code))

    log_header("CORS preflight: POST /user/credits")
    r = preflight(sess, origin, f"{base}/user/credits", "POST", req_headers="content-type, authorization", timeout=args.timeout)
    results.append(Result("preflight_credits_post", r.status_code in (200, 204), r.status_code))
    ok, note = cors_ok_for_preflight(r, origin, "POST", "content-type, authorization", want_credentials=False)
    if not ok:
        hard_cors_fail = True
        results[-1].notes = f"CORS: {note}"

    log_header("POST /user/credits +10")
    r = call(sess, origin, "POST", f"{base}/user/credits", token=token, body={"amount": 10}, timeout=args.timeout)
    results.append(Result("credits_add", r.ok, r.status_code))

    # Decks flow
    log_header("GET /decks (list)")
    r = call(sess, origin, "GET", f"{base}/decks", token=token, timeout=args.timeout)
    results.append(Result("decks_list_initial", r.ok, r.status_code))

    log_header("CORS preflight: POST /decks")
    r = preflight(sess, origin, f"{base}/decks", "POST", req_headers="content-type, authorization", timeout=args.timeout)
    results.append(Result("preflight_decks_post", r.status_code in (200, 204), r.status_code))
    ok, note = cors_ok_for_preflight(r, origin, "POST", "content-type, authorization", want_credentials=False)
    if not ok:
        hard_cors_fail = True
        results[-1].notes = f"CORS: {note}"

    log_header("POST /decks (create)")
    deck_payload = {"name": "Test Deck", "description": "Deck created by RN tester", "nodes": ["Iniciar", "Conversación"]}
    r = call(sess, origin, "POST", f"{base}/decks", token=token, body=deck_payload, timeout=args.timeout)
    results.append(Result("deck_create", r.status_code == 201, r.status_code))
    try:
        deck = r.json()
        deck_id = deck.get("id")
    except Exception:
        deck_id = None

    if deck_id:
        log_header("GET /decks/<id>")
        r = call(sess, origin, "GET", f"{base}/decks/{deck_id}", token=token, timeout=args.timeout)
        results.append(Result("deck_get", r.ok, r.status_code))

        log_header("CORS preflight: PUT /decks/<id>")
        r = preflight(sess, origin, f"{base}/decks/{deck_id}", "PUT", req_headers="content-type, authorization", timeout=args.timeout)
        results.append(Result("preflight_decks_put", r.status_code in (200, 204), r.status_code))
        ok, note = cors_ok_for_preflight(r, origin, "PUT", "content-type, authorization", want_credentials=False)
        if not ok:
            hard_cors_fail = True
            results[-1].notes = f"CORS: {note}"

        log_header("PUT /decks/<id> (update nodes)")
        r = call(sess, origin, "PUT", f"{base}/decks/{deck_id}", token=token, body={"nodes": ["Iniciar"], "description": "Updated by RN tester"}, timeout=args.timeout)
        results.append(Result("deck_update", r.ok, r.status_code))

    # Routines flow
    log_header("GET /routines (list)")
    r = call(sess, origin, "GET", f"{base}/routines", token=token, timeout=args.timeout)
    results.append(Result("routines_list_initial", r.ok, r.status_code))

    routine_id = None
    if deck_id:
        log_header("CORS preflight: POST /routines")
        r = preflight(sess, origin, f"{base}/routines", "POST", req_headers="content-type, authorization", timeout=args.timeout)
        results.append(Result("preflight_routines_post", r.status_code in (200, 204), r.status_code))
        ok, note = cors_ok_for_preflight(r, origin, "POST", "content-type, authorization", want_credentials=False)
        if not ok:
            hard_cors_fail = True
            results[-1].notes = f"CORS: {note}"

        log_header("POST /routines (create)")
        r = call(sess, origin, "POST", f"{base}/routines", token=token, body={"name": "Test Routine", "nodes": ["Iniciar"], "deck_id": int(deck_id) if str(deck_id).isdigit() else deck_id, "deck_order": ["A", "B", "C"]}, timeout=args.timeout)
        results.append(Result("routine_create", r.status_code == 201, r.status_code))
        try:
            routine_id = r.json().get("id")
        except Exception:
            routine_id = None

    if routine_id:
        log_header("GET /routines/<id>")
        r = call(sess, origin, "GET", f"{base}/routines/{routine_id}", token=token, timeout=args.timeout)
        results.append(Result("routine_get", r.ok, r.status_code))

        log_header("CORS preflight: PUT /routines/<id>")
        r = preflight(sess, origin, f"{base}/routines/{routine_id}", "PUT", req_headers="content-type, authorization", timeout=args.timeout)
        results.append(Result("preflight_routines_put", r.status_code in (200, 204), r.status_code))
        ok, note = cors_ok_for_preflight(r, origin, "PUT", "content-type, authorization", want_credentials=False)
        if not ok:
            hard_cors_fail = True
            results[-1].notes = f"CORS: {note}"

        log_header("PUT /routines/<id> (update)")
        r = call(sess, origin, "PUT", f"{base}/routines/{routine_id}", token=token, body={"nodes": ["Iniciar", "Conversación"], "deck_order": None}, timeout=args.timeout)
        results.append(Result("routine_update", r.ok, r.status_code))

        log_header("CORS preflight: DELETE /routines/<id>")
        r = preflight(sess, origin, f"{base}/routines/{routine_id}", "DELETE", req_headers="authorization", timeout=args.timeout)
        results.append(Result("preflight_routines_delete", r.status_code in (200, 204), r.status_code))
        ok, note = cors_ok_for_preflight(r, origin, "DELETE", "authorization", want_credentials=False)
        if not ok:
            hard_cors_fail = True
            results[-1].notes = f"CORS: {note}"

        log_header("DELETE /routines/<id>")
        r = call(sess, origin, "DELETE", f"{base}/routines/{routine_id}", token=token, timeout=args.timeout)
        results.append(Result("routine_delete", r.ok, r.status_code))

    # Deck cleanup
    if 'deck_id' in locals() and deck_id:
        log_header("CORS preflight: DELETE /decks/<id>")
        r = preflight(sess, origin, f"{base}/decks/{deck_id}", "DELETE", req_headers="authorization", timeout=args.timeout)
        results.append(Result("preflight_decks_delete", r.status_code in (200, 204), r.status_code))
        ok, note = cors_ok_for_preflight(r, origin, "DELETE", "authorization", want_credentials=False)
        if not ok:
            hard_cors_fail = True
            results[-1].notes = f"CORS: {note}"

        log_header("DELETE /decks/<id>")
        r = call(sess, origin, "DELETE", f"{base}/decks/{deck_id}", token=token, timeout=args.timeout)
        results.append(Result("deck_delete", r.ok, r.status_code))

        log_header("GET /decks/<id> (expect 404)")
        r = call(sess, origin, "GET", f"{base}/decks/{deck_id}", token=token, timeout=args.timeout)
        results.append(Result("deck_get_after_delete", r.status_code == 404, r.status_code))

    # Logout
    log_header("CORS preflight: POST /logout")
    r = preflight(sess, origin, f"{base}/logout", "POST", req_headers="authorization", timeout=args.timeout)
    results.append(Result("preflight_logout", r.status_code in (200, 204), r.status_code))
    ok, note = cors_ok_for_preflight(r, origin, "POST", "authorization", want_credentials=False)
    if not ok:
        hard_cors_fail = True
        results[-1].notes = f"CORS: {note}"

    log_header("POST /logout")
    r = call(sess, origin, "POST", f"{base}/logout", token=token, timeout=args.timeout)
    results.append(Result("logout", r.ok, r.status_code))

    log_header("GET /user after logout (expect 401)")
    r = call(sess, origin, "GET", f"{base}/user", token=token, timeout=args.timeout)
    results.append(Result("user_after_logout", r.status_code == 401, r.status_code))

    print_summary(results)

    # Exit code logic
    failures = [x for x in results if not x.ok]
    if hard_cors_fail:
        return 4
    return 0 if not failures else 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
        sys.exit(130)
