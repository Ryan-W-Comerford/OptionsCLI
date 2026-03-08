"""
TradeAnalyzer — AI-powered analysis of pending straddle/strangle candidates.

For each pending trade, fetches recent news + market context via Claude's
web search tool, then asks Claude to assess:
  - Likelihood of IV expansion before earnings
  - Catalysts that could drive a big move
  - Risks that could suppress the move
  - Overall signal strength (Strong / Moderate / Weak / Avoid)
"""
from __future__ import annotations

import json
import sqlite3
import urllib.request
import urllib.error


ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
MODEL = "claude-sonnet-4-20250514"

SYSTEM_PROMPT = """You are an expert options trader specializing in pre-earnings volatility strategies.
You analyze straddle and strangle candidates and assess the likelihood of profitable IV expansion.

For each trade you receive you must respond with ONLY a JSON object — no markdown, no preamble, no explanation.
The JSON must follow this exact schema:
{
  "ticker": "AAPL",
  "signal": "Strong" | "Moderate" | "Weak" | "Avoid",
  "confidence": 0-100,
  "summary": "2-3 sentence plain English verdict on the trade",
  "catalysts": ["bullish factor 1", "bullish factor 2"],
  "risks": ["risk factor 1", "risk factor 2"],
  "iv_expansion_likely": true | false,
  "suggested_action": "Enter" | "Monitor" | "Skip"
}"""

USER_PROMPT_TEMPLATE = """Analyze this pre-earnings options trade candidate and assess whether IV is likely to expand profitably before earnings.

TRADE DETAILS:
  Ticker:           {ticker}
  Strategy:         {strategy}
  Earnings Date:    {earnings_date}
  Days to Earnings: {days_to_earnings}
  IV Rank:          {iv_rank:.1f} / 100
  Current IV:       {current_iv:.3f} ({current_iv_pct:.1f}%)
  Call Strike:      ${call_strike}  (delta {call_delta:.2f})
  Put Strike:       ${put_strike}  (delta {put_delta:.2f})
  Est. Entry Cost:  {total_cost}
  Stock at Scan:    ${stock_price_at_scan:.2f}
  Current Price:    {stock_price_current}
  Scanned On:       {scan_date}

Please use your web search tool to research:
1. Recent news and developments for {ticker} in the past 2 weeks
2. Known earnings catalysts — product launches, guidance, analyst sentiment
3. Typical historical earnings move % for {ticker} (how much does it usually move?)
4. Sector headwinds or tailwinds right now
5. Any macro conditions that could affect volatility into this earnings date

Based on all of this, return your JSON analysis."""


def _build_prompt(trade: sqlite3.Row) -> str:
    cost = f"${trade['total_cost']:.2f}" if trade["total_cost"] else "n/a (no bid/ask data on current plan)"
    current = (
        f"${trade['stock_price_current']:.2f} (as of {trade['stock_price_last_sync']})"
        if trade["stock_price_current"]
        else "not yet synced — run 'sync' first"
    )
    current_iv = trade["current_iv"] or 0.0
    return USER_PROMPT_TEMPLATE.format(
        ticker=trade["ticker"],
        strategy=trade["strategy"],
        earnings_date=trade["earnings_date"],
        days_to_earnings=trade["days_to_earnings"] or "unknown",
        iv_rank=trade["iv_rank"] or 0.0,
        current_iv=current_iv,
        current_iv_pct=current_iv * 100,
        call_strike=trade["call_strike"] or "unknown",
        call_delta=trade["call_delta"] or 0.0,
        put_strike=trade["put_strike"] or "unknown",
        put_delta=trade["put_delta"] or 0.0,
        total_cost=cost,
        stock_price_at_scan=trade["stock_price_at_scan"] or 0.0,
        stock_price_current=current,
        scan_date=trade["scan_date"],
    )


def _call_claude(prompt: str) -> dict:
    """
    Call Claude API with web search enabled.
    Claude will search for news/context then return structured JSON analysis.
    """
    payload = json.dumps({
        "model": MODEL,
        "max_tokens": 1500,
        "system": SYSTEM_PROMPT,
        "tools": [{"type": "web_search_20250305", "name": "web_search"}],
        "messages": [{"role": "user", "content": prompt}],
    }).encode("utf-8")

    req = urllib.request.Request(
        ANTHROPIC_API_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=90) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    # Response may contain tool_use + tool_result blocks alongside text — extract text only
    text = " ".join(
        block["text"]
        for block in data.get("content", [])
        if block.get("type") == "text"
    ).strip()

    # Strip any accidental markdown fences Claude might add
    text = text.replace("```json", "").replace("```", "").strip()

    return json.loads(text)


def analyze_pending(pending: list[sqlite3.Row], verbose: bool = True) -> list[dict]:
    """
    Run AI analysis on a list of pending trades.
    Returns list of result dicts — one per trade, including error details if any failed.
    """
    results = []
    for trade in pending:
        ticker = trade["ticker"]
        if verbose:
            print(f"    🔍 Researching {ticker} (earnings {trade['earnings_date']})...", flush=True)
        try:
            prompt = _build_prompt(trade)
            analysis = _call_claude(prompt)
            # Ensure core fields always present
            analysis.setdefault("ticker", ticker)
            analysis.setdefault("earnings_date", trade["earnings_date"])
            analysis.setdefault("days_to_earnings", trade["days_to_earnings"])
            results.append({"status": "ok", **analysis})
        except json.JSONDecodeError as e:
            results.append({
                "status": "parse_error",
                "ticker": ticker,
                "earnings_date": trade["earnings_date"],
                "error": f"Could not parse Claude response as JSON: {e}",
            })
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            results.append({
                "status": "api_error",
                "ticker": ticker,
                "earnings_date": trade["earnings_date"],
                "error": f"HTTP {e.code} {e.reason}: {body[:200]}",
            })
        except Exception as e:
            results.append({
                "status": "error",
                "ticker": ticker,
                "earnings_date": trade["earnings_date"],
                "error": str(e),
            })
    return results