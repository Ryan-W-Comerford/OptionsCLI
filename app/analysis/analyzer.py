"""
TradeAnalyzer — AI-powered analysis of pending straddle/strangle candidates.

Two modes:
  analyze      — Haiku, no web search. Fast, cheap (~$0.0003/ticker, ~10s).
                 Uses Claude's training knowledge. Good for daily quick checks.
  analyze deep — Sonnet + web search. Live news, analyst sentiment, recent filings.
                 (~$0.02/ticker, ~60s). Use before actually entering a trade.
"""
from __future__ import annotations

import json
import sqlite3
import time
import urllib.request
import urllib.error


ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
MODEL_FAST = "claude-haiku-4-5-20251001"
MODEL_DEEP = "claude-sonnet-4-20250514"

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

{research_instruction}

Return your JSON analysis."""

RESEARCH_INSTRUCTION_FAST = """Based on your training knowledge, assess:
1. This company's typical earnings reaction (historical avg move %)
2. Known business model risks and strengths relevant to this earnings
3. Sector conditions and macro factors that affect IV expansion
4. Whether the IV rank and DTE window suggest a good entry"""

RESEARCH_INSTRUCTION_DEEP = """Use your web search tool to research:
1. Recent news and developments for {ticker} in the past 2 weeks
2. Known earnings catalysts — product launches, guidance, analyst sentiment
3. Typical historical earnings move % for {ticker}
4. Sector headwinds or tailwinds right now
5. Any macro conditions that could affect volatility into this earnings date"""


def _build_prompt(trade: sqlite3.Row, deep: bool = False) -> str:
    cost = f"${trade['total_cost']:.2f}" if trade["total_cost"] else "n/a (no bid/ask data on current plan)"
    current = (
        f"${trade['stock_price_current']:.2f} (as of {trade['stock_price_last_sync']})"
        if trade["stock_price_current"]
        else "not yet synced — run 'sync' first"
    )
    current_iv = trade["current_iv"] or 0.0
    research = (
        RESEARCH_INSTRUCTION_DEEP.format(ticker=trade["ticker"])
        if deep
        else RESEARCH_INSTRUCTION_FAST
    )
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
        research_instruction=research,
    )


def _call_claude(prompt: str, deep: bool = False) -> dict:
    """
    Call Claude API.
    deep=False: Haiku, no web search — fast and cheap.
    deep=True:  Sonnet + web search — live research, slower, costs more.
    """
    from app.config.config import config
    api_key = config.ANTHROPIC_API_KEY
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not set in secrets.yaml")

    body = {
        "model":      MODEL_DEEP if deep else MODEL_FAST,
        "max_tokens": 1500 if deep else 1000,
        "system":     SYSTEM_PROMPT,
        "messages":   [{"role": "user", "content": prompt}],
    }
    if deep:
        body["tools"] = [{"type": "web_search_20250305", "name": "web_search"}]

    payload = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        ANTHROPIC_API_URL,
        data=payload,
        headers={
            "Content-Type":      "application/json",
            "anthropic-version": "2023-06-01",
            "x-api-key":         api_key,
        },
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=90) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    text = " ".join(
        block["text"]
        for block in data.get("content", [])
        if block.get("type") == "text"
    ).strip()
    text = text.replace("```json", "").replace("```", "").strip()
    return json.loads(text)


def analyze_pending(
    pending: list[sqlite3.Row],
    verbose: bool = True,
    deep: bool = False,
) -> list[dict]:
    """
    Run AI analysis on a list of pending trades.
    deep=False: fast Haiku analysis (~10s/ticker, ~$0.0003/ticker)
    deep=True:  Sonnet + web search (~60s/ticker, ~$0.02/ticker)
    """
    # Deduplicate by (ticker, earnings_date) — same ticker can appear for straddle + strangle
    seen = set()
    unique_pending = []
    for trade in pending:
        key = (trade["ticker"], trade["earnings_date"])
        if key not in seen:
            seen.add(key)
            unique_pending.append(trade)
    pending = unique_pending

    delay_between = 60 if deep else 10
    delay_initial  = 10 if deep else 3

    results = []
    for trade in pending:
        ticker = trade["ticker"]
        if verbose:
            mode = "deep research" if deep else "quick analysis"
            print(f"    🔍 {ticker} ({mode}, earnings {trade['earnings_date']})...", flush=True)
        time.sleep(delay_between if results else delay_initial)
        try:
            prompt = _build_prompt(trade, deep=deep)
            try:
                analysis = _call_claude(prompt, deep=deep)
            except urllib.error.HTTPError as retry_e:
                if retry_e.code == 429:
                    wait = 90 if deep else 30
                    print(f"    ⏳ Rate limited — waiting {wait}s then retrying {ticker}...", flush=True)
                    time.sleep(wait)
                    analysis = _call_claude(prompt, deep=deep)
                else:
                    raise
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