#!/usr/bin/env python3
"""
RN-like CORS API Tester

This script simulates a React Native client calling the API endpoints with
appropriate CORS headers and detailed output to assess end-to-end behavior.

Usage:
  python scripts/rn_cors_api_tester.py

Before running, edit SERVER_IP below to match your server.
"""

import argparse
import json
import os
import sys
import time
import uuid
from dataclasses import dataclass
from typing import Dict, Optional, Tuple, List

import requests


# ========================
# Config — EDIT AS NEEDED
# ========================

# Replace with your server IP or hostname (can be overridden by --host or env API_HOST)
SERVER_IP = "127.0.0.1"  # e.g. "161.153.217.110"
# Default port (can be overridden by --port or env API_PORT). If set to 0, will auto-discover.
PORT = 8080

# Simulated RN origin (Expo dev server, mobile app webview, etc.)
ORIGIN = "http://example-react-native.dev"

# Test credentials (email is randomized if already taken)
TEST_EMAIL = "rn.tester@example.com"
TEST_PASSWORD = "rn_test_pw"


@dataclass
class Result:
    name: str
    ok: bool
    status: Optional[int] = None
    notes: str = ""


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
        # mask token for readability
        tok = hmask["Authorization"]
        hmask["Authorization"] = tok[:16] + "…" if len(tok) > 16 else tok
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


def preflight(sess: requests.Session, url: str, method: str, req_headers: Optional[str] = None) -> requests.Response:
    headers = {
        "Origin": ORIGIN,
        "Access-Control-Request-Method": method,
    }
    if req_headers:
        headers["Access-Control-Request-Headers"] = req_headers
    print_req("OPTIONS", url, headers)
    r = sess.options(url, headers=headers, timeout=15)
    print_res(r)
    return r


def call(sess: requests.Session, method: str, url: str, token: Optional[str] = None, body: Optional[dict] = None) -> requests.Response:
    headers = {
        "Origin": ORIGIN,
        "Accept": "application/json",
    }
    if body is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = token
    print_req(method, url, headers, body)
    func = getattr(sess, method.lower())
    if body is not None:
        r = func(url, headers=headers, json=body, timeout=30)
    else:
        r = func(url, headers=headers, timeout=30)
    print_res(r)
    return r


def discover_port(host: str, candidates: List[int]) -> Tuple[Optional[int], List[Tuple[int, str]]]:
    """Try candidate ports by GET /api/config. Return (port, attempts log)."""
    attempts = []
    sess = requests.Session()
    for p in candidates:
        url = f"http://{host}:{p}/api/config"
        try:
            r = sess.get(url, headers={"Origin": ORIGIN, "Accept": "application/json"}, timeout=3)
            if r.status_code == 200:
                attempts.append((p, f"200 OK"))
                return p, attempts
            attempts.append((p, f"HTTP {r.status_code}"))
        except requests.RequestException as e:
            attempts.append((p, f"{type(e).__name__}: {e}"))
    return None, attempts


def main() -> int:
    parser = argparse.ArgumentParser(description="RN-like CORS API tester")
    parser.add_argument("--host", default=os.getenv("API_HOST", SERVER_IP), help="API host/IP (default env API_HOST or script default)")
    parser.add_argument("--port", default=os.getenv("API_PORT", str(PORT)), help="API port or 'auto' to discover (default env API_PORT or script default)")
    parser.add_argument("--origin", default=os.getenv("API_ORIGIN", ORIGIN), help="Origin header to send")
    parser.add_argument("--discover", action="store_true", help="Force port discovery before running")
    args = parser.parse_args()

    host = args.host
    global ORIGIN
    ORIGIN = args.origin

    port_val = args.port
    auto = args.discover or str(port_val).lower() in ("auto", "0", "none")
    port: Optional[int]
    if auto:
        print("Auto-discovering port... candidates: 8080, 5000, 8000, 80")
        port, attempts = discover_port(host, [8080, 5000, 8000, 80])
        for p, note in attempts:
            print(f"  Tried {host}:{p} -> {note}")
        if port is None:
            print("Could not discover a working port via /api/config. You may need to start the server or expose the correct port.")
            return 3
        print(f"Using discovered port: {port}")
    else:
        try:
            port = int(port_val)
        except ValueError:
            print(f"Invalid --port value: {port_val}")
            return 2

    base = f"http://{host}:{port}/api"
    sess = requests.Session()
    results = []

    # Public config
    log_header("GET /api/config (public)")
    r = call(sess, "GET", f"{base}/config")
    results.append(Result("config", r.ok, r.status_code))

    # Register new user (handle already registered)
    log_header("CORS preflight: POST /api/register")
    preflight(sess, f"{base}/register", "POST", req_headers="content-type")

    email = TEST_EMAIL
    reg_body = {"email": email, "password": TEST_PASSWORD}
    log_header("POST /api/register")
    r = call(sess, "POST", f"{base}/register", body=reg_body)
    if r.status_code == 400 and r.headers.get("Content-Type", "").startswith("application/json"):
        try:
            if r.json().get("error") == "email already registered":
                # use a random email to proceed
                email = f"{uuid.uuid4().hex[:10]}@example.com"
                print(f"Note: email already registered, retrying with {email}")
                r = call(sess, "POST", f"{base}/register", body={"email": email, "password": TEST_PASSWORD})
        except Exception:
            pass
    results.append(Result("register", r.status_code in (201, 200), r.status_code))

    # Login
    log_header("CORS preflight: POST /api/login")
    preflight(sess, f"{base}/login", "POST", req_headers="content-type")

    log_header("POST /api/login")
    r = call(sess, "POST", f"{base}/login", body={"email": email, "password": TEST_PASSWORD})
    token = None
    try:
        token = r.json().get("token") if r.ok else None
    except Exception:
        token = None
    results.append(Result("login", bool(token), r.status_code, notes=("token acquired" if token else "no token")))
    if not token:
        print("Fatal: could not obtain token. Aborting.")
        print_summary(results)
        return 1

    # GET /user (header token)
    log_header("GET /api/user with Authorization header")
    r = call(sess, "GET", f"{base}/user", token=token)
    results.append(Result("user_header", r.ok, r.status_code))

    # GET /user (query token)
    log_header("GET /api/user with ?token=")
    r = call(sess, "GET", f"{base}/user?token={token}")
    results.append(Result("user_query", r.ok, r.status_code))

    # Credits
    log_header("GET /api/user/credits")
    r = call(sess, "GET", f"{base}/user/credits", token=token)
    results.append(Result("credits_get", r.ok, r.status_code))

    log_header("CORS preflight: POST /api/user/credits")
    preflight(sess, f"{base}/user/credits", "POST", req_headers="content-type, authorization")

    log_header("POST /api/user/credits +10")
    r = call(sess, "POST", f"{base}/user/credits", token=token, body={"amount": 10})
    results.append(Result("credits_add", r.ok, r.status_code))

    # Decks flow
    log_header("GET /api/decks (list)")
    r = call(sess, "GET", f"{base}/decks", token=token)
    results.append(Result("decks_list_initial", r.ok, r.status_code))

    log_header("CORS preflight: POST /api/decks")
    preflight(sess, f"{base}/decks", "POST", req_headers="content-type, authorization")

    log_header("POST /api/decks (create)")
    deck_payload = {
        "name": "Test Deck",
        "description": "Deck created by RN tester",
        "nodes": ["Iniciar", "Conversación"],
    }
    r = call(sess, "POST", f"{base}/decks", token=token, body=deck_payload)
    results.append(Result("deck_create", r.status_code == 201, r.status_code))
    try:
        deck = r.json()
        deck_id = deck.get("id")
    except Exception:
        deck_id = None

    if not deck_id:
        print("Fatal: deck not created; skipping dependent tests.")
    else:
        log_header("GET /api/decks/<id>")
        r = call(sess, "GET", f"{base}/decks/{deck_id}", token=token)
        results.append(Result("deck_get", r.ok, r.status_code))

        log_header("CORS preflight: PUT /api/decks/<id>")
        preflight(sess, f"{base}/decks/{deck_id}", "PUT", req_headers="content-type, authorization")

        log_header("PUT /api/decks/<id> (update nodes)")
        r = call(
            sess,
            "PUT",
            f"{base}/decks/{deck_id}",
            token=token,
            body={"nodes": ["Iniciar"], "description": "Updated by RN tester"},
        )
        results.append(Result("deck_update", r.ok, r.status_code))

    # Routines flow (depends on deck)
    log_header("GET /api/routines (list)")
    r = call(sess, "GET", f"{base}/routines", token=token)
    results.append(Result("routines_list_initial", r.ok, r.status_code))

    routine_id = None
    if deck_id:
        log_header("CORS preflight: POST /api/routines")
        preflight(sess, f"{base}/routines", "POST", req_headers="content-type, authorization")

        log_header("POST /api/routines (create)")
        r = call(
            sess,
            "POST",
            f"{base}/routines",
            token=token,
            body={
                "name": "Test Routine",
                "nodes": ["Iniciar"],
                "deck_id": int(deck_id) if str(deck_id).isdigit() else deck_id,
                "deck_order": ["A", "B", "C"],
            },
        )
        results.append(Result("routine_create", r.status_code == 201, r.status_code))
        try:
            routine_id = r.json().get("id")
        except Exception:
            routine_id = None

    if routine_id:
        log_header("GET /api/routines/<id>")
        r = call(sess, "GET", f"{base}/routines/{routine_id}", token=token)
        results.append(Result("routine_get", r.ok, r.status_code))

        log_header("CORS preflight: PUT /api/routines/<id>")
        preflight(sess, f"{base}/routines/{routine_id}", "PUT", req_headers="content-type, authorization")

        log_header("PUT /api/routines/<id> (update)")
        r = call(
            sess,
            "PUT",
            f"{base}/routines/{routine_id}",
            token=token,
            body={"nodes": ["Iniciar", "Conversación"], "deck_order": None},
        )
        results.append(Result("routine_update", r.ok, r.status_code))

        log_header("CORS preflight: DELETE /api/routines/<id>")
        preflight(sess, f"{base}/routines/{routine_id}", "DELETE", req_headers="authorization")

        log_header("DELETE /api/routines/<id>")
        r = call(sess, "DELETE", f"{base}/routines/{routine_id}", token=token)
        results.append(Result("routine_delete", r.ok, r.status_code))

    # Clean up deck after routine
    if deck_id:
        log_header("CORS preflight: DELETE /api/decks/<id>")
        preflight(sess, f"{base}/decks/{deck_id}", "DELETE", req_headers="authorization")

        log_header("DELETE /api/decks/<id>")
        r = call(sess, "DELETE", f"{base}/decks/{deck_id}", token=token)
        results.append(Result("deck_delete", r.ok, r.status_code))

        log_header("GET /api/decks/<id> (expect 404)")
        r = call(sess, "GET", f"{base}/decks/{deck_id}", token=token)
        results.append(Result("deck_get_after_delete", r.status_code == 404, r.status_code))

    # Logout
    log_header("CORS preflight: POST /api/logout")
    preflight(sess, f"{base}/logout", "POST", req_headers="authorization")

    log_header("POST /api/logout")
    r = call(sess, "POST", f"{base}/logout", token=token)
    results.append(Result("logout", r.ok, r.status_code))

    log_header("GET /api/user after logout (expect 401)")
    r = call(sess, "GET", f"{base}/user", token=token)
    results.append(Result("user_after_logout", r.status_code == 401, r.status_code))

    print_summary(results)
    failures = [x for x in results if not x.ok]
    return 0 if not failures else 2


def print_summary(results):
    print("\n" + "#" * 80)
    print("Summary")
    print("#" * 80)
    width = max(len(r.name) for r in results) if results else 10
    for r in results:
        status = "OK" if r.ok else "FAIL"
        code = r.status if r.status is not None else "-"
        notes = f" ({r.notes})" if r.notes else ""
        print(f"{r.name.ljust(width)}  {status:4}  {str(code):>3}{notes}")


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
        sys.exit(130)
