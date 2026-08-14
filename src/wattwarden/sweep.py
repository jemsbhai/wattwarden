"""Sweep orchestrator: walk the configuration grid, manage llama-server
lifecycles, and write lab-protocol experiment artifacts.

Design rules:
- The driver runs on the benchmark host and launches llama-server itself,
  one process per condition, so every condition starts from a cold,
  identical server state.
- Experiment directories are append-only: an existing exp_id is refused,
  never overwritten.
- Everything nondeterministic that the tests need to control (process
  launch, health polling, HTTP client, sleeping) is injectable.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

import httpx
import yaml

from .bench import RequestMeasurement, measure_chat, summarize


@dataclass(frozen=True)
class Condition:
    model_name: str
    gguf_path: str
    quant: str
    threads: int

    @property
    def key(self) -> str:
        return f"{self.model_name}_t{self.threads}"


def load_config(config_path: Path) -> dict[str, Any]:
    with open(config_path, encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def build_conditions(
    config: dict[str, Any], cpu_count: int, repo_root: Path
) -> list[Condition]:
    """Expand models x threads, capping threads at the host core count.

    Fails fast if any model file is missing: a sweep that dies on
    condition seven wastes the first six.
    """
    requested: list[int] = list(config["sweep"]["threads"])
    effective = sorted({t for t in requested if t <= cpu_count})
    conditions: list[Condition] = []
    for model in config["models"]:
        gguf = repo_root / model["gguf"]
        if not gguf.is_file():
            raise FileNotFoundError(
                f"model file not found: {gguf} (download the GGUF into models/ "
                "before sweeping; models/ is gitignored by design)"
            )
        for threads in effective:
            conditions.append(
                Condition(
                    model_name=model["name"],
                    gguf_path=str(gguf),
                    quant=model["quant"],
                    threads=threads,
                )
            )
    return conditions


def environment_snapshot(server_bin: str | None) -> dict[str, Any]:
    snapshot: dict[str, Any] = {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "python": platform.python_version(),
        "cpu_count": os.cpu_count(),
        "hostname": platform.node(),
        "captured_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "server_bin": server_bin,
    }
    if server_bin:
        try:
            proc = subprocess.run(
                [server_bin, "--version"],
                capture_output=True,
                text=True,
                timeout=15,
            )
            snapshot["server_version"] = (proc.stdout or proc.stderr).strip()
        except (OSError, subprocess.SubprocessError) as exc:
            snapshot["server_version"] = f"unavailable: {exc}"
    return snapshot


def _default_health_getter(base_url: str) -> bool:
    try:
        response = httpx.get(base_url.rstrip("/") + "/health", timeout=2.0)
    except httpx.HTTPError:
        return False
    return response.status_code == 200


class ServerManager:
    """Launch and tear down one llama-server instance."""

    def __init__(
        self,
        server_bin: str,
        gguf_path: str,
        threads: int,
        port: int,
        *,
        ctx_size: int = 4096,
        log_path: Path | None = None,
        startup_timeout_s: float = 180.0,
        popen_factory: Callable[..., Any] = subprocess.Popen,
        health_getter: Callable[[str], bool] = _default_health_getter,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.base_url = f"http://127.0.0.1:{port}"
        self._args = [
            server_bin,
            "-m",
            gguf_path,
            "-t",
            str(threads),
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "-c",
            str(ctx_size),
        ]
        self._log_path = log_path
        self._startup_timeout_s = startup_timeout_s
        self._popen_factory = popen_factory
        self._health_getter = health_getter
        self._sleep = sleep
        self._proc: Any | None = None
        self._log_handle: Any | None = None

    def __enter__(self) -> ServerManager:
        if self._log_path is not None:
            self._log_path.parent.mkdir(parents=True, exist_ok=True)
            self._log_handle = open(self._log_path, "w", encoding="utf-8")
        self._proc = self._popen_factory(
            self._args,
            stdout=self._log_handle or subprocess.DEVNULL,
            stderr=subprocess.STDOUT if self._log_handle else subprocess.DEVNULL,
        )
        deadline = time.monotonic() + self._startup_timeout_s
        while time.monotonic() < deadline:
            if self._health_getter(self.base_url):
                return self
            self._sleep(0.5)
        self.__exit__(None, None, None)
        raise RuntimeError(
            f"llama-server did not become healthy within "
            f"{self._startup_timeout_s:.0f}s (args: {' '.join(self._args)})"
        )

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        if self._proc is not None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=10)
            except Exception:
                self._proc.kill()
            self._proc = None
        if self._log_handle is not None:
            self._log_handle.close()
            self._log_handle = None


def run_sweep(
    repo_root: Path,
    config_path: Path,
    exp_id: str,
    server_bin: str,
    *,
    popen_factory: Callable[..., Any] = subprocess.Popen,
    health_getter: Callable[[str], bool] = _default_health_getter,
    sleep: Callable[[float], None] = time.sleep,
    client_factory: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    """Execute the full grid and write lab artifacts. Returns summaries."""
    exp_dir = repo_root / "experiments" / exp_id
    if exp_dir.exists():
        raise ValueError(
            f"experiment directory already exists: {exp_dir} "
            "(experiments are append-only; pick a new exp_id)"
        )

    config = load_config(config_path)
    config_text = Path(config_path).read_text(encoding="utf-8")
    sweep_cfg = config["sweep"]
    conditions = build_conditions(config, os.cpu_count() or 1, repo_root)

    prompts_path = repo_root / sweep_cfg["prompts_file"]
    prompts = [
        line.strip()
        for line in prompts_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    prompt = prompts[int(sweep_cfg.get("prompt_index", 0))]

    (exp_dir / "raw").mkdir(parents=True)
    _write_json(exp_dir / "environment.json", environment_snapshot(server_bin))
    frozen = {
        "source_config_sha256": hashlib.sha256(config_text.encode()).hexdigest(),
        "exp_id": exp_id,
        "prompt": prompt,
        "n_predict": sweep_cfg["n_predict"],
        "repetitions": sweep_cfg["repetitions"],
        "seed": sweep_cfg["seed"],
        "conditions": [asdict(c) for c in conditions],
    }
    with open(exp_dir / "frozen_config.yaml", "w", encoding="utf-8") as handle:
        yaml.safe_dump(frozen, handle, sort_keys=False)

    port = int(sweep_cfg.get("port", 8091))
    repetitions = int(sweep_cfg["repetitions"])
    results: dict[str, Any] = {}

    for index, condition in enumerate(conditions, start=1):
        print(
            f"[{index}/{len(conditions)}] {condition.key}: starting server",
            flush=True,
        )
        log_path = exp_dir / "raw" / f"server_{condition.key}.log"
        with ServerManager(
            server_bin,
            condition.gguf_path,
            condition.threads,
            port,
            log_path=log_path,
            popen_factory=popen_factory,
            health_getter=health_getter,
            sleep=sleep,
        ) as server:
            client = client_factory() if client_factory else None
            measurements: list[RequestMeasurement] = []
            for rep in range(repetitions + 1):
                measurement = measure_chat(
                    server.base_url,
                    model=condition.model_name,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=int(sweep_cfg["n_predict"]),
                    seed=int(sweep_cfg["seed"]),
                    client=client,
                )
                if rep == 0:
                    continue  # warmup, unrecorded
                measurements.append(measurement)
            if client is not None and hasattr(client, "close"):
                client.close()

        raw_path = exp_dir / "raw" / f"{condition.key}.jsonl"
        with open(raw_path, "w", encoding="utf-8") as handle:
            for measurement in measurements:
                handle.write(json.dumps(measurement.to_record()) + "\n")

        results[condition.key] = {
            "condition": asdict(condition),
            "summary": summarize(measurements),
        }
        gen = results[condition.key]["summary"]["gen_tok_s"]["mean"]
        print(f"[{index}/{len(conditions)}] {condition.key}: done, tg {gen:.1f} tok/s", flush=True)

    _write_json(exp_dir / "results.json", results)
    return results


def probe_endpoint(
    url: str,
    model: str,
    *,
    repetitions: int = 5,
    max_tokens: int = 128,
    seed: int = 42,
    prompt: str = "Explain the difference between a process and a thread.",
    client: Any | None = None,
) -> dict[str, Any]:
    """Measure an already-running endpoint. No artifacts, quick numbers."""
    measurements = [
        measure_chat(
            url,
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            seed=seed,
            client=client,
        )
        for _ in range(repetitions)
    ]
    return summarize(measurements)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")
