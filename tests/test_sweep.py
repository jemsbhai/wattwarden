"""Tests for the sweep orchestrator: grid building, append-only artifact
discipline, server lifecycle, and fake-driven end-to-end runs."""

import json

import pytest
import yaml

from tests.conftest import FakeProc, FakeStreamClient
from wattwarden.sweep import (
    Condition,
    ServerManager,
    build_conditions,
    run_sweep,
)


def _write_config(repo_root, models=None, threads=None):
    models = models or [
        {"name": "qwen2.5-1.5b-instruct-q4_0",
         "gguf": "models/q4_0.gguf", "quant": "Q4_0"},
    ]
    config = {
        "server": {"url": "http://127.0.0.1:8091", "api_key": "none"},
        "models": models,
        "sweep": {
            "threads": threads or [1, 2, 4, 8, 16],
            "n_predict": 8,
            "repetitions": 2,
            "seed": 42,
            "prompts_file": "configs/prompts.txt",
            "prompt_index": 0,
            "port": 8091,
        },
    }
    (repo_root / "configs").mkdir(parents=True, exist_ok=True)
    config_path = repo_root / "configs" / "base.yaml"
    config_path.write_text(yaml.safe_dump(config), encoding="utf-8")
    (repo_root / "configs" / "prompts.txt").write_text(
        "Explain a hash table briefly.\nSecond prompt.\n", encoding="utf-8"
    )
    return config, config_path


def _touch_models(repo_root, config):
    for model in config["models"]:
        path = repo_root / model["gguf"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"gguf-stub")


def test_build_conditions_caps_threads_at_cpu_count(tmp_path):
    config, _ = _write_config(tmp_path)
    _touch_models(tmp_path, config)
    conditions = build_conditions(config, cpu_count=8, repo_root=tmp_path)
    assert [c.threads for c in conditions] == [1, 2, 4, 8]
    assert all(c.quant == "Q4_0" for c in conditions)


def test_build_conditions_missing_model_fails_fast(tmp_path):
    config, _ = _write_config(tmp_path)
    with pytest.raises(FileNotFoundError, match="models/"):
        build_conditions(config, cpu_count=4, repo_root=tmp_path)


def test_condition_key_is_stable():
    condition = Condition("m", "path", "Q4_0", 4)
    assert condition.key == "m_t4"


def test_run_sweep_refuses_existing_experiment(tmp_path):
    config, config_path = _write_config(tmp_path)
    _touch_models(tmp_path, config)
    (tmp_path / "experiments" / "exp_taken").mkdir(parents=True)
    with pytest.raises(ValueError, match="append-only"):
        run_sweep(tmp_path, config_path, "exp_taken", "llama-server")


def test_server_manager_kills_on_health_timeout(tmp_path):
    proc = FakeProc()
    manager = ServerManager(
        "llama-server",
        "model.gguf",
        threads=2,
        port=8099,
        startup_timeout_s=0.05,
        popen_factory=lambda *a, **k: proc,
        health_getter=lambda url: False,
        sleep=lambda s: None,
    )
    with pytest.raises(RuntimeError, match="did not become healthy"):
        manager.__enter__()
    assert proc.terminated


def test_run_sweep_writes_lab_artifacts_with_fakes(tmp_path, standard_events):
    config, config_path = _write_config(tmp_path, threads=[1, 2])
    _touch_models(tmp_path, config)
    procs = []

    def popen_factory(*args, **kwargs):
        proc = FakeProc()
        procs.append(proc)
        return proc

    results = run_sweep(
        tmp_path,
        config_path,
        "exp_777_fake",
        "llama-server",
        popen_factory=popen_factory,
        health_getter=lambda url: True,
        sleep=lambda s: None,
        client_factory=lambda: FakeStreamClient(standard_events),
    )

    exp_dir = tmp_path / "experiments" / "exp_777_fake"
    assert (exp_dir / "frozen_config.yaml").is_file()
    assert (exp_dir / "environment.json").is_file()
    assert (exp_dir / "results.json").is_file()

    keys = list(results)
    assert keys == ["qwen2.5-1.5b-instruct-q4_0_t1", "qwen2.5-1.5b-instruct-q4_0_t2"]
    for key in keys:
        raw = (exp_dir / "raw" / f"{key}.jsonl").read_text().strip().splitlines()
        # repetitions=2 recorded lines; the warmup request is not recorded
        assert len(raw) == 2
        record = json.loads(raw[0])
        assert record["output_tokens"] == 2
        assert results[key]["summary"]["n"] == 2
    # one server per condition, all torn down
    assert len(procs) == 2
    assert all(p.terminated for p in procs)

    frozen = yaml.safe_load((exp_dir / "frozen_config.yaml").read_text())
    assert frozen["exp_id"] == "exp_777_fake"
    assert len(frozen["conditions"]) == 2
    assert frozen["prompt"] == "Explain a hash table briefly."
