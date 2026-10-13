from __future__ import annotations

import http.client
import ipaddress
import socket
import ssl
import time
from urllib.parse import urljoin, urlsplit

MAX_BYTES = 8 * 1024 * 1024


class SubscriptionError(ValueError):
    """An error safe to show without revealing a subscription URL or payload."""


def subscription_url(value: str) -> str:
    value = value.strip()
    try:
        url = urlsplit(value)
        if (url.scheme not in {"http", "https"} or not url.hostname or url.username
                or url.password or url.fragment or len(value) > 4096
                or any(ord(c) < 33 for c in value)):
            raise ValueError
        port = url.port
        if port is not None and not 1 <= port <= 65535:
            raise ValueError
    except ValueError:
        raise SubscriptionError("请输入有效的 HTTP/HTTPS 订阅链接") from None
    return value


def fetch_subscription(value: str, *, timeout: float = 25) -> bytes:
    """Pin the actual socket to a validated public address, retaining TLS SNI."""
    deadline = time.monotonic() + timeout
    target = subscription_url(value)
    try:
        for redirect in range(5):
            parsed = urlsplit(target)
            hostname = parsed.hostname
            port = parsed.port or (443 if parsed.scheme == "https" else 80)
            addresses = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
            if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
                raise SubscriptionError("订阅服务器必须使用公网地址")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise SubscriptionError("订阅下载超时")
            family, socktype, proto, _, sockaddr = addresses[0]
            sock = socket.socket(family, socktype, proto)
            connection = http.client.HTTPConnection(hostname, port, timeout=remaining)
            try:
                sock.settimeout(remaining)
                sock.connect(sockaddr)
                if parsed.scheme == "https":
                    sock = ssl.create_default_context().wrap_socket(sock, server_hostname=hostname)
                connection.sock = sock
                path = parsed.path or "/"
                if parsed.query:
                    path += "?" + parsed.query
                connection.request("GET", path, headers={
                    "User-Agent": "mihomo/1.19.32", "Accept-Encoding": "identity",
                })
                response = connection.getresponse()
                if response.status in {301, 302, 303, 307, 308}:
                    location = response.getheader("Location")
                    if not location or redirect == 4:
                        raise SubscriptionError("订阅重定向次数过多")
                    next_target = subscription_url(urljoin(target, location))
                    if parsed.scheme == "https" and urlsplit(next_target).scheme != "https":
                        raise SubscriptionError("订阅重定向不能降低 HTTPS 安全性")
                    target = next_target
                    continue
                if response.status != 200:
                    raise SubscriptionError(f"订阅服务器返回 HTTP {response.status}")
                length = response.getheader("Content-Length")
                if length and int(length) > MAX_BYTES:
                    raise SubscriptionError("订阅内容超过 8 MB")
                result = bytearray()
                while True:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise SubscriptionError("订阅下载超时")
                    sock.settimeout(remaining)
                    block = response.read1(min(65536, MAX_BYTES + 1 - len(result)))
                    if not block:
                        return bytes(result)
                    result.extend(block)
                    if len(result) > MAX_BYTES:
                        raise SubscriptionError("订阅内容超过 8 MB")
            finally:
                connection.close()
                sock.close()
    except SubscriptionError:
        raise
    except Exception:
        raise SubscriptionError("订阅下载失败，请检查地址、证书和服务器网络") from None
    raise SubscriptionError("订阅下载失败")
