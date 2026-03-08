from app.models.models import StraddleCandidate


class Colors:
    """ANSI color codes for terminal output."""
    RESET  = "\033[0m"
    BOLD   = "\033[1m"
    DIM    = "\033[2m"
    RED    = "\033[91m"
    GREEN  = "\033[92m"
    YELLOW = "\033[93m"
    BLUE   = "\033[94m"
    CYAN   = "\033[96m"
    WHITE  = "\033[97m"


C = Colors


def _iv_rank_color(iv_rank: float) -> str:
    if iv_rank >= 65:
        return C.GREEN
    if iv_rank >= 45:
        return C.YELLOW
    return C.RED


def _ratio_color(ratio: float) -> str:
    if ratio >= 6:
        return C.GREEN
    if ratio >= 4:
        return C.YELLOW
    return C.RED


def print_candidates(candidates: list[StraddleCandidate]) -> None:
    if not candidates:
        print(f"\n{C.YELLOW}  No candidates found matching the strategy criteria.{C.RESET}\n")
        return

    sorted_candidates = sorted(candidates, key=lambda c: c.iv_rank, reverse=True)

    print(f"\n{C.BOLD}{C.CYAN}  CANDIDATES{C.RESET}  {C.DIM}({len(sorted_candidates)} found, sorted by IV Rank){C.RESET}")
    print(f"  {C.CYAN}{'═' * 58}{C.RESET}")

    for c in sorted_candidates:
        ivr_color   = _iv_rank_color(c.iv_rank)
        ratio_color = _ratio_color(c.vega_theta_ratio)

        print(f"  {C.BOLD}{C.WHITE}{c.ticker}{C.RESET}")
        print(
            f"    Earnings    {C.BOLD}{c.earnings_date}{C.RESET}"
            f"  {C.DIM}({c.days_to_earnings}d away){C.RESET}"
        )
        cost_str = f"${c.total_cost:.2f}" if c.total_cost > 0 else f"{C.DIM}n/a{C.RESET}"
        print(
            f"    IV Rank     {ivr_color}{C.BOLD}{c.iv_rank:.1f}{C.RESET}"
            f"    Vega/Theta  {ratio_color}{C.BOLD}{c.vega_theta_ratio:.2f}x{C.RESET}"
            f"    Est. Cost   {C.BOLD}{cost_str}{C.RESET}"
        )
        print(
            f"    {C.GREEN}CALL{C.RESET}  {c.call.symbol:<28}"
            f"  Δ {c.call.delta:+.2f}  Θ {c.call.theta:.3f}"
            f"  V {c.call.vega:.3f}  OI {c.call.open_interest:,}"
        )
        print(
            f"    {C.RED}PUT{C.RESET}   {c.put.symbol:<28}"
            f"  Δ {c.put.delta:+.2f}  Θ {c.put.theta:.3f}"
            f"  V {c.put.vega:.3f}  OI {c.put.open_interest:,}"
        )
        print(f"  {C.DIM}  {'─' * 56}{C.RESET}")

    print()


def print_history(trades: list, stats: dict) -> None:
    C2 = Colors
    print(f"\n{C2.BOLD}{C2.CYAN}  TRADE HISTORY{C2.RESET}  {C2.DIM}({stats['total']} total){C2.RESET}")
    print(f"  {C2.CYAN}{'═' * 70}{C2.RESET}")

    status_icon = {
        "pending":        f"{C2.YELLOW}⏳ pending{C2.RESET}",
        "resolved_win":   f"{C2.GREEN}✅ win{C2.RESET}",
        "resolved_loss":  f"{C2.RED}❌ loss{C2.RESET}",
        "unresolvable":   f"{C2.DIM}❓ unresolvable{C2.RESET}",
        "expired":        f"{C2.DIM}💀 expired{C2.RESET}",
    }

    for t in trades:
        icon = status_icon.get(t["status"], t["status"])
        move = f"{t['actual_move_pct']:.1f}%" if t["actual_move_pct"] is not None else "—"
        be   = f"{t['breakeven_pct']:.1f}%" if t["breakeven_pct"] is not None else "—"
        pnl  = f"{t['pnl_estimate']:+.1f}%" if t["pnl_estimate"] is not None else "—"
        cost = f"${t['total_cost']:.2f}" if t["total_cost"] else "n/a"

        print(
            f"  {C2.BOLD}{t['ticker']:<6}{C2.RESET} "
            f"{C2.DIM}{t['earnings_date']}{C2.RESET}  "
            f"IV {t['iv_rank']:.0f}  "
            f"cost={cost}  move={move}  be={be}  pnl={pnl}  {icon}"
        )
        if t["notes"]:
            print(f"         {C2.DIM}{t['notes']}{C2.RESET}")

    # Stats summary
    wins   = stats["wins"] or 0
    losses = stats["losses"] or 0
    total_resolved = wins + losses
    win_rate = (wins / total_resolved * 100) if total_resolved else 0

    print(f"\n  {C2.DIM}{'─' * 70}{C2.RESET}")
    print(f"  {C2.BOLD}Summary{C2.RESET}  "
          f"pending={stats['pending']}  "
          f"wins={C2.GREEN}{wins}{C2.RESET}  "
          f"losses={C2.RED}{losses}{C2.RESET}  "
          f"win_rate={C2.BOLD}{win_rate:.0f}%{C2.RESET}  "
          f"avg_pnl={stats['avg_pnl']:.1f}%" if stats['avg_pnl'] else
          f"  {C2.BOLD}Summary{C2.RESET}  pending={stats['pending']}  wins={C2.GREEN}{wins}{C2.RESET}  losses={C2.RED}{losses}{C2.RESET}  win_rate={C2.BOLD}{win_rate:.0f}%{C2.RESET}")
    print()