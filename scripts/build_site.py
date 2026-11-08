#!/usr/bin/env python3
"""Build the public Football Betting Board as one self-contained index.html.

Usage:
    python3 -I scripts/build_site.py <data_dir> <out_html> [--x-handle HANDLE]

<data_dir> holds the five public files the daily task already builds:
    slate.json, nfl_games.json, cfb_games.json, nfl_splits.json, cfb_splits.json
Any missing file is treated as empty. Only these public datasets are used.
"""
import html
import json
import sys
from pathlib import Path

SITE_URL = "https://bcs5056.github.io/football-board-public/"


def load(d: Path, name: str):
    p = d / name
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return []


def e(v) -> str:
    if v is None or v == "":
        return "—"
    return html.escape(str(v))


def num(v):
    return v if isinstance(v, (int, float)) else None


# ---------- splits signals ----------

def split_rows(splits, league):
    """One row per market (spread / total) with money-minus-tickets gap."""
    rows = []
    for s in splits or []:
        m = s.get("matchup", "")
        away, _, home = m.partition(" @ ")
        mk = [
            ("Spread", away + (" (away)" if away else ""), s.get("away_sp_bets"), s.get("away_sp_money")),
            ("Spread", home + (" (home)" if home else ""), s.get("home_sp_bets"), s.get("home_sp_money")),
            ("Total", f"Over {s.get('dk_total') or ''}".strip(), s.get("over_bets"), s.get("over_money")),
            ("Total", f"Under {s.get('dk_total') or ''}".strip(), s.get("under_bets"), s.get("under_money")),
        ]
        for market, side, bets, money in mk:
            bets, money = num(bets), num(money)
            if bets is None or money is None:
                continue
            gap = money - bets
            if gap <= 0:
                continue
            thin = (bets in (0, 100)) or (money in (0, 100))
            rows.append({
                "league": league, "matchup": m, "market": market, "side": side,
                "bets": bets, "money": money, "gap": gap, "thin": thin,
                "dk_line": s.get("dk_line"), "dk_total": s.get("dk_total"),
            })
    return rows


def splits_table(rows):
    if not rows:
        return '<p class="empty">No betting splits were posted this run.</p>'
    rows = sorted(rows, key=lambda r: (r["thin"], -r["gap"]))[:12]
    out = ['<table class="splits"><thead><tr><th>Lg</th><th>Game</th><th>Side</th>'
           '<th>Tickets</th><th>Money</th><th>Gap</th></tr></thead><tbody>']
    for r in rows:
        flag = ' <span class="tag thin" title="Very small sample (100/0)">thin</span>' if r["thin"] else ""
        strong = " strong" if r["gap"] >= 15 and not r["thin"] else ""
        out.append(
            f'<tr class="{strong.strip()}"><td>{e(r["league"])}</td><td>{e(r["matchup"])}</td>'
            f'<td>{e(r["market"])}: {e(r["side"])}{flag}</td>'
            f'<td><div class="bar"><span style="width:{r["bets"]}%"></span></div>{r["bets"]}%</td>'
            f'<td><div class="bar money"><span style="width:{r["money"]}%"></span></div>{r["money"]}%</td>'
            f'<td class="gap">+{r["gap"]}</td></tr>')
    out.append("</tbody></table>")
    out.append('<p class="fine">Gap = share of money minus share of tickets on a side. A big positive gap means '
               'fewer, larger bets (often read as sharper money). Source: DraftKings splits via the board\'s data.</p>')
    return "".join(out)


# ---------- game cards ----------

def splits_by_matchup(splits):
    return {s.get("matchup"): s for s in splits or []}


def mini_splits(s):
    if not s:
        return ""
    parts = []
    if num(s.get("away_sp_bets")) is not None and num(s.get("away_sp_money")) is not None:
        parts.append(f'Spread {e(s.get("dk_line"))}: away {s["away_sp_bets"]}% tix / {s["away_sp_money"]}% $, '
                     f'home {s.get("home_sp_bets")}% / {s.get("home_sp_money")}%')
    if num(s.get("over_bets")) is not None and num(s.get("over_money")) is not None:
        parts.append(f'Total {e(s.get("dk_total"))}: over {s["over_bets"]}% tix / {s["over_money"]}% $')
    if not parts:
        return ""
    return '<div class="ms">' + "<br>".join(parts) + "</div>"


def flags(g):
    out = []
    if g.get("la_flag") == "Y":
        out.append('<span class="tag la" title="Look-ahead spot">look-ahead</span>')
    if g.get("hg_flag") == "Y":
        out.append('<span class="tag hg" title="Hangover / letdown spot">hangover</span>')
    if g.get("ranked") in (True, "Y", "y", 1):
        out.append('<span class="tag rk">ranked</span>')
    wl = (g.get("wx_level") or "")
    if wl and wl not in ("—", "Low", "Dome"):
        out.append(f'<span class="tag wx">weather: {e(wl)}</span>')
    if str(g.get("kickoff", "")).lower().startswith("final"):
        out.append('<span class="tag fin">final</span>')
    return " ".join(out)


def game_card(g, sp):
    m = g.get("matchup") or f'{g.get("away", "")} @ {g.get("home", "")}'
    day = g.get("day") or ""
    detail = []
    for label, key in (("Edge", "edge"), ("Look-ahead", "lookahead"), ("Last game", "hangover"),
                       ("Market", "note"), ("Injuries", "injuries"), ("Letdown", "letdown")):
        v = g.get(key)
        if v and v != "—":
            detail.append(f"<p><b>{label}:</b> {e(v)}</p>")
    analysis = g.get("analysis")
    if analysis and analysis != "—":
        detail.append(f'<p class="an">{e(analysis)}</p>')
    body = "".join(detail)
    search = html.escape(f"{m} {day}".lower())
    return (
        f'<article class="game" data-day="{e(day)}" data-q="{search}">'
        f'<header><h3>{e(m)}</h3><span class="ko">{e(day)} · {e(g.get("kickoff"))}</span></header>'
        f'<div class="nums"><div><small>Line</small><b>{e(g.get("line"))}</b></div>'
        f'<div><small>Total</small><b>{e(g.get("total"))}</b></div>'
        f'<div class="wxc"><small>Weather</small><span>{e(g.get("weather"))}</span></div></div>'
        f'<div class="flags">{flags(g)}</div>'
        f'{mini_splits(sp)}'
        + (f'<details><summary>Breakdown</summary>{body}</details>' if body else "")
        + "</article>"
    )


def board(games, splits, league_id):
    if not games:
        return '<p class="empty">No games on the board this run.</p>'
    sp = splits_by_matchup(splits)
    days = []
    for g in games:
        d = g.get("day")
        if d and d not in days:
            days.append(d)
    chips = ['<button class="chip on" data-day="">All</button>'] + [
        f'<button class="chip" data-day="{e(d)}">{e(d)}</button>' for d in days]
    cards = "".join(game_card(g, sp.get(g.get("matchup"))) for g in games)
    return (f'<div class="tools" data-board="{league_id}">{"".join(chips)}'
            f'<input type="search" placeholder="Find a team…" aria-label="Find a team"></div>'
            f'<div class="grid" id="{league_id}">{cards}</div>')


CSS = """
:root{--bg:#0b1220;--panel:#121b2e;--line:#22304d;--ink:#e8eefb;--mut:#93a3c4;--acc:#38d39f;--acc2:#5aa9ff;--warn:#ffb547;--bad:#ff6b6b}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
a{color:var(--acc2)}
.wrap{max-width:1180px;margin:0 auto;padding:20px 16px 60px}
.top{display:flex;flex-wrap:wrap;gap:12px;align-items:flex-end;justify-content:space-between;border-bottom:1px solid var(--line);padding-bottom:14px}
h1{margin:0;font-size:28px;letter-spacing:-.02em}h1 span{color:var(--acc)}
.meta{color:var(--mut);font-size:13px}
h2{font-size:19px;margin:34px 0 12px;display:flex;gap:10px;align-items:baseline}h2 small{color:var(--mut);font-weight:400;font-size:13px}
.reads{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:12px;margin-top:18px}
.read{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:14px 16px}
.read h4{margin:0 0 6px;font-size:12px;text-transform:uppercase;letter-spacing:.08em;color:var(--acc)}
.read p{margin:0}
table.splits{width:100%;border-collapse:collapse;background:var(--panel);border:1px solid var(--line);border-radius:12px;overflow:hidden;font-size:14px}
.splits th,.splits td{padding:8px 10px;border-bottom:1px solid var(--line);text-align:left;vertical-align:middle}
.splits th{color:var(--mut);font-weight:500;font-size:12px;text-transform:uppercase;letter-spacing:.06em}
.splits tr.strong td{background:rgba(56,211,159,.07)}
.splits td.gap{color:var(--acc);font-weight:700}
.bar{display:inline-block;width:60px;height:6px;background:#1d2a45;border-radius:3px;margin-right:6px;vertical-align:middle}
.bar span{display:block;height:100%;background:var(--mut);border-radius:3px}.bar.money span{background:var(--acc)}
.tableWrap{overflow-x:auto}
.tools{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:12px;align-items:center}
.chip{background:var(--panel);color:var(--ink);border:1px solid var(--line);border-radius:999px;padding:5px 12px;cursor:pointer;font:inherit;font-size:13px}
.chip.on{background:var(--acc);color:#06281c;border-color:var(--acc);font-weight:600}
.tools input{margin-left:auto;background:var(--panel);border:1px solid var(--line);color:var(--ink);border-radius:8px;padding:6px 10px;font:inherit;min-width:200px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(330px,1fr));gap:12px;align-items:start}
.game{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:14px}
.game header{display:flex;justify-content:space-between;gap:8px;align-items:baseline}
.game h3{margin:0;font-size:16px}.ko{color:var(--mut);font-size:12px;white-space:nowrap}
.nums{display:grid;grid-template-columns:auto auto 1fr;gap:14px;margin:10px 0 6px}
.nums small{display:block;color:var(--mut);font-size:11px;text-transform:uppercase;letter-spacing:.06em}
.nums b{font-size:17px}.wxc span{font-size:12.5px;color:var(--mut)}
.flags{display:flex;flex-wrap:wrap;gap:6px;min-height:4px}
.tag{font-size:11px;padding:2px 8px;border-radius:999px;border:1px solid var(--line);color:var(--mut)}
.tag.la{color:var(--warn);border-color:rgba(255,181,71,.4)}.tag.hg{color:var(--bad);border-color:rgba(255,107,107,.4)}
.tag.rk{color:var(--acc2);border-color:rgba(90,169,255,.4)}.tag.wx{color:var(--warn)}.tag.fin{color:var(--ink)}.tag.thin{font-size:10px}
.ms{font-size:12.5px;color:var(--mut);margin-top:8px;border-top:1px dashed var(--line);padding-top:8px}
details{margin-top:8px}summary{cursor:pointer;color:var(--acc2);font-size:13px}
details p{margin:6px 0;font-size:13.5px}details .an{color:var(--ink)}
.empty{color:var(--mut)}.fine{color:var(--mut);font-size:12px;margin:8px 2px}
footer{margin-top:40px;border-top:1px solid var(--line);padding-top:14px;color:var(--mut);font-size:12.5px}
.hide{display:none!important}
@media (max-width:560px){h1{font-size:22px}.tools input{margin-left:0;width:100%}.grid{grid-template-columns:1fr}}
"""

JS = """
document.querySelectorAll('.tools').forEach(function(t){
  var grid=document.getElementById(t.dataset.board), day='', q='';
  function apply(){grid.querySelectorAll('.game').forEach(function(c){
    var ok=(!day||c.dataset.day===day)&&(!q||c.dataset.q.indexOf(q)>-1);
    c.classList.toggle('hide',!ok);});}
  t.querySelectorAll('.chip').forEach(function(b){b.addEventListener('click',function(){
    t.querySelectorAll('.chip').forEach(function(x){x.classList.remove('on')});
    b.classList.add('on');day=b.dataset.day;apply();});});
  var i=t.querySelector('input');i.addEventListener('input',function(){q=i.value.trim().toLowerCase();apply();});
});
"""


def build(data_dir: Path, out: Path, x_handle: str = ""):
    slate_l = load(data_dir, "slate.json")
    slate = slate_l[0] if isinstance(slate_l, list) and slate_l else (slate_l if isinstance(slate_l, dict) else {})
    nfl = load(data_dir, "nfl_games.json")
    cfb = load(data_dir, "cfb_games.json")
    nsp = load(data_dir, "nfl_splits.json")
    csp = load(data_dir, "cfb_splits.json")

    title = "Football Betting Board"
    desc = slate.get("takeaway") or "Daily NFL and college football lines, betting splits and game breakdowns."
    nfl_wk = f'{slate.get("nfl_week", "")} · {slate.get("nfl_dates", "")}'.strip(" ·")
    cfb_wk = f'{slate.get("cfb_week", "")} · {slate.get("cfb_dates", "")}'.strip(" ·")
    byes = slate.get("nfl_byes")
    follow = (f' · Daily picks on <a href="https://x.com/{html.escape(x_handle)}">@{html.escape(x_handle)}</a>'
              if x_handle else "")

    reads = []
    for label, key in (("The day's read", "takeaway"), ("NFL", "nfl_takeaway"), ("College", "cfb_takeaway")):
        if slate.get(key):
            reads.append(f'<div class="read"><h4>{label}</h4><p>{e(slate[key])}</p></div>')

    rows = split_rows(nsp, "NFL") + split_rows(csp, "CFB")

    page = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} — {e(slate.get("nfl_week"))} NFL · {e(slate.get("cfb_week"))} CFB</title>
<meta name="description" content="{e(desc)}">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:type" content="website">
<meta property="og:url" content="{SITE_URL}">
<meta property="og:image" content="{SITE_URL}post/card.png">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:image" content="{SITE_URL}post/card.png">
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>🏈</text></svg>">
<style>{CSS}</style></head>
<body><div class="wrap">
<div class="top"><div><h1>Football <span>Betting</span> Board</h1>
<div class="meta">Updated {e(slate.get("as_of"))}{follow}</div></div>
<div class="meta">NFL {e(nfl_wk)}{(" · Byes: " + e(byes)) if byes else ""}<br>College {e(cfb_wk)}</div></div>
<div class="reads">{"".join(reads)}</div>

<h2>Sharp vs. public <small>biggest money-over-tickets gaps</small></h2>
<div class="tableWrap">{splits_table(rows)}</div>

<h2>NFL game board <small>{len(nfl)} games · {len(nsp)} with splits</small></h2>
{board(nfl, nsp, "nflgrid")}

<h2>College game board <small>{len(cfb)} games · {len(csp)} with splits</small></h2>
{board(cfb, csp, "cfbgrid")}

<footer>Informational research for entertainment only — not betting advice. Lines move; check your sportsbook.
Must be 21+ (18+ where permitted). Gambling problem? Call 1-800-GAMBLER.
Data compiled daily from public sources including DraftKings (via Cleatz), ESPN, CBS Sports, VegasInsider and the National Weather Service.</footer>
</div><script>{JS}</script></body></html>
"""
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    return {"nfl_games": len(nfl), "cfb_games": len(cfb), "nfl_splits": len(nsp),
            "cfb_splits": len(csp), "bytes": len(page.encode())}


if __name__ == "__main__":
    args = sys.argv[1:]
    handle = ""
    if "--x-handle" in args:
        i = args.index("--x-handle")
        handle = args[i + 1].lstrip("@")
        del args[i:i + 2]
    if len(args) != 2:
        sys.exit(__doc__)
    print(json.dumps(build(Path(args[0]), Path(args[1]), handle)))
