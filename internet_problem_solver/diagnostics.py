from __future__ import annotations

import json
import os
import queue
import threading
import re
import socket
import subprocess
import time
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable


@dataclass(frozen=True)
class CheckResult:
    key: str
    title: str
    status: str
    value: str
    explanation: str
    action: str = ""


def _run(command: list[str], timeout: float = 8) -> str:
    completed = subprocess.run(command, capture_output=True, text=True, timeout=timeout, errors="replace")
    return (completed.stdout + "\n" + completed.stderr).strip()


def _ping(host: str) -> tuple[str, str]:
    started = time.perf_counter()
    try:
        output = _run(["ping", "-n", "1", "-w", "1500", host], 4)
    except (OSError, subprocess.SubprocessError) as exc:
        return "fail", str(exc)
    elapsed = round((time.perf_counter() - started) * 1000)
    match = re.search(r"[=<]([0-9]+)ms", output, re.IGNORECASE)
    value = f"{match.group(1)} ms" if match else f"{elapsed} ms"
    return ("pass", value) if "TTL=" in output.upper() else ("fail", "No reply")


def _adapter_summary() -> tuple[str, str]:
    try:
        output = _run(["ipconfig", "/all"], 6)
    except (OSError, subprocess.SubprocessError) as exc:
        return "fail", str(exc)
    connected = [line.strip() for line in output.splitlines() if "IPv4 Address" in line or "Default Gateway" in line]
    return ("pass", " · ".join(connected[:4])) if connected else ("warn", "No active address or gateway found")


def _dns_summary() -> tuple[str, str]:
    started = time.perf_counter()
    try:
        socket.gethostbyname("example.com")
    except OSError as exc:
        return "fail", str(exc)
    return "pass", f"Resolved in {round((time.perf_counter() - started) * 1000)} ms"


def _https_summary() -> tuple[str, str]:
    started = time.perf_counter()
    try:
        request = urllib.request.Request("https://www.msftconnecttest.com/connecttest.txt", method="HEAD")
        with urllib.request.urlopen(request, timeout=6) as response:
            code = response.status
    except Exception as exc:
        return "fail", str(exc)
    return "pass", f"HTTP {code} in {round((time.perf_counter() - started) * 1000)} ms"


def _proxy_summary() -> tuple[str, str]:
    proxies = urllib.request.getproxies()
    return ("warn", json.dumps(proxies)) if proxies else ("pass", "No system proxy detected")


def diagnose(mode: str, cancel: Callable[[], bool] | None = None, selected: set[str] | None = None) -> list[CheckResult]:
    cancel = cancel or (lambda: False)
    checks: list[CheckResult] = []

    def add(key: str, title: str, fn, explanation: str, action: str = "") -> None:
        if cancel():
            return
        outcome: queue.Queue[tuple[str, str]] = queue.Queue()

        def probe() -> None:
            try:
                outcome.put(fn())
            except Exception as exc:
                outcome.put(("warn", f"Check could not complete: {exc}"))

        threading.Thread(target=probe, daemon=True).start()
        deadline = time.monotonic() + 9
        while not cancel():
            try:
                status, value = outcome.get(timeout=0.1)
                break
            except queue.Empty:
                if time.monotonic() >= deadline:
                    status, value = "warn", "Check timed out"
                    break
        else:
            return
        checks.append(CheckResult(key, title, status, value, explanation, action))

    if mode != "manual" or not selected or "adapter" in selected:
        add("adapter", "Network adapter", _adapter_summary, "The adapter needs a valid address and gateway.", "Open network settings")
    if mode != "manual" or not selected or "dns" in selected:
        add("dns", "DNS resolution", _dns_summary, "DNS converts website names into addresses.", "Flush DNS cache")
    if mode != "manual" or not selected or "internet" in selected:
        add("internet", "Internet reachability", lambda: _ping("1.1.1.1"), "A direct IP test separates internet access from DNS problems.")
    standard = {"https", "gateway"}
    if mode in {"standard", "deep"} or (mode == "manual" and (not selected or selected & standard)):
        if mode != "manual" or not selected or "https" in selected:
            add("latency", "HTTPS reachability", _https_summary, "HTTPS checks whether normal web traffic can leave the device.")
        if mode != "manual" or not selected or "gateway" in selected:
            add("packet_loss", "Gateway latency", lambda: _ping("192.168.1.1"), "A failed gateway ping can indicate a local Wi-Fi or router issue.")
    advanced = {"proxy", "route", "ipv6"}
    if mode == "deep" or (mode == "manual" and (not selected or selected & advanced)):
        if mode != "manual" or not selected or "proxy" in selected:
            add("proxy", "System proxy", _proxy_summary, "A stale proxy can block every browser and app.", "Open proxy settings")
        if mode != "manual" or not selected or "route" in selected:
            add("route", "Route table", lambda: ("pass", "Route table read") if _run(["route", "print"], 5) else ("warn", "Empty route table"), "Routes determine where packets are sent.")
        if mode != "manual" or not selected or "ipv6" in selected:
            add("ipv6", "IPv6 address", lambda: ("pass", socket.getaddrinfo("example.com", 443, socket.AF_INET6)[0][4][0]) if socket.has_ipv6 else ("warn", "IPv6 unavailable"), "IPv6 may affect some networks.")
    return checks


def summarize(results: list[CheckResult]) -> tuple[str, str, str]:
    failures = [item for item in results if item.status == "fail"]
    warnings = [item for item in results if item.status == "warn"]
    if failures:
        first = failures[0]
        return first.title, first.explanation, first.action
    if warnings:
        first = warnings[0]
        return first.title, first.explanation, first.action
    return "No problem found", "The selected checks completed successfully.", ""


class HistoryStore:
    def __init__(self, path: Path):
        self.path = path

    def append(self, mode: str, results: list[CheckResult]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        item = {"time": datetime.now(timezone.utc).isoformat(), "mode": mode, "results": [asdict(result) for result in results]}
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(item) + "\n")


def flush_dns() -> str:
    completed = subprocess.run(["ipconfig", "/flushdns"], capture_output=True, text=True, timeout=10)
    return (completed.stdout + "\n" + completed.stderr).strip()


def open_network_settings() -> None:
    os.startfile("ms-settings:network-status")


def open_proxy_settings() -> None:
    os.startfile("ms-settings:network-proxy")
