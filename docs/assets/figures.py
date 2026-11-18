"""Regenerate the README figures as static SVG, one light and one dark file each.

    python docs/assets/figures.py

Standard library only. Every number is copied from eval/REAL_TRAFFIC.md,
eval/README.md, MODEL_CARD.md or service/README.md; change it there first.
GitHub shows these through <picture> with a prefers-color-scheme source, so
each file carries literal colors and a transparent background.
"""
from pathlib import Path
from xml.sax.saxutils import escape

OUT = Path(__file__).resolve().parent

SANS = "system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif"
MONO = "ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, 'Liberation Mono', monospace"

THEMES = {
    "light": dict(page="#ffffff", ink="#1f2328", ink2="#59636e", muted="#818b98", grid="#d8dee4",
                  axis="#b7bfc7", panel="#f6f8fa", border="#d1d9e0", v4="#8c959f", v5="#2a78d6",
                  real="#eb6834", link="#9198a1"),
    "dark": dict(page="#0d1117", ink="#f0f6fc", ink2="#9198a1", muted="#768390", grid="#262c36",
                 axis="#3d444d", panel="#151b23", border="#3d444d", v4="#768390", v5="#3987e5",
                 real="#d95926", link="#656c76"),
}


def text(x, y, s, size=14, fill="#000", weight=400, anchor="start", family=SANS, extra=""):
    return (f'<text x="{x:g}" y="{y:g}" font-family="{family}" font-size="{size}" font-weight="{weight}" '
            f'fill="{fill}" text-anchor="{anchor}"{extra}>{escape(s)}</text>')


def svg(width, height, title, desc, body):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" '
            f'height="{height}" role="img" aria-labelledby="t d">\n'
            f'<title id="t">{escape(title)}</title>\n<desc id="d">{escape(desc)}</desc>\n'
            + "\n".join(body) + "\n</svg>\n")


def write(name, theme, content):
    (OUT / f"{name}-{theme}.svg").write_text(content, encoding="utf-8", newline="\n")


# --- Headline numbers -------------------------------------------------------

def headline(theme):
    c = THEMES[theme]
    tiles = [
        (236, "72.0% → 91.0%", "Sealed real requests", "v4 → v5, mean of ten heads"),
        (236, "44.0% → 97.8%", "Synthetic test set", "untuned base → v4"),
        (176, "322M", "Parameters", "ten heads, one pass"),
        (208, "37 ms", "Median latency", "short requests, Apple silicon"),
    ]
    body, x = [], 0
    for width, value, label, note in tiles:
        body.append(f'<rect x="{x + 0.5}" y="0.5" width="{width - 1}" height="103" rx="8" '
                    f'fill="{c["panel"]}" stroke="{c["border"]}"/>')
        body.append(text(x + 18, 44, value, 26, c["ink"], 650))
        body.append(text(x + 18, 70, label, 14, c["ink"], 600))
        body.append(text(x + 18, 90, note, 13, c["ink2"]))
        x += width + 8
    return svg(880, 104, "Task Router in four numbers",
               "Mean accuracy over ten heads on 30 sealed real requests rose from 72.0% (v4) to 91.0% (v5). "
               "On the synthetic test set it rose from 44.0% (untuned base) to 97.8% (v4). "
               "322M parameters, ten heads answered in one forward pass. "
               "Median latency 37 ms for short requests on Apple silicon.", body)


# --- Figure (a): per-head before/after on the sealed 30 ---------------------

# (head, v4, best v5 = "from base"), eval/REAL_TRAFFIC.md. Correct answers out of 30.
SEALED = [
    ("task_type", 26, 28), ("difficulty", 10, 24), ("web_search", 29, 29), ("input_modality", 29, 29),
    ("document_read", 21, 22), ("media_output", 30, 30), ("project_access", 8, 29),
    ("run_commands", 12, 29), ("browser_use", 29, 29), ("executor_intent", 22, 24),
]


def pct(n):
    return f"{100 * n / 30:.1f}%"


def sealed(theme):
    c = THEMES[theme]
    x0, x1 = 172, 672
    sx = lambda n: x0 + (x1 - x0) * n / 30
    rows = sorted(SEALED, key=lambda r: (-(r[2] - r[1]), r[1], r[0]))
    top, step = 96, 26
    body = [
        text(0, 22, "Per-head accuracy on 30 sealed real requests", 17, c["ink"], 650),
        f'<circle cx="7" cy="49" r="6" fill="{c["v4"]}"/>',
        text(19, 54, "v4 · in production, synthetic data only", 13.5, c["ink2"]),
        f'<circle cx="300" cy="49" r="6" fill="{c["v5"]}"/>',
        text(312, 54, "v5 · plus 75 reviewed real rows (best of three variants)", 13.5, c["ink2"]),
        text(692, 82, "v4 → v5", 12.5, c["muted"]),
        text(876, 82, "gain", 12.5, c["muted"], anchor="end"),
    ]
    bottom = top + step * (len(rows) - 1) + 52
    for k in range(5):
        x = x0 + (x1 - x0) * k / 4
        body.append(f'<line x1="{x:g}" y1="{top - 16}" x2="{x:g}" y2="{bottom + 12}" stroke="{c["grid"]}" stroke-width="1"/>')
        body.append(text(x, bottom + 32, f"{25 * k}%", 12.5, c["muted"], anchor="middle"))

    def row(y, label, a, b, bold=False, mono=True, scale=30):
        f = lambda n: x0 + (x1 - x0) * n / scale
        out = [text(0, y + 5, label, 14, c["ink"], 650 if bold else 400, family=MONO if mono else SANS)]
        if b != a:
            out.append(f'<line x1="{f(a):.1f}" y1="{y}" x2="{f(b):.1f}" y2="{y}" stroke="{c["v4"]}" stroke-width="2" stroke-linecap="round"/>')
        out.append(f'<circle cx="{f(a):.1f}" cy="{y}" r="6" fill="{c["v4"]}" stroke="{c["page"]}" stroke-width="2"/>')
        out.append(f'<circle cx="{f(b):.1f}" cy="{y}" r="6" fill="{c["v5"]}" stroke="{c["page"]}" stroke-width="2"/>')
        out.append(text(692, y + 5, f"{100 * a / scale:.1f} → {100 * b / scale:.1f}", 13.5, c["ink2"] if not bold else c["ink"],
                        650 if bold else 400, extra=' font-variant-numeric="tabular-nums"'))
        gain = 100 * (b - a) / scale
        out.append(text(876, y + 5, f"+{gain:.1f}" if gain > 0.05 else "0", 13.5,
                        c["ink"] if gain > 10 else c["muted"], 650 if gain > 10 else 400, anchor="end"))
        return out

    for i, (head, a, b) in enumerate(rows):
        body += row(top + i * step, head, a, b)
    sep = top + step * (len(rows) - 1) + 20
    body.append(f'<line x1="0" y1="{sep}" x2="880" y2="{sep}" stroke="{c["axis"]}" stroke-width="1"/>')
    body += row(bottom, "Mean of ten heads", 720, 910, bold=True, mono=False, scale=1000)
    desc = ("Dumbbell chart, v4 to v5 per head, ordered by gain: "
            + "; ".join(f"{h} {pct(a)} to {pct(b)}" for h, a, b in rows)
            + ". Mean of ten heads 72.0% to 91.0%.")
    return svg(880, bottom + 40, "Per-head accuracy on 30 sealed real requests, v4 vs v5", desc, body)


# --- Figure (b): synthetic test accuracy against training rows --------------

CURVE = [("base", 0, 44.0), ("v1", 240, 79.8), ("v2", 400, 83.7), ("v3", 520, 96.2), ("v4", 720, 97.8)]


def curve(theme):
    c = THEMES[theme]
    x0, x1, y0, y1 = 52, 600, 92, 262        # y0 = 100%, y1 = 40%
    sx = lambda rows: x0 + (x1 - x0) * rows / 720
    sy = lambda p: y1 - (y1 - y0) * (p - 40) / 60
    body = [
        text(0, 22, "Mean accuracy over ten heads, by training rows", 16, c["ink"], 650),
        f'<line x1="0" y1="45" x2="18" y2="45" stroke="{c["v5"]}" stroke-width="2"/>',
        f'<circle cx="9" cy="45" r="4" fill="{c["v5"]}"/>',
        text(26, 50, "synthetic test (60 rows)", 13, c["ink2"]),
        f'<circle cx="218" cy="45" r="5" fill="none" stroke="{c["real"]}" stroke-width="2.5"/>',
        text(230, 50, "same v4 on 30 sealed real requests", 13, c["ink2"]),
    ]
    for p in (40, 60, 80, 100):
        body.append(f'<line x1="{x0}" y1="{sy(p):g}" x2="{x1 + 16}" y2="{sy(p):g}" stroke="{c["grid"]}" stroke-width="1"/>')
        body.append(text(x0 - 8, sy(p) + 4, f"{p}%", 12, c["muted"], anchor="end"))
    for _, rows, _ in CURVE:
        body.append(text(sx(rows), y1 + 22, f"{rows}", 12, c["muted"], anchor="middle"))
    body.append(text(x1 + 16, y1 + 42, "training rows", 12, c["muted"], anchor="end"))
    pts = " ".join(f"{sx(r):.1f},{sy(p):.1f}" for _, r, p in CURVE)
    body.append(f'<polyline points="{pts}" fill="none" stroke="{c["v5"]}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>')
    gap_x = sx(720)
    body.append(f'<line x1="{gap_x:.1f}" y1="{sy(97.8) + 8:.1f}" x2="{gap_x:.1f}" y2="{sy(72.0) - 9:.1f}" stroke="{c["muted"]}" stroke-width="1" stroke-dasharray="3 3"/>')
    for name, r, p in CURVE:
        body.append(f'<circle cx="{sx(r):.1f}" cy="{sy(p):.1f}" r="4.5" fill="{c["v5"]}" stroke="{c["page"]}" stroke-width="2"/>')
    halo = f' stroke="{c["page"]}" stroke-width="4" stroke-linejoin="round" paint-order="stroke"'
    labels = {"base": (10, 4, "start"), "v1": (-8, -10, "end"), "v2": (0, -12, "middle"),
              "v3": (0, -12, "middle"), "v4": (0, -12, "middle")}
    for name, r, p in CURVE:
        dx, dy, anchor = labels[name]
        body.append(text(sx(r) + dx, sy(p) + dy, f"{name} {p:.1f}%", 12.5, c["ink"], 600, anchor=anchor, extra=halo))
    body.append(f'<circle cx="{gap_x:.1f}" cy="{sy(72.0):.1f}" r="5.5" fill="{c["page"]}" stroke="{c["real"]}" stroke-width="2.5"/>')
    body.append(text(gap_x - 12, sy(72.0) + 4, "v4 on real requests 72.0%", 12.5, c["ink"], 600, anchor="end", extra=halo))
    desc = ("Line chart of mean accuracy on the 60-row synthetic test against training rows: "
            + ", ".join(f"{n} ({r} rows) {p:.1f}%" for n, r, p in CURVE)
            + ". A separate point shows the same v4 at 72.0% on 30 sealed real requests.")
    return svg(640, 312, "Synthetic test accuracy by training rows, v1 to v4", desc, body)


# --- Figure (c): request flow ------------------------------------------------

def arrow(x1, y1, x2, y2, color, dashed=False, width=1.5):
    dash = ' stroke-dasharray="5 4"' if dashed else ""
    out = [f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="{width}"{dash}/>']
    if x2 != x1:
        d = 1 if x2 > x1 else -1
        out.append(f'<polygon points="{x2},{y2} {x2 - 8 * d},{y2 - 4.5} {x2 - 8 * d},{y2 + 4.5}" fill="{color}"/>')
    else:
        d = 1 if y2 > y1 else -1
        out.append(f'<polygon points="{x2},{y2} {x2 - 4.5},{y2 - 8 * d} {x2 + 4.5},{y2 - 8 * d}" fill="{color}"/>')
    return out


def box(x, y, w, h, c, fill=None, stroke=None, dashed=False):
    dash = ' stroke-dasharray="5 4"' if dashed else ""
    return (f'<rect x="{x + 0.5}" y="{y + 0.5}" width="{w - 1}" height="{h - 1}" rx="8" '
            f'fill="{fill or c["panel"]}" stroke="{stroke or c["border"]}"{dash}/>')


def flow(theme):
    c = THEMES[theme]
    body = []
    # Column A: the request state, built by PugPort.
    ax, aw = 0, 200
    body.append(text(ax, 16, "PUGPORT", 12, c["muted"], 650, extra=' letter-spacing="0.08em"'))
    body.append(box(ax, 28, aw, 214, c))
    body.append(text(ax + 16, 56, "Request state", 15, c["ink"], 650))
    for i, part in enumerate(["message", "recent context", "quoted reference text",
                              "attachment metadata", "candidate executors"]):
        body.append(f'<circle cx="{ax + 21}" cy="{80 + i * 25}" r="2.5" fill="{c["ink2"]}"/>')
        body.append(text(ax + 32, 85 + i * 25, part, 14, c["ink"]))
    body.append(text(ax + 16, 228, "packed to 1024 tokens", 12, c["ink2"]))

    # Column B: the service.
    bx, bw = 272, 296
    body.append(text(bx, 16, "TASK ROUTER SERVICE", 12, c["muted"], 650, extra=' letter-spacing="0.08em"'))
    body.append(box(bx, 28, bw, 214, c))
    body.append(text(bx + 16, 56, "mmBERT encoder, one pass", 15, c["ink"], 650))
    body.append(text(bx + 16, 76, "queue of 8 · one inference at a time", 12, c["ink2"]))
    heads = ["task_type", "difficulty", "web_search", "document_read", "run_commands",
             "browser_use", "input_modality", "media_output", "project_access", "executor_intent"]
    for i, head in enumerate(heads):
        col, r = i % 2, i // 2
        px, py = bx + 16 + col * 138, 90 + r * 29
        body.append(f'<rect x="{px + 0.5}" y="{py + 0.5}" width="129" height="23" rx="5" fill="{c["page"]}" stroke="{c["border"]}"/>')
        body.append(text(px + 65, py + 16, head, 12.5, c["ink"], anchor="middle", family=MONO))
    body += arrow(aw + 2, 135, bx - 4, 135, c["ink2"])
    body.append(text((aw + bx) / 2, 126, "POST", 12, c["ink2"], 600, anchor="middle", family=MONO))
    body.append(text((aw + bx) / 2, 154, "/v1/judge", 12, c["ink2"], 600, anchor="middle", family=MONO))

    # Column C: how PugPort uses the answers.
    cx, cw = 640, 240
    body.append(text(cx, 16, "PUGPORT", 12, c["muted"], 650, extra=' letter-spacing="0.08em"'))
    body.append(box(cx, 28, cw, 214, c))
    body.append(text(cx + 16, 56, "Uses the answers", 15, c["ink"], 650))
    uses = [("difficulty", "model tier and effort"), ("task_type", "routing category"),
            ("project_access, run_commands,", None), ("browser_use, media_output", "reply or task")]
    y = 84
    for head, use in uses:
        body.append(text(cx + 16, y, head, 12.5, c["ink"], family=MONO))
        if use:
            body.append(text(cx + 16, y + 18, "→ " + use, 13, c["ink2"]))
            y += 44
        else:
            y += 17
    body += arrow(bx + bw + 2, 135, cx - 4, 135, c["ink2"])
    body.append(text((bx + bw + cx) / 2, 126, "ten", 12, c["ink2"], 600, anchor="middle"))
    body.append(text((bx + bw + cx) / 2, 154, "answers", 12, c["ink2"], 600, anchor="middle"))

    # Fallback path and the policy layer that always wins.
    body.append(box(ax, 300, aw + 60, 56, c, fill=c["page"], dashed=True))
    body.append(text(ax + 16, 324, "Rule-based routing", 14, c["ink"], 650))
    body.append(text(ax + 16, 343, "deadline missed or error · 30 s back-off", 12, c["ink2"]))
    body += arrow(ax + 40, 244, ax + 40, 298, c["ink2"], dashed=True)
    px, pw = 436, 350
    body.append(box(px, 290, pw, 76, c, fill=c["page"], stroke=c["v5"]))
    body.append(text(px + 16, 315, "Policy layer, always wins", 14, c["ink"], 650))
    body.append(text(px + 16, 335, "user pins · approved rules · quotas · budgets", 12.5, c["ink2"]))
    body.append(text(px + 16, 354, "read-only limits · advice never widens permissions", 12.5, c["ink2"]))
    body += arrow(cx + 120, 244, cx + 120, 288, c["ink2"])
    body += arrow(ax + aw + 62, 328, px - 4, 328, c["ink2"], dashed=True)
    body += arrow(px + pw + 2, 328, px + pw + 34, 328, c["ink2"])
    body.append(text(880, 333, "route", 14, c["ink"], 650, anchor="end"))
    desc = ("PugPort sends a five-part request state (message, recent context, quoted reference text, attachment "
            "metadata, candidate executors) to POST /v1/judge. The service runs one inference at a time with a queue "
            "of 8; the mmBERT encoder answers ten heads in one pass. PugPort uses difficulty for model tier and effort, "
            "task_type for routing category, and project_access, run_commands, browser_use and media_output to decide "
            "reply or task. On a missed deadline or error it falls back to rule-based routing with a 30 s back-off. "
            "A policy layer of user pins, approved rules, quotas, budgets and read-only limits always wins.")
    return svg(880, 372, "How a request is routed", desc, body)


def main():
    for theme in THEMES:
        write("headline", theme, headline(theme))
        write("sealed-per-head", theme, sealed(theme))
        write("synthetic-curve", theme, curve(theme))
        write("request-flow", theme, flow(theme))


if __name__ == "__main__":
    main()
