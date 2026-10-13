from __future__ import annotations

import copy
import hashlib
import json
import logging
import os
import re
import secrets
import subprocess
import threading
import time
import uuid
from pathlib import Path
from urllib.parse import quote, urlsplit

import httpx
import yaml

from .fetch import MAX_BYTES, SubscriptionError, fetch_subscription, subscription_url

TEST_URL = "https://www.gstatic.com/generate_204"
RESERVED = {"Proxy", "Auto", "DIRECT", "REJECT"}
logger = logging.getLogger(__name__)


def atomic_write(path: Path, data: bytes) -> None:
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with temporary.open("xb") as handle:
            os.chmod(temporary, 0o600)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        if os.name != "nt":
            directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
    finally:
        temporary.unlink(missing_ok=True)


def parse_nodes(payload: bytes) -> list[dict]:
    if not payload or len(payload) > MAX_BYTES:
        raise SubscriptionError("配置不能为空且不能超过 8 MB")
    try:
        depth = 0
        for count, event in enumerate(yaml.parse(payload)):
            if count > 50000 or isinstance(event, yaml.events.AliasEvent):
                raise ValueError
            if isinstance(event, (yaml.events.MappingStartEvent, yaml.events.SequenceStartEvent)):
                depth += 1
            elif isinstance(event, (yaml.events.MappingEndEvent, yaml.events.SequenceEndEvent)):
                depth -= 1
            if depth > 24:
                raise ValueError
        document = yaml.safe_load(payload)
        nodes = document.get("proxies") if isinstance(document, dict) else None
        if not isinstance(nodes, list) or not 1 <= len(nodes) <= 512:
            raise ValueError
        names = set()
        for node in nodes:
            if not isinstance(node, dict) or not isinstance(node.get("type"), str):
                raise ValueError
            name = node.get("name")
            if (not isinstance(name, str) or not 1 <= len(name) <= 160
                    or any(ord(c) < 32 for c in name) or name in RESERVED or name in names):
                raise ValueError
            names.add(name)
        return nodes
    except Exception:
        raise SubscriptionError("需要 Clash/Mihomo YAML 配置，包含 1–512 个名称唯一的 proxies 节点；不支持原始链接或 YAML 别名") from None


class Runtime:
    """Owns private profiles and the validated configuration of one Mihomo process."""

    def __init__(self, data: Path, binary: str, controller: str = "http://127.0.0.1:9091"):
        self.data = data
        self.binary = binary
        self.controller = controller
        self.lock = threading.RLock()
        self.stop_event = threading.Event()
        self.process = None
        self.thread = None
        self.data.mkdir(parents=True, exist_ok=True)
        os.chmod(self.data, 0o700)
        (self.data / "profiles").mkdir(exist_ok=True)
        os.chmod(self.data / "profiles", 0o700)
        self.secret = self.private_key(".controller-secret")
        self.manifest = self.data / "profiles.json"
        self.config = self.data / "config.yaml"
        self.state = {"schema": 1, "active": None, "profiles": []}
        if self.manifest.exists():
            try:
                self.state = json.loads(self.manifest.read_text("utf-8"))
                if self.state.get("schema") != 1 or not isinstance(self.state.get("profiles"), list):
                    raise ValueError
                self._configuration(self.state)
            except Exception:
                raise RuntimeError("订阅数据无法读取；请保留 /data 并检查备份，系统不会覆盖原有数据") from None

    def private_key(self, name: str) -> str:
        path = self.data / name
        if not path.exists():
            atomic_write(path, secrets.token_hex(32).encode())
        return path.read_text("utf-8").strip()

    def _cache(self, profile: dict) -> Path:
        name = profile["cache"]
        if Path(name).name != name or not name.endswith(".yaml"):
            raise ValueError("Invalid cache reference")
        return self.data / "profiles" / name

    def _configuration(self, state: dict) -> bytes:
        active = next((p for p in state["profiles"] if p["id"] == state["active"]), None)
        if state["active"] and active is None:
            raise ValueError("Missing active profile")
        nodes = parse_nodes(self._cache(active).read_bytes()) if active else []
        names = [node["name"] for node in nodes]
        groups = [{"name": "Proxy", "type": "select", "proxies": ["Auto", *names] if names else ["REJECT"]}]
        if names:
            groups.append({"name": "Auto", "type": "url-test", "proxies": names,
                           "url": TEST_URL, "interval": 300, "tolerance": 50})
        configuration = {
            "mixed-port": 7890, "allow-lan": True, "bind-address": "0.0.0.0",
            "mode": "rule", "log-level": "warning", "ipv6": False,
            "external-controller": urlsplit(self.controller).netloc, "secret": self.secret,
            "dns": {"enable": False}, "tun": {"enable": False},
            "profile": {"store-selected": True}, "proxies": nodes,
            "proxy-groups": groups, "rules": ["MATCH,Proxy"],
        }
        return yaml.safe_dump(configuration, allow_unicode=True, sort_keys=False).encode()

    def _core(self, method: str, path: str, **kwargs):
        try:
            with httpx.Client(trust_env=False, timeout=8) as client:
                response = client.request(method, self.controller + path,
                                          headers={"Authorization": "Bearer " + self.secret}, **kwargs)
                response.raise_for_status()
                return response.json() if response.content else {}
        except Exception:
            raise SubscriptionError("Mihomo 内核暂不可用，操作未完成") from None

    def _validate(self, path: Path):
        try:
            result = subprocess.run([self.binary, "-t", "-d", str(self.data), "-f", str(path)],
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
            if result.returncode:
                raise ValueError
        except Exception:
            raise SubscriptionError("Mihomo 校验未通过，请检查节点协议和配置字段；原有配置仍保留") from None

    def _commit(self, state: dict):
        """Validate and apply before committing metadata; compensate on any failure."""
        content = self._configuration(state)
        old_content = self._configuration(self.state)
        if content == old_content:
            atomic_write(self.manifest, json.dumps(state, ensure_ascii=False, indent=2).encode())
            self.state = state
            self._prune_cache()
            return
        candidate = self.data / ("candidate-" + uuid.uuid4().hex + ".yaml")
        applied = False
        try:
            atomic_write(candidate, content)
            self._validate(candidate)
            if self.process is not None:
                applied = True  # A timed-out request may already have applied.
                self._core("PUT", "/configs", params={"force": "true"}, json={"path": str(candidate)})
            atomic_write(self.config, content)
            atomic_write(self.manifest, json.dumps(state, ensure_ascii=False, indent=2).encode())
            self.state = state
        except Exception:
            try:
                atomic_write(self.config, old_content)
                if applied:
                    self._core("PUT", "/configs", params={"force": "true"}, json={"path": str(self.config)})
            except Exception:
                self._terminate()  # Never keep a candidate active if compensation fails.
            raise
        finally:
            candidate.unlink(missing_ok=True)
        self._prune_cache()

    def _prune_cache(self):
        live = {p["cache"] for p in self.state["profiles"]}
        for path in (self.data / "profiles").glob("*.yaml"):
            if path.name not in live and re.fullmatch(r"[0-9a-f]{32}-[0-9a-f]{16}\.yaml", path.name):
                try:
                    path.unlink(missing_ok=True)
                except OSError:
                    logger.warning("Unused profile cache could not be removed")

    def _terminate(self):
        process, self.process = self.process, None
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=4)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=4)

    def _launch(self):
        atomic_write(self.config, self._configuration(self.state))
        self._validate(self.config)
        self.process = subprocess.Popen([self.binary, "-d", str(self.data), "-f", str(self.config)],
                                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(40):
            if self.process.poll() is not None:
                break
            try:
                self._core("GET", "/version")
                return
            except SubscriptionError:
                time.sleep(0.15)
        self._terminate()
        raise RuntimeError("Mihomo 内核启动失败，请检查端口占用和 /data 权限")

    def start(self):
        with self.lock:
            self._launch()
        self.thread = threading.Thread(target=self._supervise, daemon=True)
        self.thread.start()

    def close(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=30)
        with self.lock:
            self._terminate()

    def _supervise(self):
        while not self.stop_event.wait(15):
            with self.lock:
                if self.process is None or self.process.poll() is not None:
                    try:
                        self._terminate()
                        self._launch()
                    except Exception:
                        logger.warning("Mihomo restart failed; will retry with saved configuration")
                        continue
                pending = [p["id"] for p in self.state["profiles"] if p["url"] and p["interval"]
                           and time.time() - p.get("attempted", p["updated"]) >= p["interval"] * 3600]
            for profile_id in pending:
                if self.stop_event.is_set():
                    break
                try:
                    self.refresh(profile_id)
                except Exception:
                    logger.warning("Subscription refresh failed; saved configuration retained")

    def _find(self, state: dict, profile_id: str) -> dict:
        profile = next((p for p in state["profiles"] if p["id"] == profile_id), None)
        if profile is None:
            raise SubscriptionError("该订阅不存在或已删除，请刷新页面")
        return profile

    def _save_cache(self, payload: bytes, profile_id: str) -> tuple[str, int]:
        nodes = parse_nodes(payload)
        clean = yaml.safe_dump({"proxies": nodes}, allow_unicode=True, sort_keys=False).encode()
        name = profile_id + "-" + hashlib.sha256(clean).hexdigest()[:16] + ".yaml"
        atomic_write(self.data / "profiles" / name, clean)
        return name, len(nodes)

    def _validate_state(self, state: dict, profile_id: str):
        check = copy.deepcopy(state)
        check["active"] = profile_id
        candidate = self.data / ("validate-" + profile_id + ".yaml")
        try:
            atomic_write(candidate, self._configuration(check))
            self._validate(candidate)
        finally:
            candidate.unlink(missing_ok=True)

    def add(self, name: str, url: str, content: str, interval: int):
        source = subscription_url(url) if url else ""
        if bool(source) == bool(content.strip()):
            raise SubscriptionError("请填写订阅链接或导入 YAML 配置，二选一")
        payload = fetch_subscription(source) if source else content.encode()
        with self.lock:
            if len(self.state["profiles"]) >= 50:
                raise SubscriptionError("最多保存 50 个订阅")
            profile_id = uuid.uuid4().hex
            cache, count = self._save_cache(payload, profile_id)
            state = copy.deepcopy(self.state)
            state["profiles"].append({"id": profile_id, "name": name, "url": source,
                                      "interval": interval if source else 0, "cache": cache,
                                      "count": count, "updated": time.time(), "error": ""})
            # Validate inactive profiles too, without making them active.
            self._validate_state(state, profile_id)
            if state["active"] is None:
                state["active"] = profile_id
            self._commit(state)

    def edit(self, profile_id: str, name: str, url: str, interval: int):
        with self.lock:
            previous = copy.deepcopy(self._find(self.state, profile_id))
        source = subscription_url(url) if url else previous["url"]
        payload = fetch_subscription(source) if source and source != previous["url"] else None
        with self.lock:
            state = copy.deepcopy(self.state)
            profile = self._find(state, profile_id)
            if profile != previous:
                raise SubscriptionError("订阅已更新，请刷新后重试")
            if payload is not None:
                profile["cache"], profile["count"] = self._save_cache(payload, profile_id)
                self._validate_state(state, profile_id)
                profile.update(updated=time.time(), error="")
            profile.update(name=name, url=source, interval=interval if source else 0)
            self._commit(state)

    def refresh(self, profile_id: str):
        with self.lock:
            previous = copy.deepcopy(self._find(self.state, profile_id))
        if not previous["url"]:
            raise SubscriptionError("导入的配置没有订阅链接，请添加新配置后切换")
        try:
            payload = fetch_subscription(previous["url"])
            with self.lock:
                state = copy.deepcopy(self.state)
                profile = self._find(state, profile_id)
                if profile != previous:
                    raise SubscriptionError("订阅已更新，请刷新后重试")
                profile["cache"], profile["count"] = self._save_cache(payload, profile_id)
                self._validate_state(state, profile_id)
                profile.update(updated=time.time(), attempted=time.time(), error="")
                self._commit(state)
        except Exception:
            self._failed_refresh(profile_id, previous)
            raise

    def _failed_refresh(self, profile_id: str, expected: dict):
        with self.lock:
            state = copy.deepcopy(self.state)
            try:
                profile = self._find(state, profile_id)
            except SubscriptionError:
                return
            if profile != expected:
                return  # A late download must not mark a newer revision as failed.
            profile.update(attempted=time.time(), error="更新失败，继续使用已保存的配置")
            atomic_write(self.manifest, json.dumps(state, ensure_ascii=False, indent=2).encode())
            self.state = state

    def activate(self, profile_id: str):
        with self.lock:
            state = copy.deepcopy(self.state)
            self._find(state, profile_id)
            state["active"] = profile_id
            self._commit(state)

    def delete(self, profile_id: str):
        with self.lock:
            state = copy.deepcopy(self.state)
            self._find(state, profile_id)
            if state["active"] == profile_id:
                raise SubscriptionError("请先切换到其他订阅，再删除当前订阅")
            state["profiles"] = [p for p in state["profiles"] if p["id"] != profile_id]
            self._commit(state)

    def overview(self) -> dict:
        with self.lock:
            profiles = [{"id": p["id"], "name": p["name"], "source": urlsplit(p["url"]).hostname or "本地导入",
                         "remote": bool(p["url"]), "interval": p["interval"], "count": p["count"],
                         "updated": p["updated"], "error": p.get("error", ""), "active": p["id"] == self.state["active"],
                         "actions": {"activate": p["id"] != self.state["active"], "refresh": bool(p["url"]),
                                     "delete": p["id"] != self.state["active"]}}
                        for p in self.state["profiles"]]
            try:
                version = self._core("GET", "/version").get("version", "")
                proxies = self._core("GET", "/proxies")["proxies"]
                selected = proxies.get("Proxy", {}).get("now", "")
                active = next((p for p in self.state["profiles"] if p["id"] == self.state["active"]), None)
                names = ["Auto", *[n["name"] for n in parse_nodes(self._cache(active).read_bytes())]] if active else []
                nodes = []
                for name in names:
                    native = proxies.get(name, {})
                    history = native.get("history", [])
                    nodes.append({"name": name, "type": native.get("type", ""), "selected": name == selected,
                                  "delay": history[-1].get("delay", 0) if history else None})
                return {"core_running": True, "core_version": version, "active": self.state["active"],
                        "profiles": profiles, "nodes": nodes, "selected": selected}
            except SubscriptionError:
                return {"core_running": False, "core_version": "", "active": self.state["active"],
                        "profiles": profiles, "nodes": [], "selected": ""}

    def _allowed_node(self, name: str):
        active = self._find(self.state, self.state["active"])
        names = {n["name"] for n in parse_nodes(self._cache(active).read_bytes())} | {"Auto"}
        if name not in names:
            raise SubscriptionError("该节点不在当前订阅中，请刷新页面")

    def select(self, name: str):
        with self.lock:
            self._allowed_node(name)
            self._core("PUT", "/proxies/Proxy", json={"name": name})

    def delay(self, name: str) -> int:
        with self.lock:
            self._allowed_node(name)
        result = self._core("GET", "/proxies/" + quote(name, safe="") + "/delay",
                            params={"timeout": 5000, "url": TEST_URL})
        return int(result["delay"])
