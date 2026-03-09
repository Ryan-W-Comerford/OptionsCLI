"""
EventScanner — Claude-powered discovery of upcoming market-moving events.

Uses Claude + web search to find dated upcoming events (legislation votes,
FDA decisions, Fed meetings, product launches, geopolitical flashpoints, etc.)
that could cause IV spikes in specific stocks. Returns a list of EventCandidate
objects that are then passed to the existing straddle/strangle scanner to find
exact option contracts.

This is the non-earnings equivalent of the pre-earnings IV expansion strategy —
same thesis (buy before IV spikes, sell at peak) but driven by macro/event
catalysts rather than fixed earnings dates.
"""
from __future__ import annotations

import json
import urllib.request
import urllib.error
from dataclasses import dataclass
from datetime import date, datetime


ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
MODEL = "claude-haiku-4-5-20251001"  # Haiku — web search works on Haiku at much lower token cost

SYSTEM_PROMPT = """You are an expert options trader and market analyst.
Your job is to identify upcoming market-moving events with specific known dates that could cause
IV spikes in specific US-listed stocks or ETFs.

You must respond with ONLY a JSON array — no markdown, no preamble, no explanation.
Each element must follow this exact schema:
{
  "event": "Short event name (e.g. 'Senate IRA vote', 'FDA PDUFA date for MRNA', 'Fed rate decision')",
  "event_date": "YYYY-MM-DD",
  "confidence_in_date": "high" | "medium" | "low",
  "tickers": ["TICK1", "TICK2"],
  "thesis": "1-2 sentences on why this event causes IV expansion in these specific tickers",
  "sector": "energy | tech | biotech | financials | defense | consumer | macro | other",
  "expected_move_pct": 5
}

Rules:
- Only include events with a SPECIFIC known date within the next 60 days
- Only include US-listed stocks and ETFs with liquid options (OI > 500)
- Do not include events that have already happened
- Do not include earnings — those are handled separately
- Rank by expected IV impact (highest first)
- Return between 3 and 10 events maximum"""

USER_PROMPT = """Today is {today}. Use your web search tool to find upcoming market-moving events
in the next 60 days that could cause significant IV spikes in specific stocks.

Only suggest tickers from this list (these are the only ones with options data available):
{watchlist}

Search for:
1. Scheduled Congressional votes or bill signings affecting specific sectors (energy, defense, tech, pharma)
2. FDA PDUFA dates and drug approval decisions
3. Federal Reserve meeting dates and rate decisions
4. Major product launches or investor days with specific dates
5. Scheduled geopolitical events (sanctions votes, treaty signings, OPEC meetings)
6. Regulatory decisions (FTC/DOJ antitrust rulings, SEC rule changes)
7. Major economic data releases that move specific sectors (CPI, jobs report, etc.)
8. Known legal/litigation outcomes with scheduled dates

For each event found, identify the specific US-listed stocks most likely to see IV expansion.
Focus on events where the outcome is uncertain — binary events create the most IV expansion.

IMPORTANT: Your final message must be ONLY the raw JSON array starting with [ and ending with ].
No introduction, no explanation, no markdown fences. Just the JSON array."""


@dataclass
class EventCandidate:
    event: str
    event_date: date
    confidence_in_date: str
    tickers: list[str]
    thesis: str
    sector: str
    expected_move_pct: float


def _do_request(body: dict, api_key: str) -> dict:
    """Make a single API request and return parsed JSON response."""
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
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _call_claude(today: date) -> list[dict]:
    """
    Call Claude with server-side web search.
    Anthropic's web search is a server_tool — results come back inline in a
    single response alongside text blocks. No multi-turn loop needed.
    We grab the LAST text block which contains the final JSON answer.
    """
    from app.config.config import config
    api_key = config.ANTHROPIC_API_KEY
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not set in secrets.yaml")

    body = {
        "model":      MODEL,
        "max_tokens": 4000,
        "system":     SYSTEM_PROMPT,
        "tools":      [{"type": "web_search_20250305", "name": "web_search", "max_uses": 3}],
        "messages":   [{"role": "user", "content": USER_PROMPT.format(today=str(today), watchlist=", ".join(sorted(config.STOCKS)))}],
    }

    data = _do_request(body, api_key)

    # Extract all text blocks — the last one contains the final JSON
    text_blocks = [
        block["text"].strip()
        for block in data.get("content", [])
        if block.get("type") == "text" and block.get("text", "").strip()
    ]

    if not text_blocks:
        raise ValueError(f"No text in response. Block types: {[b.get('type') for b in data.get('content', [])]}")

    # Search all text blocks for a JSON array — extract from [ to ] even if surrounded by prose
    import re
    all_text = " ".join(text_blocks)
    match = re.search(r'\[.*\]', all_text, re.DOTALL)
    if match:
        return json.loads(match.group(0))

    # Fallback: try each block cleaned
    for tb in reversed(text_blocks):
        cleaned = tb.replace("```json", "").replace("```", "").strip()
        if cleaned.startswith("["):
            return json.loads(cleaned)

    raise ValueError(f"No JSON array found. Blocks: {[repr(t[:150]) for t in text_blocks]}")


def discover_events(verbose: bool = True) -> list[EventCandidate]:
    """
    Use Claude + web search to discover upcoming market-moving events.
    Returns a list of EventCandidate objects sorted by event_date.
    """
    today = date.today()
    if verbose:
        print(f"    🌐 Searching for upcoming market events (next 60 days)...", flush=True)

    raw = _call_claude(today)

    candidates = []
    for item in raw:
        try:
            edate = datetime.strptime(item["event_date"], "%Y-%m-%d").date()
            if edate < today:
                continue  # skip past events
            candidates.append(EventCandidate(
                event=item["event"],
                event_date=edate,
                confidence_in_date=item.get("confidence_in_date", "medium"),
                tickers=item.get("tickers", []),
                thesis=item.get("thesis", ""),
                sector=item.get("sector", "other"),
                expected_move_pct=float(item.get("expected_move_pct", 5)),
            ))
        except (KeyError, ValueError):
            continue

    candidates.sort(key=lambda c: c.event_date)
    return candidates