"""The homedata command, built from the same manifest as the tools."""

from __future__ import annotations

import json

import httpx
import pytest

from homedata_mcp import cli
from homedata_mcp.manifest import load_manifest


def test_every_tool_is_a_command():
    parser = cli.build_parser()
    commands = set(parser._subparsers._group_actions[0].choices)
    assert commands == {t["name"] for t in load_manifest()["tools"]} | {"tools"}


def test_tools_lists_prices(capsys):
    assert cli.main(["tools", "--compact"]) == 0
    listing = {row["tool"]: row["tokens"] for row in json.loads(capsys.readouterr().out)}
    assert listing["property_core"] == "25"
    assert listing["calc_mortgage"] == "free"
    assert listing["risks"] == "1, 5 when risk_type=all"
    assert listing["property_custom"] == "1 + add-ons"


def test_invalid_arguments_exit_2_without_a_request(monkeypatch, capsys):
    monkeypatch.setattr(cli, "HomedataClient", pytest.fail)  # must not even build a client
    assert cli.main(["property_core", "--uprn", "12a"]) == 2
    assert "digits only" in capsys.readouterr().err


def test_a_command_sends_the_manifest_request(monkeypatch, capsys):
    sent: list[httpx.Request] = []

    def handler(request):
        sent.append(request)
        return httpx.Response(200, json={"monthly_payment": 1425.16}, headers={"X-Tokens-Charged": "0"})

    real = cli.HomedataClient

    class Recording(real):
        def __init__(self, **kwargs):
            super().__init__(**kwargs, transport=httpx.MockTransport(handler))

    monkeypatch.setattr(cli, "HomedataClient", Recording)
    monkeypatch.delenv("HOMEDATA_API_KEY", raising=False)
    code = cli.main(["calc_mortgage", "--price", "300000", "--deposit", "30000", "--rate", "4", "--term", "25",
                     "--field", "monthly_payment"])
    out = capsys.readouterr()
    assert code == 0 and out.out.strip() == "1425.16"
    assert "tokens charged: 0" in out.err
    assert len(sent) == 1 and sent[0].url.path == "/calculators/mortgage/"
    assert "authorization" not in sent[0].headers, "a keyless free call must not send a key header"


def test_a_post_command_sends_a_json_body_and_an_idempotency_key(monkeypatch, capsys):
    # The server path is covered by the parity guard; the CLI builds its own send.
    sent: list[httpx.Request] = []

    def handler(request):
        sent.append(request)
        return httpx.Response(200, json={"uprn": 100040253100}, headers={"X-Tokens-Charged": "20"})

    real = cli.HomedataClient

    class Recording(real):
        def __init__(self, **kwargs):
            super().__init__(**kwargs, transport=httpx.MockTransport(handler))

    monkeypatch.setattr(cli, "HomedataClient", Recording)
    monkeypatch.setenv("HOMEDATA_API_KEY", "cli-test")
    assert cli.main(["listing_address", "--listing-id", "7f9200c5-93be-487a-befa-26aa8667b3e4"]) == 0
    assert len(sent) == 1
    req = sent[0]
    assert (req.method, req.url.path, dict(req.url.params)) == ("POST", "/listing-address/", {})
    assert json.loads(req.content) == {"listing_id": "7f9200c5-93be-487a-befa-26aa8667b3e4"}
    assert req.headers.get("Idempotency-Key")


def test_a_keyed_tool_needs_a_key(monkeypatch, capsys):
    monkeypatch.delenv("HOMEDATA_API_KEY", raising=False)
    assert cli.main(["property_core", "--uprn", "100023336956"]) == 2
    assert "HOMEDATA_API_KEY is required" in capsys.readouterr().err
