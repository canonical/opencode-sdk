#!/usr/bin/env python3
"""Minimal MCP server with OAuth discovery, DCR, and a loopback token endpoint.

The OAuth behaviour mirrors the mock authorization server in
anomalyco/opencode's packages/core/test/mcp-oauth.test.ts. The MCP response
shape mirrors packages/core/test/mcp.test.ts.
"""

import argparse
import json
import secrets
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlencode, urlparse


def local_ip():
    # Ask the routing table which source address the default route would
    # use. The TEST-NET-1 destination (RFC 5737) is never contacted; it
    # only selects the route.
    result = subprocess.run(
        ["ip", "route", "get", "192.0.2.1"],
        capture_output=True,
        text=True,
        check=False,
    )
    fields = result.stdout.split()
    if "src" in fields:
        return fields[fields.index("src") + 1]
    return "127.0.0.1"


class Handler(BaseHTTPRequestHandler):
    server_version = "opencode-mcp-oauth-fixture/1.0"

    def log_message(self, fmt, *args):
        print(f"{self.address_string()} {fmt % args}", flush=True)

    @property
    def base_url(self):
        return f"http://127.0.0.1:{self.server.port}"

    def respond(self, status, body=None, headers=None):
        payload = b"" if body is None else json.dumps(body).encode()
        self.send_response(status)
        if body is not None:
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(payload)))
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        url = urlparse(self.path)
        if url.path.startswith("/.well-known/oauth-protected-resource"):
            return self.respond(
                200,
                {
                    "resource": f"{self.base_url}/mcp",
                    "authorization_servers": [self.base_url],
                },
            )
        if url.path == "/.well-known/oauth-authorization-server":
            return self.respond(200, self.metadata())
        if url.path == "/authorize":
            return self.authorize(url)
        if url.path == "/health":
            return self.respond(200)
        return self.respond(404, {"error": "not_found"})

    def metadata(self):
        return {
            "issuer": self.base_url,
            "authorization_endpoint": (
                f"{self.server.public_auth_base}/authorize"
            ),
            "token_endpoint": f"{self.base_url}/token",
            "registration_endpoint": f"{self.base_url}/register",
            "response_types_supported": ["code"],
        }

    def authorize(self, url):
        query = parse_qs(url.query)
        redirect_uri = query.get("redirect_uri", [None])[0]
        if not redirect_uri:
            return self.respond(400, {"error": "invalid_request"})
        code = f"code-{secrets.token_hex(8)}"
        self.server.codes[code] = redirect_uri
        params = {"code": code}
        if query.get("state"):
            params["state"] = query["state"][0]
        separator = "&" if "?" in redirect_uri else "?"
        location = f"{redirect_uri}{separator}{urlencode(params)}"
        return self.respond(302, headers={"Location": location})

    def do_POST(self):
        url = urlparse(self.path)
        body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        if url.path == "/register":
            return self.register(body)
        if url.path == "/token":
            return self.token(body)
        if url.path == "/mcp":
            return self.mcp(body)
        return self.respond(404, {"error": "not_found"})

    def register(self, body):
        request = json.loads(body or b"{}")
        return self.respond(
            200,
            {
                "client_id": f"client-{secrets.token_hex(4)}",
                "redirect_uris": request.get("redirect_uris", []),
            },
        )

    def token(self, body):
        form = parse_qs(body.decode())
        if form.get("grant_type", [""])[0] != "authorization_code":
            return self.respond(400, {"error": "unsupported_grant_type"})
        code = form.get("code", [""])[0]
        if code not in self.server.codes:
            return self.respond(400, {"error": "invalid_grant"})
        self.server.codes.pop(code)
        access = f"access-{secrets.token_hex(8)}"
        self.server.tokens.add(access)
        return self.respond(
            200,
            {
                "access_token": access,
                "token_type": "Bearer",
                "refresh_token": f"refresh-{secrets.token_hex(8)}",
                "expires_in": 3600,
            },
        )

    def mcp(self, body):
        auth = self.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return self.respond(
                401,
                headers={
                    "WWW-Authenticate": (
                        'Bearer resource_metadata="'
                        f"{self.base_url}"
                        '/.well-known/oauth-protected-resource"'
                    )
                },
            )
        if auth.removeprefix("Bearer ") not in self.server.tokens:
            return self.respond(401)
        message = json.loads(body)
        if "id" not in message:
            return self.respond(202)
        method = message.get("method")
        if method == "initialize":
            result = {
                "protocolVersion": message.get("params", {}).get(
                    "protocolVersion", "2025-06-18"
                ),
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "oauth-fixture", "version": "1.0.0"},
            }
            return self.respond(
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
            return self.respond(
                200, {"jsonrpc": "2.0", "id": message["id"], "result": result}
            )
        return self.respond(
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
    server.port = args.port
    server.public_auth_base = public_auth_base.rstrip("/")
    server.codes = {}
    server.tokens = set()
    print(
        f"serving MCP and OAuth on 0.0.0.0:{args.port} "
        f"(authorization endpoint {server.public_auth_base})",
        flush=True,
    )
    server.serve_forever()


if __name__ == "__main__":
    main()
