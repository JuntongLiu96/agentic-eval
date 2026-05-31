"""Harness probe layer — metrics the agent cannot self-report.

A second class of metric (beyond the comparative ones in
``orchestrator._enrich_with_harness_metrics``) requires an oracle, a probe of
the memory store, or a cross-round / cross-tenant view. This module computes
them. See ``eval_suite/HARNESS_PROBES.md`` for the authoring contract.

Four families:

  * **text probes** — derived from the agent's per-turn response text against
    ``must_present`` / ``must_absent`` term lists declared on probe sessions.
    Produces the FAMA family (mpa/faa/fama) and erasure-leakage metrics. No
    network calls.

  * **store probes** — HTTP ``GET /memory`` / ``GET /memory/{id}`` against the
    memory service to measure dedup, confidence series, erasure tombstones, and
    supersession filtering (``store.superseded`` — M1: a superseded card must be
    excluded from scoped reads).

  * **tenant probes** — HTTP ``POST /memory/retrieve`` under a *sibling*
    tenant's scope to confirm zero cross-tenant leakage and that out-of-scope
    reads 404/empty (never 403, which would confirm existence).

  * **staleness probes** — HTTP ``POST /memory/retrieve`` with a dropped-column
    / repo-file manifest, reading ``passages[].stale`` to score the JIT
    schema-drift verifier (``staleness_catch_rate`` /
    ``staleness_false_positive_rate`` — GN-007/CA-007).

All functions return a flat ``dict[str, Any]`` of metric → value, merged into
``agent_metadata`` by the orchestrator (idempotent: agent self-report wins).
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)


def _memsvc_base() -> str:
    return os.environ.get("MEMSVC_BASE_URL", "http://localhost:9200")


def _auth_headers() -> dict[str, str]:
    tok = os.environ.get("MEMSVC_TOKEN", "")
    return {"Authorization": f"Bearer {tok}"} if tok else {}


def _scope_headers(scope: dict[str, Any] | None) -> dict[str, str]:
    s = scope or {}
    h = dict(_auth_headers())
    h["X-Org-Id"] = str(s.get("org_id") or "")
    h["X-Repo-Id"] = str(s.get("repo_id") or "")
    h["X-Agent-Id"] = str(s.get("agent_id") or "")
    return h


# ───────────────────────── text probes ─────────────────────────

def _terms_present(text: str, terms: list[str]) -> bool:
    t = (text or "").lower()
    return all(term.lower() in t for term in terms if isinstance(term, str))


def _any_term_present(text: str, terms: list[str]) -> list[str]:
    t = (text or "").lower()
    return [term for term in terms if isinstance(term, str) and term.lower() in t]


def compute_text_probes(
    per_turn_responses: list[str],
    probe_spec: dict[str, Any] | None,
) -> dict[str, Any]:
    """Compute FAMA-family + erasure metrics from per-turn response text.

    ``probe_spec.text`` is a list of ``{turn_index, role, must_present,
    must_absent}`` entries (emitted by the exporter from ``sessions[].probe``).
    ``role`` ∈ ``presence | forget | erasure | baseline``.
    """
    spec = (probe_spec or {}).get("text") or []
    if not spec:
        return {}

    presence_total = presence_clean = 0
    forget_total = forget_clean = 0
    forbidden_checks = leaked = 0
    bpr_total = bpr_clean = 0
    preserve_total = preserve_clean = 0

    for entry in spec:
        if not isinstance(entry, dict):
            continue
        ti = entry.get("turn_index")
        if not isinstance(ti, int) or ti < 0 or ti >= len(per_turn_responses):
            # No response captured for this probe turn → treat as a failed probe
            # (cannot prove the fact surfaced / stayed clean).
            resp = ""
        else:
            resp = per_turn_responses[ti] or ""
        must_present = entry.get("must_present") or []
        must_absent = entry.get("must_absent") or []
        role = entry.get("role")

        present_ok = _terms_present(resp, must_present) if must_present else True
        leaks = _any_term_present(resp, must_absent) if must_absent else []
        clean = present_ok and not leaks

        if role == "presence":
            presence_total += 1
            presence_clean += 1 if clean else 0
        elif role == "forget":
            forget_total += 1
            forget_clean += 1 if clean else 0
        elif role == "erasure":
            forbidden_checks += len(must_absent)
            leaked += len(leaks)
            # Selective erasure: an erasure-role probe MAY also carry
            # must_present terms (a fact deliberately KEPT — e.g. GN-004 erases
            # address + allergy but preserves the name). Those must still
            # surface. Tracked separately so a kept fact failing to appear
            # fails selective_erasure_preserved_unrelated without inflating
            # erasure_completeness (which is purely about leakage).
            if must_present:
                preserve_total += 1
                preserve_clean += 1 if present_ok else 0
        elif role == "bpr":
            # Branch-on-Prior-Result: the agent resumed correctly iff it
            # surfaced the required prior-state terms (must_present) and
            # avoided the forbidden re-do terms (must_absent). One probe per
            # session; bpr_rate is the clean fraction across them.
            bpr_total += 1
            bpr_clean += 1 if clean else 0
        # baseline: sanity-only, not scored

    out: dict[str, Any] = {}
    if presence_total:
        out["mpa"] = presence_clean / presence_total
    if forget_total:
        out["faa"] = forget_clean / forget_total
    if presence_total or forget_total:
        mpa = out.get("mpa", 1.0 if not presence_total else 0.0)
        faa = out.get("faa", 1.0 if not forget_total else 0.0)
        lam = forget_total / (presence_total + forget_total) if (presence_total + forget_total) else 0.0
        out["fama"] = max(0.0, mpa - lam * (1.0 - faa))
    if forbidden_checks:
        out["erasure_completeness"] = 1.0 - (leaked / forbidden_checks)
        out["forbidden_memory_returned"] = leaked > 0
    if preserve_total:
        out["selective_erasure_preserved_unrelated"] = preserve_clean == preserve_total
    if bpr_total:
        out["bpr_rate"] = bpr_clean / bpr_total
    return out


# ───────────────────────── store probes ─────────────────────────

async def _list_scope(client: httpx.AsyncClient, scope: dict[str, Any] | None) -> list[dict[str, Any]]:
    try:
        r = await client.get("/memory", headers=_scope_headers(scope))
        if r.status_code != 200:
            return []
        body = r.json()
        return body.get("memories", []) if isinstance(body, dict) else (body or [])
    except Exception as e:  # noqa: BLE001
        logger.warning("store-probe list failed: %s", e)
        return []


async def probe_memory_store(
    probe_spec: dict[str, Any] | None,
    round_series: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Probe ``GET /memory`` for dedup + tombstone; derive confidence series.

    ``round_series`` is an optional list of per-round agent_metadata dicts used
    only when the case wants a confidence trend the store alone can't give
    (the store holds the *current* card, not its history).
    """
    store = (probe_spec or {}).get("store") or {}
    if not store:
        return {}
    out: dict[str, Any] = {}
    scope = store.get("scope")
    async with httpx.AsyncClient(base_url=_memsvc_base(), timeout=30) as c:
        # dedup: count cards whose task_pattern contains the expected substring
        dedup = store.get("dedup")
        if isinstance(dedup, dict):
            pattern = (dedup.get("task_pattern") or "").lower()
            rows = await _list_scope(c, scope)
            matches = [m for m in rows
                       if pattern and pattern in str(m.get("task_pattern", "")).lower()]
            out["dedup_count"] = len(matches)

        # tombstone: GET the erased id, confirm body gone + audit hash kept
        tomb = store.get("tombstone")
        if isinstance(tomb, dict) and tomb.get("memory_id"):
            mid = tomb["memory_id"]
            try:
                r = await c.get(f"/memory/{mid}", headers=_scope_headers(scope))
                if r.status_code == 200:
                    body = r.json()
                    out["audit_trail_retained"] = bool(body.get("audit_hash")) and body.get("erased", False)
                    out["original_body_recoverable"] = body.get("body") not in (None, "")
                else:
                    # 404 after erase is acceptable only if we don't require an
                    # audit hash; the case asserts audit_trail_retained, so a
                    # 404 means the trail is gone → fail.
                    out["audit_trail_retained"] = False
                    out["original_body_recoverable"] = False
            except Exception as e:  # noqa: BLE001
                logger.warning("tombstone probe failed: %s", e)

        # confidence: prefer live store value; supplement with round series
        conf = store.get("confidence")
        if isinstance(conf, dict) and conf.get("memory_id"):
            mid = conf["memory_id"]
            series: list[float] = []
            for md in (round_series or []):
                v = (md or {}).get("confidence_by_id", {}).get(mid)
                if isinstance(v, (int, float)):
                    series.append(float(v))
            if not series:
                try:
                    r = await c.get(f"/memory/{mid}", headers=_scope_headers(scope))
                    if r.status_code == 200:
                        series = [float(r.json().get("confidence", 0.0))]
                except Exception:  # noqa: BLE001
                    pass
            if len(series) >= 2:
                out["confidence_monotonic_increase"] = all(
                    b >= a for a, b in zip(series, series[1:])
                )
                out["confidence_series"] = series
            elif series:
                out["confidence_series"] = series

        # supersession: each id in store.superseded must be filtered from the
        # owner's scoped retrieve/list (M1 — a superseded card is kept for audit
        # but excluded from scoped reads). A 200 with the card still listed means
        # the stale preference can still leak (the GN-001 failure mode).
        superseded = store.get("superseded")
        if isinstance(superseded, list) and superseded:
            rows = await _list_scope(c, scope)
            live_ids = {m.get("memory_id") for m in rows}
            still_live = [mid for mid in superseded if mid in live_ids]
            out["superseded_cards_filtered"] = len(still_live) == 0
            if still_live:
                out["superseded_still_live_ids"] = still_live
    return out


# ───────────────────────── staleness probes ─────────────────────────

async def probe_staleness(probe_spec: dict[str, Any] | None) -> dict[str, Any]:
    """Probe JIT staleness flagging via ``POST /memory/retrieve``.

    ``probe_spec.staleness`` is a list of ``{turn_index, must_flag,
    must_not_flag, dropped_columns, repo_files?, scope?, query?}`` entries
    (emitted by the exporter from ``assertions.jit_verification`` + the case's
    schema_mutation manifest). For each entry we retrieve under the case scope,
    passing the dropped-column / repo-file manifest, and read ``passages[].stale``.

    Computes, across all entries:
      * ``staleness_catch_rate`` = flagged ∩ must_flag / must_flag
      * ``staleness_false_positive_rate`` = flagged ∩ must_not_flag / must_not_flag
    Abstains (emits nothing) when no staleness spec is present."""
    specs = (probe_spec or {}).get("staleness") or []
    if not specs:
        return {}
    store = (probe_spec or {}).get("store") or {}
    default_scope = store.get("scope")

    must_flag_total = must_flag_caught = 0
    must_not_total = must_not_flagged = 0

    async with httpx.AsyncClient(base_url=_memsvc_base(), timeout=30) as c:
        for entry in specs:
            if not isinstance(entry, dict):
                continue
            scope = entry.get("scope") or default_scope
            payload: dict[str, Any] = {
                "query": entry.get("query") or " ".join(
                    str(x) for x in (entry.get("must_flag") or []) + (entry.get("must_not_flag") or [])
                ) or "schema",
                "k": 20,
                "mode": "L1",
                "scope": scope or {},
            }
            if entry.get("dropped_columns"):
                payload["dropped_columns"] = entry["dropped_columns"]
            if entry.get("repo_files"):
                payload["repo_files"] = entry["repo_files"]

            flagged: dict[str, bool] = {}
            try:
                r = await c.post("/memory/retrieve", headers=_auth_headers(), json=payload)
                if r.status_code == 200 and isinstance(r.json(), dict):
                    for p in r.json().get("passages", []):
                        if isinstance(p, dict) and p.get("memory_id"):
                            flagged[p["memory_id"]] = bool(p.get("stale"))
            except Exception as e:  # noqa: BLE001
                logger.warning("staleness probe retrieve failed: %s", e)

            for mid in entry.get("must_flag") or []:
                must_flag_total += 1
                # A must-flag id absent from retrieval counts as NOT caught (we
                # cannot prove it was flagged) — the strict reading the case wants.
                if flagged.get(mid) is True:
                    must_flag_caught += 1
            for mid in entry.get("must_not_flag") or []:
                must_not_total += 1
                if flagged.get(mid) is True:
                    must_not_flagged += 1

    out: dict[str, Any] = {}
    if must_flag_total:
        out["staleness_catch_rate"] = must_flag_caught / must_flag_total
    if must_not_total:
        out["staleness_false_positive_rate"] = must_not_flagged / must_not_total
    return out


# ───────────────────────── tenant probes ─────────────────────────

async def probe_tenant_isolation(probe_spec: dict[str, Any] | None) -> dict[str, Any]:
    """Probe cross-tenant leakage by querying a sibling scope.

    ``probe_spec.tenant`` carries ``owner_scope``, ``sibling_scope`` and a
    ``forbidden_query``. We list the owner's cards, then run the same query
    under the sibling scope; any owner card surfacing is leakage.
    """
    tenant = (probe_spec or {}).get("tenant") or {}
    if not tenant:
        return {}
    owner = tenant.get("owner_scope")
    sibling = tenant.get("sibling_scope")
    query = tenant.get("forbidden_query") or ""
    out: dict[str, Any] = {}
    async with httpx.AsyncClient(base_url=_memsvc_base(), timeout=30) as c:
        owner_rows = await _list_scope(c, owner)
        # Only *private* owner cards are forbidden cross-tenant. A card the owner
        # deliberately shared (share_with grants the sibling org/repo or "*") is
        # SUPPOSED to surface — counting it as a leak is a false positive. The
        # explicit-share check below asserts the positive side of that contract.
        sib = sibling or {}
        sib_org = sib.get("org_id")
        sib_repo = sib.get("repo_id")

        def _is_shared_to_sibling(m: dict[str, Any]) -> bool:
            sw = m.get("share_with") or []
            if "org:*" in sw or "repo:*" in sw:
                return True
            if sib_org and f"org:{sib_org}" in sw:
                return True
            if sib_repo and f"repo:{sib_repo}" in sw:
                return True
            return False

        private_ids = {m.get("memory_id") for m in owner_rows
                       if m.get("memory_id") and not _is_shared_to_sibling(m)}

        # sibling cross-scope retrieve
        leaked_ids: set[str] = set()
        try:
            r = await c.post(
                "/memory/retrieve",
                headers=_auth_headers(),
                json={"query": query, "k": 10, "mode": "L1", "scope": sibling or {}},
            )
            if r.status_code == 200:
                passages = r.json().get("passages", []) if isinstance(r.json(), dict) else []
                for p in passages:
                    mid = p.get("memory_id") if isinstance(p, dict) else None
                    if mid in private_ids:
                        leaked_ids.add(mid)
        except Exception as e:  # noqa: BLE001
            logger.warning("tenant retrieve probe failed: %s", e)

        n_owner = len(private_ids) or 1
        out["cross_tenant_leakage_rate"] = len(leaked_ids) / n_owner
        out["forbidden_memory_returned"] = len(leaked_ids) > 0

        # enumeration: a cross-scope GET on a *private* owner id must 404, not 403.
        # Probing a shared id would 200 legitimately and falsely flag enumeration.
        probe_id = next(iter(private_ids), None)
        if probe_id:
            try:
                r = await c.get(f"/memory/{probe_id}", headers=_scope_headers(sibling))
                # True == leaked existence via status code (403/200); 404 is correct
                out["tenant_enumeration_via_error_code"] = r.status_code in (200, 403)
            except Exception:  # noqa: BLE001
                out["tenant_enumeration_via_error_code"] = False

        # explicit share: a card the owner marked share_with:["org:*"] MUST
        # surface to the sibling. ``share_probe`` declares the query + a
        # substring expected in a returned passage body.
        share = tenant.get("share_probe")
        if isinstance(share, dict) and share.get("query"):
            want = str(share.get("expect_substring") or "").lower()
            found = False
            try:
                r = await c.post(
                    "/memory/retrieve",
                    headers=_auth_headers(),
                    json={"query": share["query"], "k": 10, "mode": "L1",
                          "scope": sibling or {}},
                )
                if r.status_code == 200 and isinstance(r.json(), dict):
                    for p in r.json().get("passages", []):
                        body = str((p or {}).get("body", "")).lower()
                        if not want or want in body:
                            found = True
                            break
            except Exception as e:  # noqa: BLE001
                logger.warning("share probe failed: %s", e)
            out["explicit_share_respected"] = found
    return out


async def run_all_probes(
    probe_spec: dict[str, Any] | None,
    per_turn_responses: list[str],
    round_series: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Run every applicable probe family and return merged metrics."""
    if not probe_spec:
        return {}
    out: dict[str, Any] = {}
    out.update(compute_text_probes(per_turn_responses, probe_spec))
    try:
        out.update(await probe_memory_store(probe_spec, round_series))
    except Exception as e:  # noqa: BLE001
        logger.warning("store probe family failed: %s", e)
    try:
        out.update(await probe_tenant_isolation(probe_spec))
    except Exception as e:  # noqa: BLE001
        logger.warning("tenant probe family failed: %s", e)
    try:
        out.update(await probe_staleness(probe_spec))
    except Exception as e:  # noqa: BLE001
        logger.warning("staleness probe family failed: %s", e)
    return out


# ───────────────────────── out-of-band seeding ─────────────────────────

async def seed_memory_store(
    ingestion: list[dict[str, Any]] | None,
    default_scope: dict[str, Any] | None,
) -> int:
    """Seed prior-run memory into memsvc OUT-OF-BAND, before the agent runs.

    A case's ``ingestion[]`` is prior-run memory the case author wants present
    before the agent's first turn (e.g. CA-001's migration recipe, GN-004's
    seeded PII). It MUST NOT be written through the agent bridge — doing so
    would hand the case oracle to the system under test (a cheating path).
    Instead the harness writes it directly to the memory service here, exactly
    as the standalone ``evomem-seed`` CLI does.

    Each entry carries a full trajectory plus an authoritative
    ``ground_truth_distillation`` (the seed field — distinct from the agent's
    ``self_distillation``). A per-trajectory ``scope_override`` lets one case
    seed multiple tenants (GN-006: tenant-a / -b / -c); otherwise the case
    scope applies.

    Returns the number of trajectories successfully seeded. Idempotent at the
    memsvc layer: an author-supplied ``memory_id`` that already exists is
    reused, not duplicated, and an erased tombstone is never resurrected.
    """
    if not ingestion:
        return 0
    seeded = 0
    base = _memsvc_base()
    async with httpx.AsyncClient(base_url=base, headers=_auth_headers(), timeout=30) as c:
        for traj in ingestion:
            if not isinstance(traj, dict):
                continue
            traj_scope = traj.get("scope_override") or default_scope or {}
            body: dict[str, Any] = {
                "task": traj.get("task", ""),
                "outcome": traj.get("outcome", "success"),
                "trace_steps": traj.get("trace_steps") or [],
                "scope": traj_scope,
            }
            if traj.get("trajectory_id"):
                body["trajectory_id"] = traj["trajectory_id"]
            # SEED field — authoritative, harness-written. Never self_distillation.
            if traj.get("ground_truth_distillation"):
                body["ground_truth_distillation"] = traj["ground_truth_distillation"]
            try:
                r = await c.post("/memory/distill", json=body)
                r.raise_for_status()
                seeded += 1
            except Exception as e:  # noqa: BLE001
                logger.warning("out-of-band ingestion seed failed: %s", e)
    return seeded
