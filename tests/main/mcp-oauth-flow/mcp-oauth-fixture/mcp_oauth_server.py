#!/usr/bin/env python3
"""Minimal MCP server with OAuth discovery, DCR, and a loopback token endpoint.

The OAuth behaviour mirrors the mock authorization server in
anomalyco/opencode's packages/core/test/mcp-oauth.test.ts. The MCP response
shape mirrors packages/core/test/mcp.test.ts.
"""

import argparse
import json
import secrets
import socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlencode, urlparse


def local_ip():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        sock.close()


class State:
    def __init__(self, port, public_auth_base):
        self.port = port
        self.public_auth_base = public_auth_base
        self.clients = {}
        self.codes = {}
        self.tokens = set()

    @property
    def base_url(self):
        return f"http://127.0.0.1:{self.port}"

    @property
    def resource_url(self):
        return f"{self.base_url}/mcp"

    @property
    def resource_metadata_url(self):
        return f"{self.base_url}/.well-known/oauth-protected-resource"


class Handler(BaseHTTPRequestHandler):
    server_version = "opencode-mcp-oauth-fixture/1.0"

    @property
    def state(self):
        return self.server.state

    def log_message(self, fmt, *args):
        print(f"{self.address_string()} {fmt % args}", flush=True)

    def send_json(self, status, body, headers=None):
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(payload)

    def send_empty(self, status, headers=None):
        self.send_response(status)
        self.send_header("Content-Length", "0")
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()

    def do_GET(self):
        url = urlparse(self.path)
        if url.path in (
            "/.well-known/oauth-protected-resource",
            "/.well-known/oauth-protected-resource/mcp",
        ):
            return self.send_json(
                200,
                {
                    "resource": self.state.resource_url,
                    "authorization_servers": [self.state.base_url],
                },
            )
        if url.path in (
            "/.well-known/oauth-authorization-server",
            "/.well-known/openid-configuration",
        ):
            return self.send_json(
                200,
                {
                    "issuer": self.state.base_url,
                    "authorization_endpoint": (
                        f"{self.state.public_auth_base}/authorize"
                    ),
                    "token_endpoint": f"{self.state.base_url}/token",
                    "registration_endpoint": f"{self.state.base_url}/register",
                    "response_types_supported": ["code"],
                    "grant_types_supported": [
                        "authorization_code",
                        "refresh_token",
                    ],
                    "code_challenge_methods_supported": ["S256"],
                    "token_endpoint_auth_methods_supported": ["none"],
                },
            )
        if url.path == "/authorize":
            query = parse_qs(url.query)
            redirect_uri = query.get("redirect_uri", [None])[0]
            if not redirect_uri:
                return self.send_json(400, {"error": "invalid_request"})
            code = f"code-{secrets.token_hex(8)}"
            self.state.codes[code] = {
                "redirect_uri": redirect_uri,
                "client_id": query.get("client_id", [None])[0],
            }
            params = {"code": code}
            if query.get("state"):
                params["state"] = query["state"][0]
            separator = "&" if "?" in redirect_uri else "?"
            location = f"{redirect_uri}{separator}{urlencode(params)}"
            return self.send_empty(302, {"Location": location})
        if url.path == "/health":
            payload = b"ok\n"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return None
        return self.send_json(404, {"error": "not_found"})

    def do_POST(self):
        url = urlparse(self.path)
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        if url.path == "/register":
            request = json.loads(body or b"{}")
            client_id = f"client-{secrets.token_hex(4)}"
            self.state.clients[client_id] = request.get("redirect_uris", [])
            return self.send_json(
                200,
                {
                    "client_id": client_id,
                    "redirect_uris": request.get("redirect_uris", []),
                    "grant_types": ["authorization_code", "refresh_token"],
                    "response_types": ["code"],
                    "token_endpoint_auth_method": "none",
                },
            )
        if url.path == "/token":
            return self.token(body)
        if url.path == "/mcp":
            return self.mcp(body)
        return self.send_json(404, {"error": "not_found"})

    def token(self, body):
        form = parse_qs(body.decode())
        grant = form.get("grant_type", [""])[0]
        if grant == "authorization_code":
            code = form.get("code", [""])[0]
            if code not in self.state.codes:
                return self.send_json(400, {"error": "invalid_grant"})
            self.state.codes.pop(code)
        elif grant != "refresh_token":
            return self.send_json(400, {"error": "unsupported_grant_type"})
        access = f"access-{secrets.token_hex(8)}"
        refresh = f"refresh-{secrets.token_hex(8)}"
        self.state.tokens.add(access)
        return self.send_json(
            200,
            {
                "access_token": access,
                "token_type": "Bearer",
                "refresh_token": refresh,
                "expires_in": 3600,
                "scope": "tools",
            },
        )

    def mcp(self, body):
        auth = self.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return self.send_empty(
                401,
                {
                    "WWW-Authenticate": (
                        'Bearer resource_metadata="'
                        f'{self.state.resource_metadata_url}"'
                    )
                },
            )
        if auth.removeprefix("Bearer ") not in self.state.tokens:
            return self.send_empty(401)
        try:
            message = json.loads(body)
        except json.JSONDecodeError:
            return self.send_json(400, {"error": "invalid_json"})
        if "id" not in message:
            return self.send_empty(202)
        method = message.get("method")
        params = message.get("params") or {}
        if method == "initialize":
            result = {
                "protocolVersion": params.get("protocolVersion", "2025-06-18"),
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "oauth-fixture", "version": "1.0.0"},
            }
            return self.send_json(
                200,
                {"jsonrpc": "2.0", "id": message["id"], "result": result},
                {"Mcp-Session-Id": "fixture-session"},
            )
        if method == "tools/list":
            result = {
                "tools": [
                    {
                        "name": "ping",
                        "description": "Return pong.",
                        "inputSchema": {"type": "object", "properties": {}},
                    }
                ]
            }
            return self.send_json(
                200, {"jsonrpc": "2.0", "id": message["id"], "result": result}
            )
        if method == "tools/call":
            result = {
                "content": [{"type": "text", "text": "pong"}],
                "isError": False,
            }
            return self.send_json(
                200, {"jsonrpc": "2.0", "id": message["id"], "result": result}
            )
        return self.send_json(
            200,
            {
                "jsonrpc": "2.0",
                "id": message["id"],
                "error": {"code": -32601, "message": "Method not found"},
            },
        )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=18080)
    parser.add_argument("--public-auth-base", default=None)
    args = parser.parse_args()
    public_auth_base = (
        args.public_auth_base or f"http://{local_ip()}:{args.port}"
    )
    server = ThreadingHTTPServer(("0.0.0.0", args.port), Handler)
    server.state = State(args.port, public_auth_base.rstrip("/"))
    print(
        f"serving MCP and OAuth on 0.0.0.0:{args.port} "
        f"(authorization endpoint {server.state.public_auth_base})",
        flush=True,
    )
    server.serve_forever()


if __name__ == "__main__":
    main()
