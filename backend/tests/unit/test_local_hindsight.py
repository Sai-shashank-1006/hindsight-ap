"""A Hindsight server on this machine: no API key needed, and scripts/local_hindsight.py sizes it
for Groq's free tier. Nothing here starts a server."""

import pytest

from app.config import Settings, load_settings
from app.memory.hindsight import make_client
from scripts import local_hindsight


@pytest.mark.parametrize("url, key, usable", [
    ("http://127.0.0.1:8888", None, True),
    ("http://localhost:8888", None, True),
    ("https://api.hindsight.vectorize.io", None, False),  # Hindsight Cloud needs a key
    ("https://api.hindsight.vectorize.io", "hs_key", True),
])
def test_a_local_server_needs_no_key(url, key, usable):
    settings = Settings(hindsight_api_url=url, hindsight_api_key=key, hindsight_bank_id="bank")
    assert (settings.hindsight_local, settings.hindsight_usable, settings.hindsight_configured) == (
        "127.0.0.1" in url or "localhost" in url, usable, usable)
    assert (make_client(settings) is not None) is usable  # building a client makes no network call


def test_a_local_server_still_needs_a_bank():
    settings = Settings(hindsight_api_url="http://127.0.0.1:8888")
    assert not settings.hindsight_configured and make_client(settings) is None
    assert make_client(settings, require_bank=False) is not None


def test_the_server_env_fits_the_groq_free_tier(monkeypatch):
    monkeypatch.setenv("HINDSIGHT_API_KEY", "hs_TEST_SECRET_DO_NOT_LEAK")  # PaySage's client setting
    env = local_hindsight.server_env("gsk_TEST", "openai/gpt-oss-20b", "qwen/qwen3.8-27b", 8888)
    assert "HINDSIGHT_API_KEY" not in env and "HINDSIGHT_BANK_ID" not in env  # never mistaken for server settings
    assert env["HINDSIGHT_API_LLM_GROQ_SERVICE_TIER"] == "on_demand"  # "auto" needs a paid plan
    assert (env["HINDSIGHT_API_LLM_PROVIDER"], env["HINDSIGHT_API_LLM_API_KEY"]) == ("groq", "gsk_TEST")
    assert env["HINDSIGHT_API_REFLECT_LLM_MODEL"] != env["HINDSIGHT_API_RETAIN_LLM_MODEL"]  # separate budgets
    assert env["HINDSIGHT_API_REFLECT_MAX_ITERATIONS"] == "4"  # halved at budget "low": one lookup and the answer
    assert env["HINDSIGHT_API_RETAIN_LLM_REASONING_EFFORT"] == "low"
    assert (env["HINDSIGHT_API_HOST"], env["PYTHONUTF8"]) == ("127.0.0.1", "1")


def test_launcher_explains_how_to_install(monkeypatch, capsys):
    monkeypatch.setattr(local_hindsight.shutil, "which", lambda name: None)
    assert local_hindsight.main([]) == 2
    assert "uv tool install hindsight-api" in capsys.readouterr().out


def test_launcher_runs_the_server_on_this_machine_only(monkeypatch, capsys):
    started = {}
    monkeypatch.setattr(local_hindsight.shutil, "which", lambda name: "hindsight-api.exe")
    monkeypatch.setattr(local_hindsight.subprocess, "call",
                        lambda command, env, cwd: started.update(command=command, env=env) or 0)
    assert local_hindsight.main(["--port", "9000"]) == 0
    assert started["command"] == ["hindsight-api.exe", "--host", "127.0.0.1", "--port", "9000"]
    assert started["env"]["HINDSIGHT_API_LLM_API_KEY"] == load_settings().groq_api_key
    assert "TEST_SECRET" not in capsys.readouterr().out
