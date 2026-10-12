#!/usr/bin/env python3
"""Portainer Analytics: persistent dashboards and scoped network viewers."""

from __future__ import annotations

import argparse
import collections
import datetime as dt
import hashlib
import hmac
import ipaddress
import json
import logging
import os
import re
import secrets
import signal
import socket
import threading
import time
from http.cookies import SimpleCookie
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

import engine
from dashboard_metrics import (
    metric_catalog,
    metric_info,
    metric_values,
    resources,
    validate_dashboard,
)
from engine import decode_logs, redact, safe_inspect
from persistence import Conflict, Store

ROOT = Path(__file__).resolve().parent
WEB = ROOT / "web"
LOG = logging.getLogger("portainer-analytics")


def chart_points(points, max_gap_ms, limit=360):
    """Reduce only after aggregation, keeping outages explicit in the chart."""
    expanded = []
    for point in points:
        if expanded and point["t"] - expanded[-1]["t"] > max_gap_ms:
            expanded.append({"t": expanded[-1]["t"] + max_gap_ms, "v": None})
        expanded.append(point)
    stride = max(1, (len(expanded) + limit - 1) // limit)
    result = []
    for start in range(0, len(expanded), stride):
        bucket = expanded[start : start + stride]
        # An outage must never disappear when a long window is reduced.
        result.append(next((p for p in bucket if p["v"] is None), bucket[-1]))
    if expanded and result[-1]["t"] != expanded[-1]["t"]:
        result.append(expanded[-1])
    return result


def source_id(url):
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if ":" in host:
        host = f"[{host}]"
    port = parsed.port
    if port and not (
        parsed.scheme.lower() == "https"
        and port == 443
        or parsed.scheme.lower() == "http"
        and port == 80
    ):
        host += f":{port}"
    canonical = parsed.scheme.lower() + "://" + host + parsed.path.rstrip("/")
    return hashlib.sha256(canonical.encode()).hexdigest()[:24]


def validate_connection(raw, previous):
    url = str(raw.get("url", "")).strip().rstrip("/")
    parsed = urlparse(url)
    if (
        parsed.scheme not in ("https", "http")
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(
            "Enter a complete HTTP or HTTPS Portainer URL without credentials, query or fragment."
        )
    try:
        parsed.port
    except ValueError:
        raise ValueError("The Portainer port is invalid.") from None
    if len(url) > 2048 or any(c.isspace() for c in url):
        raise ValueError("The Portainer URL is invalid.")
    token = raw.get("token", "")
    if not isinstance(token, str) or len(token) > 8192 or "\r" in token or "\n" in token:
        raise ValueError("The API token is invalid.")
    token = token.strip()
    if not token and url == previous.get("url"):
        token = previous.get("token", "")
    if not token:
        raise ValueError(
            "Enter an API token for this server. Existing tokens are never forwarded to a different URL."
        )
    verify = raw.get("verify", True)
    timeout = raw.get("timeout", 8)
    if type(verify) is not bool or type(timeout) is not int or not 2 <= timeout <= 30:
        raise ValueError("Use a valid TLS option and a timeout between 2 and 30 seconds.")
    return {"url": url, "token": token, "verify": verify, "timeout": timeout}


def password_hash(password):
    salt = secrets.token_hex(16)
    digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()
    return salt + ":" + digest


def password_matches(password, stored):
    try:
        salt, expected = stored.split(":", 1)
        actual = hashlib.scrypt(
            password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1
        ).hex()
        return hmac.compare_digest(actual, expected)
    except ValueError, TypeError:
        return False


class Manager:
    def __init__(self, store, interval=5):
        self.store = store
        self.interval = interval
        self.lock = threading.RLock()
        self.change_lock = threading.Lock()
        self.stop = threading.Event()
        self.recent = {}
        self.retiring = []
        # Every installation starts clean and requires administrator sign-in.
        self.standalone = True
        saved = store.setting("connection")
        self.cfg = saved if saved is not None else engine.config(clean=True)
        self.source = source_id(self.cfg["url"])
        self.collector = engine.Collector(engine.Client(self.cfg), interval)
        self.collector.start()
        self.generation = secrets.token_hex(8)
        self.worker = threading.Thread(target=self.observe, daemon=True, name="dashboard-history")
        self.worker.start()

    def snapshot(self):
        with self.lock:
            collector, source, generation = self.collector, self.source, self.generation
            value = collector.snapshot()
            value.update(source_id=source, generation=generation)
            return value

    def connection_public(self):
        with self.lock:
            return {
                "url": self.cfg["url"],
                "has_token": bool(self.cfg["token"]),
                "verify": self.cfg["verify"],
                "timeout": self.cfg["timeout"],
                "source_id": self.source,
                "admin_password_set": bool(self.store.setting("admin_password")),
                "public_base_url": os.environ.get("CONSOLE_PUBLIC_URL", "").rstrip("/"),
                "saved": self.store.setting("connection") is not None,
            }

    def test_connection(self, raw):
        with self.lock:
            cfg = validate_connection(raw, self.cfg)
        endpoints = engine.Client(cfg).get("/api/endpoints")
        if isinstance(endpoints, dict):
            endpoints = endpoints.get("value")
        if not isinstance(endpoints, list):
            raise ValueError("This server did not return a Portainer environment list.")
        return cfg, len(endpoints)

    def change_connection(self, raw, initial_password=None):
        with self.change_lock:
            if self.stop.is_set():
                raise ValueError("The server is shutting down.")
            if initial_password is not None and (
                not self.standalone or not self.store.is_pristine()
            ):
                raise Conflict("This workspace has already been initialized. Sign in to continue.")
            cfg, count = self.test_connection(raw)
            if self.stop.is_set():
                raise ValueError("The server is shutting down.")
            new = engine.Collector(engine.Client(cfg), self.interval)
            # Commit first: a failed disk write must never appear to have saved.
            if initial_password is not None:
                self.store.initialize(cfg, password_hash(initial_password))
            else:
                self.store.set_setting("connection", cfg)
            with self.lock:
                old = self.collector
                self.cfg, self.source = cfg, source_id(cfg["url"])
                self.collector = new
                self.generation = secrets.token_hex(8)
                self.recent.clear()
                new.start()
            old.stop.set()
            retiring = threading.Thread(target=old.close, daemon=True, name="retire-collector")
            retiring.start()
            self.retiring = [t for t in self.retiring if t.is_alive()] + [retiring]
        return {
            "ok": True,
            "environments": count,
            "connection": self.connection_public(),
            "generation": self.generation,
        }

    def observe(self):
        previous = None
        cleanup = 0
        while not self.stop.wait(1):
            try:
                snap = self.snapshot()
                identity = (snap["generation"], snap["sequence"], snap["status"])
                if identity == previous or not snap["sequence"]:
                    continue
                previous = identity
                wanted = {}
                for dashboard in self.store.dashboards():
                    if dashboard["source_id"] == snap["source_id"]:
                        for w in dashboard["widgets"]:
                            for name in w["sources"]:
                                wanted.setdefault(
                                    (dashboard["environment_id"], w["kind"], name), set()
                                ).add(w["metric"])
                rows = []
                now = time.time()
                for env in snap["environments"]:
                    stamp = dt.datetime.fromisoformat(
                        env.get("updated_at") or snap["updated_at"]
                    ).timestamp()
                    if env.get("status") == "offline" or snap["status"] == "offline":
                        stamp = now
                    for kind, name in resources(env):
                        values = (
                            metric_values(env, kind, name) if snap["status"] != "offline" else None
                        )
                        selected = wanted.get((env["id"], kind, name), set())
                        recent_values = {
                            k: v
                            for k, v in (values or {}).items()
                            if not k.startswith("raw.") or k in selected
                        }
                        key = (snap["source_id"], env["id"], kind, name)
                        with self.lock:
                            if self.generation != snap["generation"]:
                                break
                            queue = self.recent.setdefault(key, collections.deque(maxlen=180))
                            if not queue or queue[-1][0] != stamp:
                                queue.append((stamp, recent_values))
                        if (env["id"], kind, name) in wanted:
                            rows.append(
                                (
                                    *key,
                                    stamp,
                                    json.dumps(
                                        {k: (values or {}).get(k) for k in selected},
                                        allow_nan=False,
                                    ),
                                )
                            )
                self.store.record(rows)
                if now - cleanup > 60:
                    self.store.prune(now - 86400)
                    cleanup = now
            except Exception as exc:
                LOG.error("History update failed (%s)", type(exc).__name__)

    def dashboard_data(self, dashboard):
        snap = self.snapshot()
        same_source = snap["source_id"] == dashboard["source_id"]
        env = (
            next((e for e in snap["environments"] if e["id"] == dashboard["environment_id"]), None)
            if same_source
            else None
        )
        fresh = (
            env
            and env.get("status") not in ("offline", "unsupported")
            and snap["status"] != "offline"
        )
        if fresh and env.get("updated_at"):
            fresh = time.time() - dt.datetime.fromisoformat(env["updated_at"]).timestamp() < max(
                30, self.interval * 4
            )
        result = {
            "id": dashboard.get("id"),
            "name": dashboard["name"],
            "description": dashboard["description"],
            "theme": dashboard["theme"],
            "range_minutes": dashboard["range_minutes"],
            "refresh_seconds": dashboard["refresh_seconds"],
            "environment_name": env.get("name") if env else None,
            "status": "live" if fresh else "unavailable",
            "message": ""
            if fresh
            else "This dashboard belongs to a different Portainer connection."
            if not same_source
            else "The environment is unavailable or its latest sample is stale.",
            "updated_at": env.get("updated_at") if env else None,
            "widgets": [],
        }
        since = time.time() - dashboard["range_minutes"] * 60
        memo = {}
        for widget in dashboard["widgets"]:
            info = metric_info(widget["metric"])
            panel = {
                k: widget[k]
                for k in (
                    "id",
                    "title",
                    "visual",
                    "width",
                    "height",
                    "color",
                    "min",
                    "max",
                    "threshold",
                    "aggregate",
                )
            }
            panel.update(
                metric_label=info["label"], unit=info["unit"], note=info["help"], series=[]
            )
            if widget["kind"] == "network":
                panel["note"] = (
                    "Aggregate of containers attached to this network; traffic includes their other interfaces."
                )
            for name in widget["sources"]:
                key = (dashboard["source_id"], dashboard["environment_id"], widget["kind"], name)
                if key not in memo:
                    history = self.store.history(*key, since, limit=None)
                    with self.lock:
                        recent = list(self.recent.get(key, []))
                    samples = dict(history)
                    samples.update((t, v) for t, v in recent if t >= since)
                    memo[key] = sorted(samples.items())
                values = metric_values(env, widget["kind"], name) if fresh else None
                value = (values or {}).get(widget["metric"])
                points = [
                    {"t": int(t * 1000), "v": metrics.get(widget["metric"])}
                    for t, metrics in memo[key]
                ]
                if fresh and env.get("updated_at"):
                    t = int(dt.datetime.fromisoformat(env["updated_at"]).timestamp() * 1000)
                    if not points or points[-1]["t"] < t:
                        points.append({"t": t, "v": value})
                panel["series"].append(
                    {
                        "name": env.get("name", "Environment") if name == "host" and env else name,
                        "value": value,
                        "points": points,
                    }
                )
            if widget["aggregate"] == "sum" and len(panel["series"]) > 1:
                series = panel["series"]
                times = sorted(set(p["t"] for s in series for p in s["points"]))
                maps = [{p["t"]: p["v"] for p in s["points"]} for s in series]

                def total(vals):
                    return sum(vals) if all(v is not None for v in vals) else None

                panel["series"] = [
                    {
                        "name": "Total",
                        "value": total([s["value"] for s in series]),
                        "points": [{"t": t, "v": total([m.get(t) for m in maps])} for t in times],
                    }
                ]
            for series in panel["series"]:
                series["points"] = chart_points(series["points"], max(30, self.interval * 4) * 1000)
            result["widgets"].append(panel)
        return result

    def close(self):
        self.stop.set()
        self.worker.join(timeout=5)
        with self.change_lock:
            self.collector.close()
            for t in self.retiring:
                t.join()


class Handler(engine.Handler):
    def log_message(self, fmt, *args):
        # Capability tokens and credentials never belong in access logs.
        if len(args) > 1 and str(args[1]) not in ("200", "201", "204", "304"):
            LOG.info("HTTP %s", args[1])

    def send(self, payload, status=200, mime="application/json; charset=utf-8"):
        data = (
            json.dumps(payload, ensure_ascii=False, allow_nan=False).encode()
            if "json" in mime
            else payload
        )
        self.send_response(status)
        for key, value in {
            "Content-Type": mime,
            "Content-Length": str(len(data)),
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer",
            "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
        }.items():
            self.send_header(key, value)
        if getattr(self, "new_cookie", None):
            self.send_header("Set-Cookie", self.new_cookie)
        self.end_headers()
        try:
            self.wfile.write(data)
        except BrokenPipeError, ConnectionResetError, ConnectionAbortedError:
            pass

    def guard(self):
        raw = self.headers.get("Host", "")
        try:
            host = urlparse("//" + raw).hostname
        except ValueError:
            host = None
        allowed = host in self.server.allowed_hosts
        try:
            address = ipaddress.ip_address(host or "")
            allowed = allowed or address.is_loopback or address.is_private
        except ValueError:
            pass
        if not allowed:
            self.send(
                {"error": "Host not allowed. Configure CONSOLE_ALLOWED_HOSTS for this hostname."},
                403,
            )
            return False
        path = urlparse(self.path).path
        public_navigation = (
            self.command == "GET"
            and (path == "/" or re.fullmatch(r"/d/[A-Za-z0-9_-]{30,60}", path))
            and self.headers.get("Sec-Fetch-Mode") == "navigate"
        )
        if self.headers.get("Sec-Fetch-Site") == "cross-site" and not public_navigation:
            self.send({"error": "Cross-site requests are not allowed."}, 403)
            return False
        origin = self.headers.get("Origin")
        if origin and urlparse(origin).netloc.lower() != raw.lower() and not public_navigation:
            self.send({"error": "Origin not allowed."}, 403)
            return False
        return True

    def session(self, create_local=False):
        cookies = SimpleCookie()
        try:
            cookies.load(self.headers.get("Cookie", ""))
        except Exception:
            return None
        token = cookies.get("edge_session")
        with self.server.session_lock:
            session = self.server.sessions.get(token.value) if token else None
            if session and session["expires"] > time.time():
                return session
        try:
            local = ipaddress.ip_address(self.client_address[0]).is_loopback
        except ValueError:
            local = False
        # Loopback admin is a desktop convenience. Forwarded headers are never trusted.
        if create_local and local and self.server.local_admin:
            return self.create_session()
        return None

    def setup_required(self):
        return (
            bool(getattr(self.server.manager, "standalone", False))
            and self.server.manager.store.is_pristine()
        )

    def create_session(self, admin=True):
        token = secrets.token_urlsafe(32)
        ttl = 8 * 3600 if admin else 15 * 60
        session = {"csrf": secrets.token_urlsafe(32), "expires": time.time() + ttl, "admin": admin}
        with self.server.session_lock:
            self.server.sessions = {
                k: v for k, v in self.server.sessions.items() if v["expires"] > time.time()
            }
            while len(self.server.sessions) >= self.server.max_sessions:
                oldest = next(
                    (
                        key
                        for key, value in self.server.sessions.items()
                        if not value.get("admin", True)
                    ),
                    next(iter(self.server.sessions)),
                )
                del self.server.sessions[oldest]
            self.server.sessions[token] = session
        self.new_cookie = self.session_cookie(token, ttl)
        return session

    def session_cookie(self, token, ttl):
        secure = "; Secure" if self.server.secure_cookies else ""
        return f"edge_session={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age={ttl}{secure}"

    def admin(self, write=False):
        session = self.session(create_local=not write)
        if not session or not session.get("admin", True):
            self.send({"error": "Administrator sign-in required."}, 401)
            return False
        if write and not hmac.compare_digest(
            self.headers.get("X-Console-CSRF", ""), session["csrf"]
        ):
            self.send({"error": "The session has expired. Refresh and try again."}, 403)
            return False
        return True

    def body(self):
        if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
            raise ValueError("Content-Type must be application/json.")
        if not self.request_body:
            raise ValueError("Request body must be between 1 byte and 256 KiB.")
        data = json.loads(
            self.request_body,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Invalid number.")),
        )
        if not isinstance(data, dict):
            raise ValueError("A JSON object is required.")
        return data

    def do_GET(self):
        if not self.guard():
            return
        path = urlparse(self.path).path
        m = self.server.manager
        store = m.store
        files = {
            "/": "index.html",
            "/index.html": "index.html",
            **{
                "/" + name: name
                for name in (
                    "app.js",
                    "views.js",
                    "controller.js",
                    "styles.css",
                    "theme.js",
                    "alpha.css",
                    "settings.js",
                    "dashboards.js",
                    "charts.js",
                    "shared.js",
                )
            },
        }
        if re.fullmatch(r"/d/[A-Za-z0-9_-]{30,60}", path):
            files[path] = "shared.html"
        if path in files:
            file = WEB / files[path]
            if file.is_file():
                mime = {".js": "text/javascript", ".css": "text/css", ".html": "text/html"}[
                    file.suffix
                ] + "; charset=utf-8"
                return self.send(file.read_bytes(), mime=mime)
        if path == "/api/health":
            return self.send({"status": "ok", "version": "alpha.3"})
        if path == "/api/session":
            setup = self.setup_required()
            session = self.session(create_local=not setup)
            if setup and (not session or session.get("admin", True)):
                session = self.create_session(admin=False)
            return self.send(
                {
                    "admin": bool(session and session.get("admin", True)),
                    "csrf": session["csrf"] if session else None,
                    "login_available": bool(store.setting("admin_password")),
                    "setup_required": setup,
                    "version": "alpha.3",
                }
            )
        shared = re.fullmatch(r"/api/public/dashboards/([A-Za-z0-9_-]{30,60})", path)
        if shared:
            dashboard = store.dashboard(shared[1], shared=True)
            return (
                self.send(m.dashboard_data(dashboard))
                if dashboard
                else self.send({"error": "Dashboard not found or sharing has been disabled."}, 404)
            )
        if not path.startswith("/api/"):
            return self.send({"error": "Not found."}, 404)
        if not self.admin():
            return
        if path == "/api/snapshot":
            return self.send(m.snapshot())
        if path == "/api/settings":
            return self.send(m.connection_public())
        if path == "/api/catalog":
            return self.send(metric_catalog(m.snapshot(), store.dashboards()))
        if path == "/api/dashboards":
            return self.send({"dashboards": store.dashboards()})
        match = re.fullmatch(r"/api/dashboards/([a-f0-9]{32})(/data)?", path)
        if match:
            dashboard = store.dashboard(match[1])
            if not dashboard:
                return self.send({"error": "Dashboard not found."}, 404)
            return self.send(m.dashboard_data(dashboard) if match[2] else dashboard)
        match = re.fullmatch(
            r"/api/environments/(\d+)/(?:containers/([a-f0-9]{12,64})/(inspect|logs)|(events))",
            path,
        )
        if match:
            eid, cid, action = int(match[1]), match[2], match[3] or match[4]
            with m.lock:
                collector, generation = m.collector, m.generation
            env = next((e for e in collector.snapshot()["environments"] if e["id"] == eid), None)
            if not env or (cid and not any(c["id"] == cid for c in env.get("containers", []))):
                return self.send({"error": "Resource not found."}, 404)
            try:
                if action == "inspect":
                    result = safe_inspect(collector.docker(eid, f"containers/{cid}/json"))
                elif action == "logs":
                    result = {
                        "logs": decode_logs(
                            collector.docker(
                                eid,
                                f"containers/{cid}/logs",
                                {
                                    "stdout": "true",
                                    "stderr": "true",
                                    "timestamps": "true",
                                    "tail": "200",
                                },
                                raw=True,
                            )
                        ),
                        "updated_at": engine.utcnow(),
                    }
                else:
                    now = int(time.time())
                    raw = collector.docker(
                        eid, "events", {"since": now - 3600, "until": now}, raw=True
                    )
                    result = {
                        "events": redact(
                            [
                                json.loads(line)
                                for line in raw.decode().splitlines()
                                if line.strip()
                            ][-200:]
                        ),
                        "updated_at": engine.utcnow(),
                    }
                if generation != m.generation:
                    return self.send(
                        {"error": "Connection changed. Retry with the new connection."}, 409
                    )
                return self.send(result)
            except (engine.ApiError, ValueError) as exc:
                return self.send(
                    {
                        "error": str(exc)
                        if isinstance(exc, engine.ApiError)
                        else "Invalid upstream response."
                    },
                    502,
                )
        return self.send({"error": "Not found."}, 404)

    def do_POST(self):
        self.mutate("POST")

    def do_PUT(self):
        self.mutate("PUT")

    def do_DELETE(self):
        self.mutate("DELETE")

    def mutate(self, method):
        # Consume a bounded body before an early authentication/CSRF rejection.
        # Closing a socket with unread body bytes can reset an otherwise valid
        # error response, notably on Windows. Socket timeouts still bound reads.
        try:
            if self.headers.get("Transfer-Encoding"):
                raise ValueError("Chunked request bodies are not supported.")
            length = int(self.headers.get("Content-Length", 0))
            if not 0 <= length <= 262144:
                raise ValueError("Request body must not exceed 256 KiB.")
            self.request_body = self.rfile.read(length)
            if len(self.request_body) != length:
                raise ValueError("Incomplete request body.")
        except (ValueError, TimeoutError) as exc:
            self.send(
                {"error": str(exc) if isinstance(exc, ValueError) else "Request body timed out."},
                400,
            )
            return
        if not self.guard():
            return
        path = urlparse(self.path).path
        m = self.server.manager
        try:
            if path == "/api/setup" and method == "POST":
                if not self.setup_required():
                    return self.send(
                        {"error": "Initial setup is not available. Sign in to continue."}, 409
                    )
                session = self.session()
                if (
                    not session
                    or session.get("admin", True)
                    or not hmac.compare_digest(
                        self.headers.get("X-Console-CSRF", ""), session["csrf"]
                    )
                ):
                    return self.send({"error": "Refresh the setup page and try again."}, 403)
                raw = self.body()
                password = raw.get("password", "")
                if not isinstance(password, str) or not 12 <= len(password) <= 1024:
                    raise ValueError("Use an administrator password of at least 12 characters.")
                result = m.change_connection(raw, initial_password=password)
                with self.server.session_lock:
                    self.server.sessions.clear()
                session = self.create_session()
                return self.send({**result, "admin": True, "csrf": session["csrf"]}, 201)
            if path == "/api/login" and method == "POST":
                raw = self.body()
                password = raw.get("password", "")
                if not isinstance(password, str) or len(password) > 1024:
                    raise ValueError("Invalid password.")
                now = time.time()
                with self.server.session_lock:
                    self.server.attempts = {
                        ip: [t for t in times if now - t < 60]
                        for ip, times in self.server.attempts.items()
                        if any(now - t < 60 for t in times)
                    }
                    attempts = self.server.attempts.setdefault(self.client_address[0], [])
                    if len(attempts) >= 5:
                        return self.send(
                            {"error": "Too many attempts. Try again in a minute."}, 429
                        )
                    attempts.append(now)
                if not password_matches(password, m.store.setting("admin_password", "")):
                    return self.send({"error": "Invalid administrator password."}, 401)
                session = self.create_session()
                return self.send({"admin": True, "csrf": session["csrf"]})
            if not self.admin(write=True):
                return
            raw = self.body()
            if path == "/api/logout" and method == "POST":
                current = self.session()
                with self.server.session_lock:
                    self.server.sessions = {
                        k: v for k, v in self.server.sessions.items() if v is not current
                    }
                self.new_cookie = self.session_cookie("", 0)
                return self.send({"ok": True})
            if path == "/api/admin/password" and method == "POST":
                password = raw.get("password", "")
                if not isinstance(password, str) or not 12 <= len(password) <= 1024:
                    raise ValueError("Use an administrator password of at least 12 characters.")
                m.store.set_setting("admin_password", password_hash(password))
                current = self.session()
                with self.server.session_lock:
                    self.server.sessions = {
                        k: v for k, v in self.server.sessions.items() if v is current
                    }
                return self.send({"ok": True})
            if path == "/api/settings/test" and method == "POST":
                _, count = m.test_connection(raw)
                return self.send({"ok": True, "environments": count})
            if path == "/api/settings" and method == "PUT":
                return self.send(m.change_connection(raw))
            if path == "/api/dashboards/preview" and method == "POST":
                return self.send(m.dashboard_data(validate_dashboard(raw)))
            if path == "/api/dashboards" and method == "POST":
                return self.send(m.store.save_dashboard(validate_dashboard(raw)), 201)
            match = re.fullmatch(r"/api/dashboards/([a-f0-9]{32})(/share)?", path)
            if match:
                if match[2] and method == "POST":
                    action = raw.get("action", "enable")
                    if action not in ("enable", "disable", "rotate"):
                        raise ValueError("Invalid sharing action.")
                    token = m.store.share(match[1], action)
                    return self.send(
                        {"enabled": bool(token), "path": f"/d/{token}" if token else None}
                    )
                if method == "PUT" and not match[2]:
                    return self.send(
                        m.store.save_dashboard(
                            validate_dashboard(raw), match[1], raw.get("revision")
                        )
                    )
                if method == "DELETE" and not match[2]:
                    m.store.delete_dashboard(match[1], raw.get("revision"))
                    return self.send({"ok": True})
            self.send({"error": "Not found."}, 404)
        except Conflict as exc:
            self.send({"error": str(exc)}, 409)
        except KeyError:
            self.send({"error": "Dashboard not found."}, 404)
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            self.send(
                {"error": str(exc) if isinstance(exc, ValueError) else "Invalid request."}, 400
            )
        except engine.ApiError as exc:
            self.send({"error": str(exc)}, 502)
        except Exception as exc:
            LOG.error("Request failed (%s)", type(exc).__name__)
            self.send(
                {"error": "The change could not be saved. Check the server and available storage."},
                500,
            )


class ConsoleServer(ThreadingHTTPServer):
    allow_reuse_address = os.name != "nt"
    max_requests = 32
    max_sessions = 256
    request_timeout = 15

    def __init__(self, *args, **kwargs):
        self.request_slots = threading.BoundedSemaphore(self.max_requests)
        super().__init__(*args, **kwargs)

    def get_request(self):
        request, address = super().get_request()
        request.settimeout(self.request_timeout)
        return request, address

    def process_request(self, request, client_address):
        if not self.request_slots.acquire(blocking=False):
            # Best-effort rejection without allocating another worker. Some TCP
            # stacks report a reset when the unread request is closed instead.
            try:
                request.settimeout(1)
                request.sendall(
                    b"HTTP/1.1 503 Service Unavailable\r\nConnection: close\r\nContent-Length: 0\r\nRetry-After: 5\r\n\r\n"
                )
            except OSError:
                pass
            finally:
                self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except Exception:
            self.request_slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.request_slots.release()

    def server_bind(self):
        if os.name == "nt":
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def create_server(host, port, manager, local_admin=False):
    server = ConsoleServer((host, port), Handler)
    server.daemon_threads = True
    server.manager = manager
    server.local_admin = local_admin and not getattr(manager, "standalone", False)
    server.sessions, server.attempts = {}, {}
    server.session_lock = threading.RLock()
    server.allowed_hosts = {"localhost", "127.0.0.1", "::1", socket.gethostname().lower()}
    server.allowed_hosts.update(
        x.strip().lower()
        for x in os.environ.get("CONSOLE_ALLOWED_HOSTS", "").split(",")
        if x.strip()
    )
    public = urlparse(os.environ.get("CONSOLE_PUBLIC_URL", ""))
    server.secure_cookies = public.scheme.lower() == "https"
    if public.hostname:
        server.allowed_hosts.add(public.hostname.lower())
    return server


def main():
    parser = argparse.ArgumentParser(
        description="Portainer Analytics alpha.3 · persistent dashboards and Portainer monitoring"
    )
    parser.add_argument("--host", default=os.environ.get("CONSOLE_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("CONSOLE_PORT", "8082")))
    parser.add_argument("--interval", type=int, default=5)
    parser.add_argument(
        "--data-dir", default=os.environ.get("CONSOLE_DATA_DIR", str(ROOT / "data"))
    )
    parser.add_argument("--require-login", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    store = Store(args.data_dir)
    manager = Manager(store, max(2, args.interval))
    try:
        server = create_server(args.host, args.port, manager)
    except OSError:
        manager.close()
        parser.exit(
            1,
            f"Port {args.port} is unavailable. Stop the conflicting service or choose another --port.\n",
        )
    if hasattr(signal, "SIGTERM"):
        signal.signal(
            signal.SIGTERM, lambda *_: threading.Thread(target=server.shutdown, daemon=True).start()
        )
    print(
        f"\n  PORTAINER ANALYTICS / alpha.3\n  http://localhost:{args.port}\n  Persistent dashboards · Ctrl+C to stop\n",
        flush=True,
    )
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        print("\nStopping Portainer Analytics…", flush=True)
    finally:
        server.server_close()
        manager.close()


if __name__ == "__main__":
    main()
