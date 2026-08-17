"""Advice-demo: proves the human-in-the-loop trade advisor end to end.

Flow: scan adopted indicator strategies -> proposals -> Discord-ready analysis.
Then: approve = real fill, cancel = nothing, no-answer = expire (default NO).

Assumes the real API app with a live IntegratedBot injected (like genuine_full_run).
"""

import json
import pickle
import sys

from fastapi.testclient import TestClient

sys.path.insert(0, ".")
from packages.session.manager import SessionStatus  # noqa: E402
from services.api.main import create_app  # noqa: E402

BARS = pickle.load(open("data/genuine_bars.pkl", "rb"))


def bar_to_dict(b):
    d = b.model_dump()
    d["timestamp"] = b.timestamp.isoformat()
    for k in ("open", "high", "low", "close", "spread"):
        if k in d and d[k] is not None:
            d[k] = float(d[k])
    return d


def main():
    app = create_app()
    import services.api.dependencies as deps

    with TestClient(app) as client:
        bot = deps.get_bot_instance()
        # Paper demo: allow trading regardless of weekday/session.
        bot.loop.session.is_open = lambda dt=None: True
        bot.loop.session.check_session = lambda dt=None: SessionStatus.OPEN

        print("[1] Discord-ready analysis card for a fresh scan")
        scan = client.post("/advice/scan", json={"bars": {s: [bar_to_dict(b) for b in BARS[s]] for s in BARS}})
        body = scan.json()
        print(f"    scan created={body['created']}")
        for p in body["proposals"]:
            print(f"      {p['symbol']:11s} {p['company_name']:22s} {p['strategy']:22s} "
                  f"cur={p['current_price']:8.2f} exp={p['expected_price']:8.2f} "
                  f"ret={p['expected_return_pct']:+.2f}% r/r={p['risk_reward']} conf={p['confidence']}")

        if not body["proposals"]:
            print("    no proposals on this data snapshot (honest) — nothing to demo")
            return 0

        pend = client.get("/advice/proposals?status=pending").json()
        print(f"\n[2] pending proposals: {len(pend)}")

        pid = pend[0]["id"]

        # ── ACCEPT → should genuinely fill via the trading loop ─────────────
        print(f"\n[3] APPROVE {pid}  (should execute a real paper fill)")
        r = client.post(f"/advice/proposals/{pid}/approve").json()
        print(f"    approved={r.get('approved')} status={r.get('status')} "
              f"exec.action={r.get('execution', {}).get('action')} "
              f"exec.side={r.get('execution', {}).get('side')}")
        pf = client.get("/portfolio/summary").json()
        print(f"    portfolio: equity={pf['equity']:.2f} cash={pf['cash']:.2f} "
              f"trades={pf['closed_trades']} open={pf['open_positions']}")
        pos = client.get("/portfolio/positions").json()
        print(f"    positions: {len(pos)}")
        for p in pos:
            print(f"      {p['symbol']} qty={p['quantity']} entry={p['entry_price']} pnl={p['pnl']}")

        # ── CANCEL → nothing executed ─────────────────────────────────────────
        if len(pend) > 1:
            cid = pend[1]["id"]
            r = client.post(f"/advice/proposals/{cid}/cancel").json()
            print(f"\n[4] CANCEL {cid}  -> status={r.get('status')} (must NOT trade)")

        # ── NO-ANSWER → expire (default NO) ───────────────────────────────────
        print("\n[5] default-NO: a never-decided proposal expires and never trades")
        exp = client.post("/advice/reconcile").json()
        st = client.get("/advice/proposals").json()
        status_counts = {}
        for p in st:
            status_counts[p["status"]] = status_counts.get(p["status"], 0) + 1
        print(f"    reconcile expired={exp['expired']} pending={exp['pending']} "
              f"overall={status_counts}")

    return 0


if __name__ == "__main__":
    sys.exit(main())