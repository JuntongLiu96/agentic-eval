"""Unit coverage for the harness probe layer (text / store / staleness).

The store + staleness probes hit the memory service over httpx; we inject an
``httpx.MockTransport`` by monkeypatching ``httpx.AsyncClient`` so no live
service is required.
"""
from __future__ import annotations

import httpx
import pytest

from app.services import harness_probes as hp


# ───────────────────────── text probes (pure) ─────────────────────────

def test_text_probe_presence_and_forget_clean():
    spec = {"text": [
        {"turn_index": 0, "role": "presence", "must_present": ["Rust"], "must_absent": ["Python"]},
        {"turn_index": 1, "role": "forget", "must_present": [], "must_absent": ["Python"]},
    ]}
    out = hp.compute_text_probes(["I prefer Rust now", "no stored preference"], spec)
    assert out["mpa"] == 1.0
    assert out["faa"] == 1.0
    assert out["fama"] == 1.0


def test_text_probe_leak_drops_presence_and_fama():
    spec = {"text": [
        {"turn_index": 0, "role": "presence", "must_present": ["Rust"], "must_absent": ["Python"]},
        {"turn_index": 1, "role": "forget", "must_present": [], "must_absent": ["Python"]},
    ]}
    # Python leaks into the forget turn → faa drops, fama penalized.
    out = hp.compute_text_probes(["Rust", "you used to like Python"], spec)
    assert out["mpa"] == 1.0
    assert out["faa"] == 0.0
    assert out["fama"] < 1.0


def test_text_probe_erasure_completeness():
    spec = {"text": [
        {"turn_index": 0, "role": "erasure", "must_absent": ["Munich", "penicillin"]},
    ]}
    out = hp.compute_text_probes(["I have no record of that"], spec)
    assert out["erasure_completeness"] == 1.0
    assert out["forbidden_memory_returned"] is False

    leak = hp.compute_text_probes(["you live in Munich"], spec)
    assert leak["erasure_completeness"] == 0.5
    assert leak["forbidden_memory_returned"] is True


def test_text_probe_abstains_without_spec():
    assert hp.compute_text_probes(["anything"], {}) == {}
    assert hp.compute_text_probes(["anything"], None) == {}


# ───────────────────────── store / staleness (mocked HTTP) ─────────────────────────

def _patch_transport(monkeypatch, handler):
    """Route every AsyncClient through a MockTransport using ``handler``."""
    transport = httpx.MockTransport(handler)
    orig_init = httpx.AsyncClient.__init__

    def init(self, *args, **kwargs):
        kwargs["transport"] = transport
        kwargs.pop("base_url", None)
        orig_init(self, *args, base_url="http://memsvc.test", **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "__init__", init)


@pytest.mark.asyncio
async def test_superseded_card_filtered(monkeypatch):
    # /memory list returns only the live (new) card; the superseded id is absent.
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/memory":
            return httpx.Response(200, json={"memories": [{"memory_id": "mem-new"}]})
        return httpx.Response(404)

    _patch_transport(monkeypatch, handler)
    spec = {"store": {"scope": {"org_id": "acme"}, "superseded": ["mem-old"]}}
    out = await hp.probe_memory_store(spec)
    assert out["superseded_cards_filtered"] is True


@pytest.mark.asyncio
async def test_superseded_card_still_live_fails(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/memory":
            return httpx.Response(200, json={"memories": [
                {"memory_id": "mem-new"}, {"memory_id": "mem-old"}]})
        return httpx.Response(404)

    _patch_transport(monkeypatch, handler)
    spec = {"store": {"scope": {"org_id": "acme"}, "superseded": ["mem-old"]}}
    out = await hp.probe_memory_store(spec)
    assert out["superseded_cards_filtered"] is False
    assert out["superseded_still_live_ids"] == ["mem-old"]


@pytest.mark.asyncio
async def test_staleness_catch_and_false_positive(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/memory/retrieve":
            return httpx.Response(200, json={"passages": [
                {"memory_id": "mem-stale", "stale": True},
                {"memory_id": "mem-fresh", "stale": False},
            ]})
        return httpx.Response(404)

    _patch_transport(monkeypatch, handler)
    spec = {"staleness": [{
        "turn_index": 0,
        "must_flag": ["mem-stale"],
        "must_not_flag": ["mem-fresh"],
        "dropped_columns": ["customers.email_address"],
        "scope": {"org_id": "acme"},
    }]}
    out = await hp.probe_staleness(spec)
    assert out["staleness_catch_rate"] == 1.0
    assert out["staleness_false_positive_rate"] == 0.0


@pytest.mark.asyncio
async def test_staleness_missing_passage_counts_as_not_caught(monkeypatch):
    # mem-stale never returned → cannot prove flagged → catch_rate 0.
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/memory/retrieve":
            return httpx.Response(200, json={"passages": []})
        return httpx.Response(404)

    _patch_transport(monkeypatch, handler)
    spec = {"staleness": [{"must_flag": ["mem-stale"], "scope": {"org_id": "acme"}}]}
    out = await hp.probe_staleness(spec)
    assert out["staleness_catch_rate"] == 0.0


@pytest.mark.asyncio
async def test_staleness_abstains_without_spec(monkeypatch):
    assert await hp.probe_staleness({}) == {}
    assert await hp.probe_staleness(None) == {}
