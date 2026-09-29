"""The CLI runs the same pipeline with a human at the keyboard."""

import builtins

import pytest

import cli
from tests.fakes import FakeGroq, FakeHindsight, llm_json


@pytest.fixture
def fakes(monkeypatch):
    hindsight, groq = FakeHindsight(), FakeGroq(llm_json("APPROVED", 0.9))
    monkeypatch.setattr(cli, "make_client", lambda settings, require_bank=True: hindsight)
    monkeypatch.setattr(cli, "AsyncGroq", lambda api_key: groq)
    return hindsight, groq


def keyboard(monkeypatch, answers):
    replies = iter(answers)

    def fake_input(prompt=""):
        try:
            return next(replies)
        except StopIteration:
            raise EOFError from None

    monkeypatch.setattr(builtins, "input", fake_input)


def test_cli_story(fakes, monkeypatch, capsys):
    hindsight, _ = fakes
    keyboard(monkeypatch, ["a", "Contract price changed", "", "a", "Same contract", "", "x", "n", "Check with XYZ"])
    assert cli.main(["INV001", "INV002", "INV003", "--fresh"]) == 0
    out = capsys.readouterr().out
    assert "Summary" in out and "VERIFIED_MATCH" in out and "Decision remembered" in out
    [bank] = hindsight.created_banks
    assert bank["bank_id"].startswith("hap-demo-")
    assert len(hindsight.documents(bank["bank_id"])) == 3


def test_cli_skip_and_end_of_input(fakes, monkeypatch, capsys):
    keyboard(monkeypatch, ["s"])
    assert cli.main([]) == 0
    assert "skipped" in capsys.readouterr().out
    assert fakes[0].calls_to("retain") == []


def test_cli_errors(fakes, monkeypatch, capsys):
    assert cli.main(["INV999"]) == 1
    assert "Not in demo_scenario.json: INV999" in capsys.readouterr().out
    monkeypatch.setattr(cli, "make_client", lambda settings, require_bank=True: None)
    assert cli.main([]) == 2
    assert "Hindsight is required" in capsys.readouterr().out


def test_cli_fresh_bank_failure(fakes, monkeypatch, capsys):
    fakes[0].fail_next(402)
    assert cli.main(["--fresh"]) == 2
    assert "credits exhausted" in capsys.readouterr().out


def test_cli_invoice_without_a_po(fakes, monkeypatch, tmp_path, capsys):
    (tmp_path / "invoices.json").write_text(
        '[{"invoice_id": "X1", "vendor": "Nobody", "invoice_price": 5, "quantity": 1, "invoice_date": "2026-09-28"}]')
    keyboard(monkeypatch, [])
    assert cli.main(["--invoices", str(tmp_path / "invoices.json")]) == 0
    assert "No purchase order on file for vendor 'Nobody'" in capsys.readouterr().out
