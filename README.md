# Trading Dashboards

Auto-updating stock/crypto screener dashboards, published as a static site via GitHub Pages.

**Live site:** https://littlekop.github.io/trading-dashboards/

## What this is

Three independent screeners scan for candidates where price has lagged behind fundamentals:

| Market | What "fundamentals" means here |
|---|---|
| 🇹🇭 Thai stocks | Real earnings + revenue growth (trailing 12 months), price flat/lagging |
| 🇺🇸 US stocks | Same idea, higher market-cap floor given the size of the US market |
| ₿ Crypto | No earnings exist for crypto, so this uses 30-day market cap growth and volume/market-cap ratio as proxies instead |

Each dashboard also tracks a **track record**: every candidate that ever qualified is
followed forward from its entry price, so the site shows real win rate / average return
over time — not just "here's today's snapshot."

## This is a screening shortlist, not investment advice

None of this is a recommendation to buy or sell anything. It surfaces candidates that
match a mechanical rule set; every one still needs real due diligence (financial
statements, governance, liquidity, debt) before anyone acts on it. Data comes from
Yahoo Finance and CoinGecko's free tiers, not an institutional-grade source.

## How it updates

A Windows machine runs the screeners daily (~08:00–08:35 local time) via Task
Scheduler, fully independent of any AI assistant:

```
ThaiStockScreener → USStockScreener → CryptoScreener → CombinedDashboard
```

The last step copies the freshest HTML into this repo and pushes automatically, which
is what keeps this site current. Source code lives in a separate private project (not
this repo) — this repo only holds the published output.

## Files

- `index.html` — the combined dashboard (tabs: Thai / US / Crypto)
- `thai_screener_dashboard.html`, `us_screener_dashboard.html`, `crypto_screener_dashboard.html` — the individual dashboards, also reachable directly
