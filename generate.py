#!/usr/bin/env python3
"""
Generate a clean, editorial "system dossier" GitHub profile.

Aesthetic: monospace, soft greys, hairline rules, ghosted section numerals and
restrained CSS-keyframe motion (respecting prefers-reduced-motion). No boxes —
hierarchy comes from type, spacing and rules. Inspired by the layout language of
github.com/Sharann-del, rebuilt from scratch with F3NN3X's own data.

Emits paired light/dark SVGs into assets/ + assets/dark/, a README.md that swaps
them with <picture>, and a self-contained preview.html. Pure stdlib.

Contribution counts are fetched live when a token with `read:user` is present
(GH_TOKEN / GITHUB_TOKEN) and floored to known-good values otherwise.

Run:  python generate.py
"""
from __future__ import annotations
import base64
import html
import json
import os
import urllib.request
from datetime import datetime, timezone

W = 1000              # canvas width
M, R = 48, 952        # left / right gutters
MONO = ("ui-monospace, 'SFMono-Regular', 'SF Mono', Menlo, 'Cascadia Code', "
        "Consolas, 'Liberation Mono', monospace")
CW = 0.60             # monospace advance ≈ 0.60em (layout math)

LIGHT = dict(bone="#333333", muted="#8a8a8a", dim="#b0b0b0", rule="#d3d3d3",
             accent="#555555", ghost="#dedede", amber="#b07d20")
DARK  = dict(bone="#dddddd", muted="#7a7a7a", dim="#5f5f5f", rule="#3a3a3a",
             accent="#aaaaaa", ghost="#242424", amber="#d6a54e")

# ---------------------------------------------------------------- content ----
NAME     = "F3NN3X"
ROLE     = "Full-Stack Developer · InfoPanel Plugin Author — Norway"
FOCUS    = "C# / .NET desktop telemetry · TypeScript web platforms · dev tooling & design systems"
STATUS   = "shipping — the InfoPanel ecosystem · centr · rekyndo · relentless side quests"
TAGS     = ["C# / .NET", "FULL-STACK WEB", "DEV TOOLING"]

WHOAMI = [
    ("Full-stack developer from Norway — building across the whole stack.", "bone", 16),
    ("InfoPanel plugins in C# / .NET. Web platforms in TypeScript, Next.js & Laravel.", "bone", 16),
    ("Drawn to systems telemetry and clean tooling — dashboards one day, SaaS the next.", "muted", 15),
]
WHOAMI_ROWS = [
    ("FOCUS",  "Desktop telemetry · Full-Stack Web · Dev Tooling · Design Systems", "bone"),
    ("STATUS", "shipping — InfoPanel ecosystem · centr · rekyndo", "accent"),
    ("STACK",  "C# · TypeScript · PHP · Python · Rust", "bone"),
]

# project channels: (title, [copy lines], tech meta, stars)
PROJECTS = [
    ("INFOPANEL.FPS",
     ["Real-time FPS and frametime metrics via Intel PresentMon, rendered live on an InfoPanel hardware dashboard.",
      "The most-used plugin in the whole suite."],
     "C# · .NET · PRESENTMON · WPF", 11),
    ("INFOPANEL.MEDIA",
     ["Universal now-playing tracking across Spotify, browsers, VLC and any Windows media source.",
      "One plugin, every player — title, artist, album art and progress."],
     "C# · .NET · WINDOWS MEDIA API · GDI", 1),
    ("INFOPANEL.SPOTIFY",
     ["Live Spotify track, artist and album art surfaced straight onto the panel.",
      "The plugin that started the media line."],
     "C# · .NET · SPOTIFY API · OAUTH", 4),
    ("INFOPANEL.RTSS",
     ["Frame metrics sourced from RivaTuner Statistics Server for overlay-accurate numbers.",
      "Cross-checks the PresentMon path for confidence."],
     "C# · .NET · RTSS · SHARED MEMORY", 3),
    ("INFOPANEL.STEAMAPI",
     ["Live Steam activity, session stats, friends and library data on the dashboard.",
      "Gaming presence without alt-tabbing."],
     "C# · .NET · STEAM WEB API", 1),
    ("INFOPANEL.METYR",
     ["Norwegian Met/YR weather with no API key and no signup — location in, forecast out.",
      "Built for home, works anywhere YR reaches."],
     "C# · .NET · MET.NO API", 0),
]

STACK = [
    ("LANGUAGES",  "TypeScript · JavaScript · C# · PHP · Python · Rust · Go · Swift"),
    ("FRAMEWORKS", "Next.js · React · Laravel · Astro · SvelteKit · .NET"),
    ("STYLING",    "Tailwind · SCSS · CSS"),
    ("DATA",       "PostgreSQL · SQLite · Supabase"),
    ("INFRA",      "Docker · Git · GitHub Actions · Vite"),
]

# system map — core + clustered nodes. (name, sub)
ECO_CORE = ("F3NN3X.SYS", "one-person build pipeline")
ECO_LEFT = [  # DESKTOP TELEMETRY
    ("InfoPanel.FPS", "FPS · frametime · 11★"),
    ("InfoPanel.Media", "Spotify · VLC · browsers"),
    ("InfoPanel.RTSS", "RivaTuner metrics"),
    ("InfoPanel ×14", ".NET plugin suite"),
]
ECO_RIGHT = [  # WEB PLATFORMS
    ("centr", "platform · TypeScript"),
    ("rekyndo", "SaaS · Next.js"),
    ("smelta", "Laravel · PHP"),
    ("themely", "design system"),
]
ECO_BOTTOM = [  # DEV TOOLING
    ("stack templates ×8", "Next · Astro · Go · Rust"),
    ("outline-sync", "docs → Outline"),
    ("dotfiles · CI", "workflows"),
]

# telemetry counters
COUNTERS = [("66", "REPOSITORIES"), ("14", "INFOPANEL PLUGINS"),
            ("32", "STARS EARNED"), ("29", "LANGUAGES TOUCHED")]

# real language byte counts across owned repos (gh api .../languages, summed)
LANG_BYTES = {
    "TypeScript": 51096180, "JavaScript": 7477737, "C#": 4613271, "PHP": 3691395,
    "Blade": 3244387, "HTML": 2811557, "PL/pgSQL": 2524924, "CSS": 1656625,
    "MDX": 1639189, "Kotlin": 648640, "Shell": 635937, "Python": 606641,
    "Swift": 471956, "SCSS": 106549, "C++": 96570, "PowerShell": 86678,
    "misc": 52742 + 36612 + 30727 + 7659 + 3758 + 3172 + 2352 + 1981 + 1354,
}

# ------------------------------------------------------ dynamic contributions -
FALLBACK_CONTRIB = {2025: 1246, 2026: 6538}   # real profile totals (mostly private)
MILESTONES = {
    2025: ("InfoPanel plugin surge", "NuttySpotifyMeld → the plugin suite · web platforms begin"),
    2026: ("Media · Spotify · MetYr", "centr & rekyndo build-out · dev tooling"),
}

def _fetch_year(year: int, token: str) -> int | None:
    q = ("query($f:DateTime!,$t:DateTime!){viewer{contributionsCollection(from:$f,to:$t)"
         "{contributionCalendar{totalContributions}}}}")
    payload = json.dumps({"query": q, "variables": {
        "f": f"{year}-01-01T00:00:00Z", "t": f"{year}-12-31T23:59:59Z"}}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql", data=payload,
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json",
                 "User-Agent": "f3nn3x-profile"})
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.load(r)
    return data["data"]["viewer"]["contributionsCollection"]["contributionCalendar"]["totalContributions"]

def resolve_route():
    """(year, count, headline, note) per year — live if a token is set, floored to known reals."""
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    now_year = datetime.now(timezone.utc).year
    years = sorted(y for y in set(list(FALLBACK_CONTRIB) + [now_year - 1, now_year]) if y >= 2025)
    out = []
    for y in years:
        live = None
        if token:
            try:
                live = _fetch_year(y, token)
            except Exception:
                live = None
        count = max(live or 0, FALLBACK_CONTRIB.get(y, 0))   # never regress below known reals
        head, note = MILESTONES.get(y, ("", ""))
        out.append((str(y), count, head, note))
    return out

ROUTE = [(str(y), FALLBACK_CONTRIB[y], *MILESTONES[y]) for y in sorted(FALLBACK_CONTRIB)]

# ---------------------------------------------------------------- svg core ---
# NOTE: resting state is always VISIBLE. Animations only *enhance* via `both`
# fill (which supplies the hidden pre-state while animating). This way, if CSS
# keyframe animations don't run — e.g. an SVG rendered through <img> in some
# contexts — everything still shows correctly, just without motion.
STYLE = """
  .mono{font-family:%s}
  @keyframes rise{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:translateY(0)}}
  @keyframes fade{from{opacity:0}to{opacity:1}}
  @keyframes draw{from{stroke-dashoffset:var(--l,0)}to{stroke-dashoffset:0}}
  @keyframes grow{from{transform:scaleX(0)}to{transform:scaleX(1)}}
  @keyframes pulse{0%%,100%%{opacity:1}50%%{opacity:.3}}
  @keyframes breathe{0%%,100%%{opacity:1}50%%{opacity:.55}}
  @keyframes march{to{stroke-dashoffset:-12}}
  .rise{animation:rise .7s cubic-bezier(.2,.7,.2,1) both}
  .fade{animation:fade .8s ease both}
  .draw{animation:draw 1.5s cubic-bezier(.6,0,.2,1) both}
  .grow{transform-box:fill-box;animation:grow 1.1s cubic-bezier(.2,.7,.2,1) both}
  .pulse{animation:pulse 2.4s ease-in-out infinite}
  .breathe{animation:breathe 3.2s ease-in-out infinite}
  .march{stroke-dasharray:3 9;animation:march 1.4s linear infinite}
  %s
  @media (prefers-reduced-motion:reduce){
    .rise,.fade,.draw,.grow,.pulse,.breathe,.march{animation:none}
  }
""" % (MONO, " ".join(f".s{n}{{animation-delay:{0.06 * n + 0.05:.2f}s}}" for n in range(0, 30)))

def esc(s):
    return html.escape(str(s), quote=True)

def svg(vw, vh, body):
    return (f'<svg viewBox="0 0 {vw} {vh}" fill="none" xmlns="http://www.w3.org/2000/svg" role="img">\n'
            f'<style>{STYLE}</style>\n{body}\n</svg>\n')

def T(x, y, s, size, p, color, ls=None, weight=None, anchor=None, cls=None, style=None, opacity=None):
    a = [f'x="{x}"', f'y="{y}"', f'font-size="{size}"', f'fill="{p[color]}"', 'class="mono' + (f' {cls}' if cls else '') + '"']
    if ls is not None: a.append(f'letter-spacing="{ls}"')
    if weight: a.append(f'font-weight="{weight}"')
    if anchor: a.append(f'text-anchor="{anchor}"')
    if opacity is not None: a.append(f'opacity="{opacity}"')
    if style: a.append(f'style="{style}"')
    return f'<text {" ".join(a)}>{esc(s)}</text>'

def L(x1, y1, x2, y2, p, color="rule", w=1, opacity=None, cls=None, draw=False):
    a = [f'x1="{x1}"', f'y1="{y1}"', f'x2="{x2}"', f'y2="{y2}"', f'stroke="{p[color]}"', f'stroke-width="{w}"']
    if opacity is not None: a.append(f'opacity="{opacity}"')
    classes = []
    if draw:
        length = int(((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5) + 2
        # dasharray only (offset 0 at rest = solid line); --l drives the reveal
        a.append(f'stroke-dasharray="{length}"')
        a.append(f'style="--l:{length}"')
        classes.append("draw")
    if cls: classes.extend(cls.split())
    if classes: a.append(f'class="{" ".join(classes)}"')
    return f'<line {" ".join(a)}/>'

def box(x, y, w, h, p, color="rule", sw=1, rx=2):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="none" stroke="{p[color]}" stroke-width="{sw}"/>'

def tw(s, size):   # monospace text width
    return len(s) * size * CW

# ------------------------------------------------------------ HUD motifs -----
def tick_rule(x1, x2, y, p, color="rule", step=44, th=4, cls=None, down=True):
    """A hairline with small oscilloscope ticks along it."""
    parts = [L(x1, y, x2, y, p, color, cls=cls)]
    d = th if down else -th
    x = x1
    while x <= x2 + 0.5:
        parts.append(f'<line x1="{x:.0f}" y1="{y}" x2="{x:.0f}" y2="{y+d}" '
                     f'stroke="{p[color]}" stroke-width="1" opacity=".65"/>')
        x += step
    return "\n".join(parts)

def corners(x, y, w, h, p, s=14, color="accent", sw=1.3, cls="fade s0"):
    """Four L-shaped HUD corner brackets around a frame."""
    def br(cx, cy, dx, dy):
        return (f'<path d="M {cx+dx*s:.0f} {cy:.0f} L {cx:.0f} {cy:.0f} '
                f'L {cx:.0f} {cy+dy*s:.0f}" stroke="{p[color]}" stroke-width="{sw}" fill="none"/>')
    return (f'<g class="{cls}">' + br(x, y, 1, 1) + br(x + w, y, -1, 1)
            + br(x, y + h, 1, -1) + br(x + w, y + h, -1, -1) + '</g>')

def load_meter(x, y, p, n=5, filled=3, bw=9, gap=4, h=10):
    parts = []
    for i in range(n):
        on = i < filled
        parts.append(f'<rect x="{x+i*(bw+gap)}" y="{y}" width="{bw}" height="{h}" '
                     f'fill="{p["amber"] if on else "none"}" stroke="{p["rule"]}" stroke-width="1"/>')
    return "".join(parts)

def blink(cx, cy, r, p, color="amber", ring=False, dur="2.2s"):
    """Status dot with a SMIL blink (runs even in <img> on GitHub)."""
    out = []
    if ring:
        out.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{p[color]}" stroke-width="1">'
                   f'<animate attributeName="r" values="{r};{r*2.6:.0f}" dur="{dur}" repeatCount="indefinite"/>'
                   f'<animate attributeName="opacity" values=".8;0" dur="{dur}" repeatCount="indefinite"/></circle>')
    out.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{p[color]}">'
               f'<animate attributeName="opacity" values="1;.3;1" dur="{dur}" repeatCount="indefinite"/></circle>')
    return "".join(out)

def gauge(cx, cy, r, pct, label, sub, p):
    import math
    def pt(ang, rr=r):
        a = math.radians(ang)
        return (cx + rr * math.cos(a), cy - rr * math.sin(a))
    x0, y0 = pt(180); x1, y1 = pt(0)
    ang = 180 - 180 * (pct / 100.0)
    xv, yv = pt(ang)
    out = [f'<path d="M {x0:.1f} {y0:.1f} A {r} {r} 0 0 1 {x1:.1f} {y1:.1f}" '
           f'stroke="{p["rule"]}" stroke-width="6" fill="none"/>']
    # tick marks around the dial
    for t in range(0, 181, 30):
        ax, ay = pt(180 - t, r + 2); bx, by = pt(180 - t, r + 8)
        out.append(f'<line x1="{ax:.1f}" y1="{ay:.1f}" x2="{bx:.1f}" y2="{by:.1f}" stroke="{p["dim"]}" stroke-width="1"/>')
    # value arc — SMIL sweep-in via dashoffset
    length = math.pi * r
    out.append(f'<path d="M {x0:.1f} {y0:.1f} A {r} {r} 0 0 1 {xv:.1f} {yv:.1f}" '
               f'stroke="{p["amber"]}" stroke-width="6" fill="none" '
               f'stroke-dasharray="{length:.0f}" stroke-dashoffset="{length:.0f}">'
               f'<animate attributeName="stroke-dashoffset" from="{length:.0f}" to="0" dur="1.3s" '
               f'begin="0.3s" fill="freeze" calcMode="spline" keySplines="0.2 0.7 0.2 1" keyTimes="0;1"/></path>')
    # needle sweeps from left (180°) to value
    nx, ny = pt(ang, r - 10)
    lx, ly = pt(180, r - 10)
    out.append(f'<line x1="{cx}" y1="{cy}" x2="{lx:.1f}" y2="{ly:.1f}" stroke="{p["amber"]}" stroke-width="2">'
               f'<animate attributeName="x2" from="{lx:.1f}" to="{nx:.1f}" dur="1.3s" begin="0.3s" '
               f'fill="freeze" calcMode="spline" keySplines="0.2 0.7 0.2 1" keyTimes="0;1"/>'
               f'<animate attributeName="y2" from="{ly:.1f}" to="{ny:.1f}" dur="1.3s" begin="0.3s" '
               f'fill="freeze" calcMode="spline" keySplines="0.2 0.7 0.2 1" keyTimes="0;1"/></line>')
    out.append(f'<circle cx="{cx}" cy="{cy}" r="3.5" fill="{p["amber"]}"/>')
    out.append(T(cx, cy - 6, f"{pct:.0f}%", 30, p, "bone", anchor="middle", weight=700))
    out.append(T(cx, cy + 14, label, 9.5, p, "muted", ls=2, anchor="middle"))
    out.append(T(cx, cy + 30, sub, 9, p, "amber", ls=1, anchor="middle"))
    return "".join(out)

# ---------------------------------------------------------------- assets -----
def a_header(p):
    b = [corners(20, 16, 960, 368, p, s=16, color="accent", cls="fade s0")]
    # live readout strip
    b.append(blink(M + 4, 41, 4, p, "amber"))
    b.append(T(M + 16, 45, "SYS ONLINE", 11, p, "amber", ls=3.5, cls="fade s1"))
    b.append(T(R, 45, "NORWAY   ·   UPTIME 2Y", 11, p, "muted", ls=2.5, anchor="end", cls="fade s1"))
    b.append(tick_rule(M, R, 58, p, cls="s1"))
    b += [
        T(46, 176, NAME, 74, p, "bone", ls=6, cls="rise s3"),
        T(M, 214, ROLE, 19, p, "muted", cls="fade s4"),
        T(M, 274, "focus  ▸", 12.5, p, "dim", ls=1, cls="fade s6"),
        T(132, 274, FOCUS, 12.5, p, "accent", ls=1, cls="fade s6"),
        T(M, 300, STATUS, 12.5, p, "dim", ls=1, cls="fade s7"),
        tick_rule(M, R, 342, p, cls="s7", down=False),
        T(M, 374, "    ·    ".join(TAGS), 11.5, p, "muted", ls=3, cls="fade s8"),
        T(R, 374, "SINCE 2024", 11.5, p, "muted", ls=3, anchor="end", cls="fade s8"),
    ]
    return svg(W, 400, "\n".join(b))

def a_section(num, title, slug, p):
    label = f"CH.{num} // {slug}"
    title_w = tw(title, 14) + 6 * len(title)          # includes letter-spacing
    label_w = tw(label, 11) + 2 * len(label)
    b = [
        corners(40, 28, 84, 48, p, s=9, color="accent", cls="fade s0"),
        T(M, 68, num, 52, p, "ghost", cls="fade s0"),
        f'<rect class="fade s1" x="140" y="47" width="4" height="15" fill="{p["amber"]}"/>',
        T(154, 58, title, 14, p, "accent", ls=6, cls="fade s1"),
        T(R, 58, label, 11, p, "muted", ls=2, anchor="end", cls="fade s1"),
    ]
    lx = 154 + title_w + 28
    x2 = R - label_w - 24
    if x2 > lx:
        b.append(tick_rule(lx, x2, 53, p, cls="s2"))
    return svg(W, 92, "\n".join(b))

def a_whoami(p):
    b = []
    ys = [32, 60, 88]
    for i, (line, color, size) in enumerate(WHOAMI):
        b.append(T(M, ys[i], line, size, p, color, cls=f"rise s{i+1}"))
    b.append(L(M, 116, R, 116, p, opacity=.5, cls=f"rise s4"))
    ry = [148, 182, 216]
    for i, (label, val, color) in enumerate(WHOAMI_ROWS):
        b.append(T(M, ry[i], label, 11, p, "muted", ls=2.5, cls=f"rise s{i+4}"))
        b.append(T(154, ry[i], val, 15, p, color, cls=f"rise s{i+4}"))
    return svg(W, 236, "\n".join(b))

def a_projects(p):
    """Each project as a telemetry channel readout: status LED, name, an amber
    'signal' meter for stars, spec line — module vocabulary, no boxes."""
    rows = []
    row_h = 108
    max_s = max(s for *_, s in PROJECTS) or 1
    mtrack_w = 108
    mx0 = R - mtrack_w
    for i, (title, copy, meta, stars) in enumerate(PROJECTS):
        dy = 16 + i * row_h
        fill = stars / max_s * mtrack_w
        g = [f'<g class="fade s{i}" transform="translate(0 {dy})">',
             T(M, 24, f"CH.{i+1:02d}", 12, p, "ghost", ls=1, weight=700),
             T(M + 66, 24, title, 17, p, "bone", ls=.8, weight=700),
             # signal meter (stars)
             T(mx0 - 12, 24, f"★ {stars}", 11, p, "amber", ls=.5, anchor="end"),
             f'<rect x="{mx0}" y="15" width="{mtrack_w}" height="6" rx="1" fill="none" stroke="{p["rule"]}" stroke-width="1"/>',
             f'<rect class="grow s{i}" style="transform-origin:left" x="{mx0}" y="15" width="{fill:.1f}" height="6" rx="1" fill="{p["amber"]}"/>',
             T(R, 12, "SIGNAL", 8, p, "dim", ls=2, anchor="end"),
             # copy
             T(M, 49, copy[0], 12.5, p, "muted"),
             T(M, 68, copy[1], 12.5, p, "muted"),
             # status LED + spec line
             blink(M + 3, 85, 3, p, "amber"),
             T(M + 14, 88, "LIVE", 11, p, "amber", ls=1),
             T(M + 58, 88, f"·  {meta}", 11, p, "dim", ls=.6),
             L(M, 104, R, 104, p),
             '</g>']
        rows.append("\n".join(g))
    h = 16 + len(PROJECTS) * row_h + 8
    return svg(W, h, "\n".join(rows))

def a_ecosystem(p):
    """PCB-style signal routing: a processor chip feeds three lane 'buses',
    each tapping its cluster of project nodes. An amber pulse rides each bus."""
    H = 432
    b = [tick_rule(M, R, 40, p),
         T(M, 28, "SYSTEM MAP — SIGNAL ROUTING", 11, p, "muted", ls=3.5, cls="fade s0"),
         T(R, 28, "CH.02 // MAP", 11, p, "muted", ls=3.5, anchor="end", cls="fade s0")]

    # --- processor chip, center top ---
    chip_w, chip_h, chip_y = 156, 48, 60
    chip_x = (W - chip_w) / 2
    cx = W / 2
    b.append('<g class="fade s1">')
    b.append(box(chip_x, chip_y, chip_w, chip_h, p, "accent", sw=1.3))
    for i in range(3):                       # IC leg pins
        yy = chip_y + 12 + i * 12
        b.append(L(chip_x - 6, yy, chip_x, yy, p, "accent"))
        b.append(L(chip_x + chip_w, yy, chip_x + chip_w + 6, yy, p, "accent"))
    b.append(T(cx, chip_y + 22, ECO_CORE[0], 13, p, "bone", ls=2, anchor="middle"))
    b.append(T(cx, chip_y + 38, ECO_CORE[1], 8.5, p, "muted", ls=.5, anchor="middle"))
    b.append('</g>')
    b.append(blink(chip_x + 12, chip_y + 11, 3, p, "amber"))     # power LED

    # --- distribution bus + three lanes ---
    lanes = [("DESKTOP TELEMETRY", ECO_LEFT, 135),
             ("WEB PLATFORMS", ECO_RIGHT, 445),
             ("DEV TOOLING", ECO_BOTTOM, 735)]
    bus_y, top = 138, 170
    node_w, node_h, step = 196, 44, 56
    b.append(L(cx, chip_y + chip_h, cx, bus_y, p, "rule"))               # chip → bus
    b.append(L(lanes[0][2], bus_y, lanes[-1][2], bus_y, p, "rule"))      # horizontal bus

    for li, (label, nodes, rx) in enumerate(lanes):
        ncx = rx + 20 + node_w / 2
        last_mid = top + (len(nodes) - 1) * step + node_h / 2
        b.append(T(ncx, 126, label, 10, p, "accent", ls=3, anchor="middle", cls="fade s2"))
        b.append(f'<circle cx="{rx}" cy="{bus_y}" r="2.5" fill="{p["rule"]}"/>')
        b.append(L(rx, bus_y, rx, last_mid, p, "rule"))                  # vertical rail
        for ni, (name, sub) in enumerate(nodes):
            ny = top + ni * step
            mid = ny + node_h / 2
            b.append(L(rx, mid, rx + 20, mid, p, "rule"))                # tap
            b.append(f'<circle cx="{rx}" cy="{mid:.0f}" r="2.5" fill="{p["amber"]}"/>')
            b.append(f'<g class="fade s{ni+3}">')
            b.append(box(rx + 20, ny, node_w, node_h, p, "rule"))
            b.append(T(rx + 34, ny + 19, name, 12, p, "bone", ls=.5))
            b.append(T(rx + 34, ny + 34, sub, 9, p, "muted"))
            b.append('</g>')
        # amber data pulse riding the bus
        b.append(f'<circle cx="{rx}" cy="{bus_y}" r="3" fill="{p["amber"]}" opacity="0">'
                 f'<animate attributeName="cy" values="{bus_y};{last_mid:.0f}" dur="2.6s" '
                 f'begin="{li*0.5:.1f}s" repeatCount="indefinite"/>'
                 f'<animate attributeName="opacity" values="0;1;1;0" keyTimes="0;.1;.85;1" dur="2.6s" '
                 f'begin="{li*0.5:.1f}s" repeatCount="indefinite"/></circle>')

    b.append(tick_rule(M, R, H - 34, p))
    b.append(T(R, H - 14, "AMBER PULSE — DATA IN MOTION", 10, p, "dim", ls=2, anchor="end", cls="fade s6"))
    return svg(W, H, "\n".join(b))

def a_telemetry(p):
    H = 330
    b = [tick_rule(M, R, 40, p),
         T(M, 28, "TELEMETRY — WHAT THE HANDS ARE DOING", 11, p, "muted", ls=3.5, cls="fade s0"),
         T(R, 28, "CH.04 // TELEMETRY", 11, p, "muted", ls=3.5, anchor="end", cls="fade s0"),
         L(400, 64, 400, 300, p, opacity=.4),
         L(700, 64, 700, 300, p, opacity=.4)]

    # zone A — language distribution (real bytes)
    items = sorted(LANG_BYTES.items(), key=lambda kv: -kv[1])
    dist = items[:5] + [("other", sum(v for _, v in items[5:]))]
    total = sum(LANG_BYTES.values())
    top_pct = dist[0][1] / total * 100
    b.append(T(M, 78, "LANGUAGE DISTRIBUTION · BYTES", 10, p, "dim", ls=2.5, cls="fade s1"))
    y = 108
    scale = 300.0
    for i, (name, val) in enumerate(dist):
        pct = val / total * 100
        bw = max(3, pct / 100 * scale)
        b.append(T(M, y - 6, name, 11, p, "bone"))
        b.append(f'<rect class="grow s{i+2}" style="transform-origin:left" '
                 f'x="{M}" y="{y}" width="{bw:.1f}" height="6" fill="{p["amber" if i == 0 else "bone"]}"/>')
        b.append(T(380, y + 6, f"{pct:.0f}%", 10, p, "muted", anchor="end"))
        y += 34

    # zone B — radial gauge: primary language share
    b.append(T(432, 78, "PRIMARY LANGUAGE SHARE", 10, p, "dim", ls=2.5, cls="fade s1"))
    b.append(gauge(550, 210, 74, top_pct, "OF ALL BYTES", "TYPESCRIPT", p))
    b.append(T(476, 222, "0", 9, p, "dim", anchor="middle"))
    b.append(T(624, 222, "100", 9, p, "dim", anchor="middle"))

    # zone C — counters (one signature stat in amber)
    cy = [118, 178, 238, 298]
    for i, (num, label) in enumerate(COUNTERS):
        b.append(f'<g class="rise s{i+3}">')
        b.append(T(720, cy[i], num, 44, p, "amber" if i == 1 else "bone"))
        b.append(T(790, cy[i] - 6, label, 10, p, "muted", ls=2.5))
        b.append('</g>')
    return svg(W, H, "\n".join(b))

def a_stack(p):
    H = 40 + len(STACK) * 32
    b = [L(138, 8, 138, H - 8, p, opacity=.4)]
    y = 32
    for i, (label, val) in enumerate(STACK):
        b.append(T(M, y, label, 12, p, "muted", ls=2, cls=f"rise s{i+1}"))
        b.append(T(154, y, val, 15, p, "bone", cls=f"rise s{i+1}"))
        y += 32
    return svg(W, H, "\n".join(b))

def a_route(p):
    H = 250
    b = [tick_rule(M, R, 40, p),
         T(M, 28, "THE ROUTE SO FAR", 11, p, "muted", ls=3.5, cls="fade s0"),
         T(R, 28, "CH.06 // ROUTE", 11, p, "muted", ls=3.5, anchor="end", cls="fade s0"),
         L(M, 125, R - 20, 125, p, cls="s1", draw=True)]
    n = len(ROUTE)
    x0, x1 = 210, 700
    step = (x1 - x0) / max(1, n - 1)
    for i, (yr, cnt, head, note) in enumerate(ROUTE):
        x = x0 + i * step
        above = (i % 2 == 0)
        last = i == n - 1
        col = "amber" if last else "accent"
        if last:
            b.append(blink(x, 125, 4, p, "amber", ring=True))
        else:
            b.append(f'<circle cx="{x:.0f}" cy="125" r="4" fill="{p["bone"]}"/>')
        if above:
            b.append(L(x, 121, x, 96, p))
            b.append(T(x, 74, ("NOW · " + yr) if last else yr, 11, p, col, ls=2, anchor="middle", cls=f"rise s{i+2}"))
            b.append(T(x, 90, head, 10.5, p, "bone", ls=1, anchor="middle", cls=f"rise s{i+2}"))
            b.append(T(x, 108, f"{cnt:,} contributions", 9.5, p, "muted", anchor="middle", cls=f"rise s{i+2}"))
        else:
            b.append(L(x, 129, x, 154, p))
            b.append(T(x, 172, ("NOW · " + yr) if last else yr, 11, p, col, ls=2, anchor="middle", cls=f"rise s{i+2}"))
            b.append(T(x, 188, head, 10.5, p, "bone", ls=1, anchor="middle", cls=f"rise s{i+2}"))
            b.append(T(x, 206, f"{cnt:,} contributions", 9.5, p, "muted", anchor="middle", cls=f"rise s{i+2}"))
    # ghost future
    b.append(f'<circle cx="{R-20}" cy="125" r="3" fill="{p["dim"]}"/>')
    b.append(T(R - 20, 105, f"{int(ROUTE[-1][0])+1} →", 10, p, "dim", ls=2, anchor="end", cls="fade s6"))
    b.append(T(R - 20, 150, "the interesting part", 13, p, "dim", anchor="end", cls="fade s6"))
    return svg(W, H, "\n".join(b))

def a_badge(label, p):
    w = int(tw(label, 12) + 34)
    b = [T(0, 16, label, 12, p, "bone", ls=2),
         T(tw(label, 12) + 8, 16, "↗", 12, p, "accent"),
         L(0, 26, w, 26, p, opacity=.6)]
    return svg(w, 30, "\n".join(b)), w

def a_footer(p):
    b = [tick_rule(M, R, 24, p, cls="s1"),
         blink(M + 12, 60, 4, p, "amber", ring=True),
         T(M + 32, 56, "STATUS", 12, p, "muted", ls=3, cls="fade s2"),
         T(M + 96, 56, "BUILDING", 12, p, "amber", ls=3, cls="fade s2"),
         T(M + 32, 78, "probably in a terminal, probably past midnight", 11, p, "muted", ls=1, cls="fade s3"),
         T(R, 64, "github.com/F3NN3X   ·   Norway   ·   © 2026", 13, p, "muted", anchor="end", cls="fade s3")]
    return svg(W, 104, "\n".join(b))

# ---------------------------------------------------------------- build ------
SECTIONS = [("whoami", a_whoami), ("system-map", a_ecosystem), ("projects", a_projects),
            ("telemetry", a_telemetry), ("stack", a_stack), ("the-route", a_route)]

def build():
    global ROUTE
    ROUTE = resolve_route()
    root = os.path.dirname(os.path.abspath(__file__))
    light_dir = os.path.join(root, "assets")
    dark_dir = os.path.join(light_dir, "dark")
    os.makedirs(dark_dir, exist_ok=True)
    man = {}

    def emit(name, ls, ds):
        open(os.path.join(light_dir, name), "w", encoding="utf-8", newline="\n").write(ls)
        open(os.path.join(dark_dir, name), "w", encoding="utf-8", newline="\n").write(ds)
        man[name] = (ls, ds)

    emit("header.svg", a_header(LIGHT), a_header(DARK))
    order = []
    for i, (slug, fn) in enumerate(SECTIONS, start=1):
        num = f"{i:02d}"
        title = slug.replace("-", " ").upper()
        sname = f"s{num}.svg"
        emit(sname, a_section(num, title, slug, LIGHT), a_section(num, title, slug, DARK))
        art = f"{slug.replace('-', '')}.svg"
        emit(art, fn(LIGHT), fn(DARK))
        order.append((sname, art))
    emit("footer.svg", a_footer(LIGHT), a_footer(DARK))

    badges = []          # social links removed by request
    bmeta = []
    for label, href, fname in badges:
        ls, _ = a_badge(label, LIGHT)
        ds, _ = a_badge(label, DARK)
        emit(fname, ls, ds)
        bmeta.append((label, href, fname))

    write_readme(root, order, bmeta)
    write_preview(root, man, order, bmeta)
    print(f"Wrote {len(man)} asset pairs + README.md + preview.html")

def _pic(name, extra=""):
    return (f'<picture><source media="(prefers-color-scheme: dark)" srcset="assets/dark/{name}"/>'
            f'<img src="assets/{name}" alt="{name[:-4]}"{extra}/></picture>')

def write_readme(root, order, bmeta):
    out = ['<div align="center">', "", _pic("header.svg"), ""]
    for label, href, fname in bmeta:
        out.append(f'<a href="{href}"><picture>'
                   f'<source media="(prefers-color-scheme: dark)" srcset="assets/dark/{fname}"/>'
                   f'<img src="assets/{fname}" alt="{label}"/></picture></a>')
    out += ["", "</div>", ""]
    for sec, art in order:
        out.append(_pic(sec))
        out.append(_pic(art))
    out += [_pic("footer.svg"), "", "<!-- Generated by generate.py — editorial system-dossier layout. -->"]
    open(os.path.join(root, "README.md"), "w", encoding="utf-8", newline="\n").write("\n".join(out) + "\n")

def write_preview(root, man, order, bmeta):
    # Inline the SVGs (not <img>) so CSS keyframe animations actually run in the
    # preview. Colors are literal per-file, so there is no :root cross-contamination.
    def inl(name):
        ls, ds = man[name]
        return f'<div class="light">{ls}</div><div class="dark">{ds}</div>'
    body = [f'<div class="pic">{inl("header.svg")}</div>', '<div class="badges">']
    for _, _, fname in bmeta:
        body.append(f'<span class="badge">{inl(fname)}</span>')
    body.append("</div>")
    for sec, art in order:
        body.append(f'<div class="pic">{inl(sec)}</div>')
        body.append(f'<div class="pic">{inl(art)}</div>')
    body.append(f'<div class="pic">{inl("footer.svg")}</div>')
    open(os.path.join(root, "preview.html"), "w", encoding="utf-8", newline="\n").write(
        PREVIEW_TMPL.replace("__BODY__", "\n".join(body)))

PREVIEW_TMPL = """<meta charset="utf-8"/>
<title>F3NN3X Profile Preview</title>
<style>
  :root{--bg:#ffffff;--tab:#f4f4f4;--tabfg:#666;--line:#e0e0e0;--fg:#333}
  body{margin:0;background:var(--bg);color:var(--fg);font-family:ui-monospace,Consolas,monospace}
  .wrap{max-width:1040px;margin:0 auto;padding:16px 20px 80px}
  .bar{position:sticky;top:0;display:flex;gap:12px;align-items:center;padding:14px 4px;background:var(--bg);border-bottom:1px solid var(--line);z-index:5}
  .bar b{font-size:13px;letter-spacing:2px}
  .bar .sub{font-size:12px;color:#999}
  .seg{margin-left:auto;display:flex;border:1px solid var(--line);border-radius:8px;overflow:hidden}
  .seg button{font:inherit;font-size:12px;padding:7px 16px;border:0;background:var(--tab);color:var(--tabfg);cursor:pointer}
  .seg button.on{background:#333;color:#fff}
  .col{padding-top:26px;display:flex;flex-direction:column;gap:6px}
  .pic{width:100%}
  .pic svg{width:100%;height:auto;display:block}
  .badges{display:flex;gap:22px;justify-content:center;margin:6px 0 14px}
  .badge svg{height:30px;width:auto}
  .dark{display:none}
  body.dk{--bg:#0d1117;--tab:#161b22;--tabfg:#8b949e;--line:#30363d;--fg:#ddd}
  body.dk .bar b{color:#ddd}
  body.dk .seg button.on{background:#ddd;color:#0d1117}
  body.dk .light{display:none}
  body.dk .dark{display:block}
</style>
<div class="wrap">
  <div class="bar">
    <b>PROFILE PREVIEW</b><span class="sub">github.com/F3NN3X</span>
    <div class="seg">
      <button id="bl" class="on" onclick="setTheme('light')">☀ light</button>
      <button id="bd" onclick="setTheme('dark')">☾ dark</button>
    </div>
  </div>
  <div class="col">
__BODY__
  </div>
</div>
<script>
  function setTheme(t){document.body.classList.toggle('dk',t==='dark');
    document.getElementById('bl').classList.toggle('on',t==='light');
    document.getElementById('bd').classList.toggle('on',t==='dark');
    try{localStorage.setItem('pv',t)}catch(e){}}
  try{setTheme(localStorage.getItem('pv')||(matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light'))}catch(e){}
</script>
"""

if __name__ == "__main__":
    build()
