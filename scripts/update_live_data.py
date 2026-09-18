#!/usr/bin/env python3
"""Refresh deploy-safe market data for the static GitHub Pages app.

Yahoo Finance does not consistently allow browser requests from github.io.
This script runs in GitHub Actions, writes data/live.json, and lets the UI
use same-origin cached live data while still attempting a browser refresh.
"""
from __future__ import annotations

import json
import subprocess
import tempfile
import time
import urllib.parse
from datetime import datetime, timezone
from typing import Any
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = json.loads((ROOT / "data/snapshot.json").read_text(encoding="utf-8"))
CG_IDS = json.loads((ROOT / "data/cg_idmap.json").read_text(encoding="utf-8"))
OUT = ROOT / "data/live.json"
UA = "Mozilla/5.0"


def get_json(url: str, retries: int = 3) -> Any:
    last: Exception | None = None
    for attempt in range(retries):
        try:
            with tempfile.NamedTemporaryFile(suffix=".json") as tmp:
                subprocess.run(
                    [
                        "curl", "--fail", "--silent", "--show-error", "--location",
                        "--max-time", "30", "--header", f"User-Agent: {UA}",
                        "--header", "Accept: application/json", "--output", tmp.name, url,
                    ],
                    check=True,
                )
                tmp.seek(0)
                return json.load(tmp)
        except Exception as exc:  # network/provider errors are retried and surfaced
            last = exc
            if attempt + 1 < retries:
                time.sleep(1.2 * (attempt + 1))
    raise RuntimeError(f"request failed after {retries} attempts: {last}")


def yahoo_batch(symbols: list[str]) -> dict[str, dict]:
    encoded = urllib.parse.quote(",".join(symbols), safe=",")
    url = f"https://query2.finance.yahoo.com/v7/finance/spark?symbols={encoded}&range=1y&interval=1mo"
    payload = get_json(url)
    values: dict[str, dict] = {}
    for item in payload.get("spark", {}).get("result", []):
        symbol = item.get("symbol")
        responses = item.get("response") or []
        if not symbol or not responses:
            continue
        result = responses[0]
        meta = result.get("meta", {})
        closes = [
            v
            for v in result.get("indicators", {}).get("quote", [{}])[0].get("close", [])
            if v is not None
        ]
        price = meta.get("regularMarketPrice")
        change_52w = ((price / closes[0]) - 1) * 100 if price is not None and closes else None
        values[symbol] = {
            "price": price,
            "chgDay": meta.get("regularMarketChangePercent"),
            "chg52w": change_52w,
            "hi52": meta.get("fiftyTwoWeekHigh"),
            "lo52": meta.get("fiftyTwoWeekLow"),
            "cur": meta.get("currency"),
        }
    return values


def refresh_yahoo(symbols: list[str]) -> tuple[dict, list[str]]:
    values: dict[str, dict] = {}
    errors: list[str] = []
    # Keep URLs short and isolate bad/delisted symbols: 10 per request.
    batch_size = 10
    for start in range(0, len(symbols), batch_size):
        chunk = symbols[start : start + batch_size]
        try:
            values.update(yahoo_batch(chunk))
        except Exception as exc:
            errors.append(f"batch {start // batch_size + 1}: {exc}")
            # A single bad ticker can make Yahoo reject the whole batch.
            for symbol in chunk:
                try:
                    values.update(yahoo_batch([symbol]))
                except Exception as symbol_exc:
                    errors.append(f"{symbol}: {symbol_exc}")
                time.sleep(0.15)
        if start + batch_size < len(symbols):
            time.sleep(0.5)
    missing = sorted(set(symbols) - set(values))
    if missing:
        errors.append("missing: " + ", ".join(missing))
    return values, errors


def refresh_crypto() -> dict:
    ids = ",".join(CG_IDS.values())
    url = (
        "https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&ids="
        + urllib.parse.quote(ids, safe=",")
        + "&price_change_percentage=24h,7d,30d"
    )
    rows = get_json(url)
    return {
        row["symbol"].upper(): {
            "price": row.get("current_price"),
            "chg24h": row.get("price_change_percentage_24h_in_currency"),
            "chg7d": row.get("price_change_percentage_7d_in_currency"),
            "chg30d": row.get("price_change_percentage_30d_in_currency"),
            "volmcap": (row.get("total_volume") / row.get("market_cap") * 100)
            if row.get("total_volume") and row.get("market_cap")
            else None,
            "fromath": row.get("ath_change_percentage"),
            "mcapRank": row.get("market_cap_rank"),
        }
        for row in rows
    }


def main() -> None:
    previous = {}
    if OUT.exists():
        try:
            previous = json.loads(OUT.read_text(encoding="utf-8"))
        except Exception:
            previous = {}

    thai_symbols = [row["ticker"] for row in SNAPSHOT["thai"]]
    us_symbols = [row["ticker"] for row in SNAPSHOT["us"]]
    thai, thai_errors = refresh_yahoo(thai_symbols)
    us, us_errors = refresh_yahoo(us_symbols)

    crypto_errors: list[str] = []
    try:
        crypto = refresh_crypto()
    except Exception as exc:
        crypto = previous.get("crypto", {})
        crypto_errors.append(str(exc))

    # Keep the last known value if one provider symbol temporarily fails.
    thai = {**previous.get("thai", {}), **thai}
    us = {**previous.get("us", {}), **us}

    expected = {"thai": len(thai_symbols), "us": len(us_symbols), "crypto": len(SNAPSHOT["crypto"])}
    actual = {"thai": len(thai), "us": len(us), "crypto": len(crypto)}
    errors = thai_errors + us_errors + crypto_errors
    if any(actual[key] < expected[key] for key in expected):
        raise RuntimeError(f"incomplete live dataset: actual={actual}, expected={expected}; errors={errors[:5]}")

    data = {
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "source": "Yahoo Finance + CoinGecko",
        "thai": thai,
        "us": us,
        "crypto": crypto,
    }
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"updated_at": data["updated_at"], "counts": actual, "transient_errors": len(errors)}))


if __name__ == "__main__":
    main()
