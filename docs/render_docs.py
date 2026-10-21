#!/usr/bin/env python3
"""Render the Community Meetings user guides (markdown) to HTML.

Modes:
  --mode multi   one HTML page per markdown file, with sidebar navigation
  --mode single  one big self-contained HTML page per language
  --mode both    build both (default)

Languages: english lives in docs/user, spanish in docs/user_es. The rendered
header carries a language switcher linking the equivalent page in the other
language. Only stdlib + `markdown` are required.
"""
import argparse
import html as html_lib
import re
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parent
LANGS = {
    "en": {"src": ROOT / "user", "title": "Community Meetings — User & Administrator Guide",
           "switch": "Español", "switch_to": "es"},
    "es": {"src": ROOT / "user_es", "title": "Community Meetings — Guía de uso y administración",
           "switch": "English", "switch_to": "en"},
}
OUTBASE = ROOT / "_build"
PAGE_ORDER = [
    "index.md", "concepts.md", "roles-and-permissions.md",
    "admin/configuration.md", "admin/series.md", "admin/catalogs.md",
    "user/prepare-meeting.md", "user/propose-a-point.md", "user/live-meeting.md",
    "user/minutes-and-approval.md", "user/followups.md", "user/carryovers.md",
    "integrations/calendar.md", "integrations/project.md",
    "release-notes.md", "faq.md",
]
MD_EXTENSIONS = ["tables", "fenced_code", "sane_lists", "smarty"]

NAV_LABELS = {
    "en": {
        "index.md": "Overview", "concepts.md": "Concepts",
        "roles-and-permissions.md": "Roles & permissions",
        "admin/configuration.md": "General configuration", "admin/series.md": "Series",
        "admin/catalogs.md": "Catalogs",
        "user/prepare-meeting.md": "Prepare a meeting", "user/propose-a-point.md": "Propose a point",
        "user/live-meeting.md": "Live meeting", "user/minutes-and-approval.md": "Minutes & approval",
        "user/followups.md": "Follow-ups", "user/carryovers.md": "Carryovers",
        "integrations/calendar.md": "Calendar", "integrations/project.md": "Project",
        "release-notes.md": "Release notes", "faq.md": "FAQ",
    },
    "es": {
        "index.md": "Inicio", "concepts.md": "Conceptos",
        "roles-and-permissions.md": "Roles y permisos",
        "admin/configuration.md": "Configuración general", "admin/series.md": "Series",
        "admin/catalogs.md": "Catálogos",
        "user/prepare-meeting.md": "Preparar una reunión", "user/propose-a-point.md": "Proponer un punto",
        "user/live-meeting.md": "Reunión en vivo", "user/minutes-and-approval.md": "Actas y aprobación",
        "user/followups.md": "Seguimientos", "user/carryovers.md": "Arrastres",
        "integrations/calendar.md": "Calendario", "integrations/project.md": "Project",
        "release-notes.md": "Notas de versión", "faq.md": "Preguntas frecuentes",
    },
}
GROUP_NAMES = {
    "en": [("Guide", 0, 3), ("Administer", 3, 6), ("Use", 6, 12), ("Integrations", 12, 14), ("More", 14, None)],
    "es": [("Guía", 0, 3), ("Administrar", 3, 6), ("Uso", 6, 12), ("Integraciones", 12, 14), ("Más", 14, None)],
}

THEME_JS = """<script>
(function () {
  var t = localStorage.getItem("theme") ||
      (window.matchMedia && matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
  document.documentElement.setAttribute("data-theme", t);
  document.addEventListener("DOMContentLoaded", function () {
    var b = document.getElementById("themeToggle");
    if (!b) return;
    var paint = function () { b.textContent = document.documentElement.getAttribute("data-theme") === "dark" ? "☀️" : "🌙"; };
    paint();
    b.addEventListener("click", function () {
      var next = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
      document.documentElement.setAttribute("data-theme", next);
      localStorage.setItem("theme", next);
      paint();
    });
  });
})();
</script>"""

MERMAID_JS = """<script src="https://cdn.jsdelivr.net/npm/mermaid@10.9.1/dist/mermaid.min.js"></script>
<script>document.addEventListener("DOMContentLoaded", function () {
  var blocks = document.querySelectorAll("pre code.language-mermaid");
  blocks.forEach(function (b) {
    var d = document.createElement("div");
    d.className = "mermaid";
    d.textContent = b.textContent;
    b.parentElement.replaceWith(d);
  });
  if (blocks.length && window.mermaid) mermaid.run();
});</script>"""

CSS = """
:root { --brand:#714B67; --ink:#21262d; --muted:#57606a; --line:#d0d7de; --bg:#fff; --soft:#f6f8fa; }
[data-theme="dark"] { --brand:#c9a6d9; --ink:#e4e4ea; --muted:#9aa0aa; --line:#33333d; --bg:#14141a; --soft:#1f1f27; }
* { box-sizing: border-box; }
body { margin:0; font:16px/1.65 -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
       color:var(--ink); background:var(--bg); }
a { color:var(--brand); text-decoration:none; }
a:hover { text-decoration:underline; }
code, pre { font-family:ui-monospace, "Cascadia Code", Menlo, Consolas, monospace; font-size:.9em; }
code { background:var(--soft); padding:.15em .35em; border-radius:4px; }
pre { background:var(--soft); padding:14px; border-radius:8px; overflow:auto; }
pre code { background:none; padding:0; }
h1 { font-size:1.9em; border-bottom:3px solid var(--brand); padding-bottom:.3em; }
h2 { font-size:1.4em; border-bottom:1px solid var(--line); padding-bottom:.25em; margin-top:2em; }
h3 { font-size:1.15em; margin-top:1.6em; }
.table-wrap { max-width:100%; overflow-x:auto; margin:1em 0; }
.table-wrap table { border-collapse:collapse; width:100%; margin:0; }
th, td { border:1px solid var(--line); padding:.5em .75em; text-align:left; vertical-align:top; }
th { background:var(--soft); }
blockquote { margin:1em 0; padding:.6em 1em; border-left:4px solid var(--brand);
             background:var(--soft); border-radius:0 8px 8px 0; }
blockquote p { margin:.2em 0; }
img { max-width:100%; border:1px solid var(--line); border-radius:8px; margin:.6em 0; background:#fff; }
.guide-hero { display:flex; align-items:center; gap:2rem; margin:1.5em 0 2em; padding:1.5rem;
              border:1px solid var(--line); border-radius:14px; background:var(--soft); }
.guide-hero-copy { flex:1 1 55%; min-width:0; }
.guide-hero h2 { margin:.25em 0 .6em; border:0; font-size:1.7em; line-height:1.2; }
.guide-hero p { margin:.65em 0; }
.guide-hero img { flex:0 1 45%; width:45%; margin:0; box-shadow:0 8px 24px rgba(20,20,30,.12); }
.guide-eyebrow { color:var(--brand); font-size:.76em; font-weight:700; letter-spacing:.1em;
                 text-transform:uppercase; }
.guide-cta { display:inline-block; margin-top:.4em; padding:.65em 1em; border-radius:7px;
             background:var(--brand); color:var(--bg); font-weight:700; }
.guide-cta:hover { text-decoration:none; filter:brightness(1.08); }
.guide-features { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:1rem; margin:1.5em 0; }
.guide-features article { min-width:0; overflow:hidden; border:1px solid var(--line); border-radius:12px;
                          padding:1rem; background:var(--bg); }
.guide-features img { display:block; width:100%; height:10rem; object-fit:cover; object-position:top;
                      margin:0 0 .9rem; }
.guide-features article:nth-child(3) img { object-fit:contain; background:var(--soft); }
.guide-features h3 { margin:.3em 0; }
.guide-features p { color:var(--muted); }
.guide-features a { font-weight:650; }
em { color:var(--muted); }
.mermaid svg { max-width:100%; height:auto; }
.mermaid { background:var(--soft); border-radius:8px; padding:10px; }
.langbar { background:var(--brand); color:#fff; padding:.5em 1.2em; font-size:.9em;
           display:flex; align-items:center; gap:1em; }
.langbar .brand { font-weight:700; }
.langbar a { color:#fff; text-decoration:underline; }
.langbar .spacer { flex:1; }
#themeToggle { background:none; border:1px solid rgba(255,255,255,.5); color:#fff;
               border-radius:6px; padding:.15em .55em; cursor:pointer; font-size:1em; }
.wrap { display:flex; align-items:flex-start; }
nav.side { width:260px; flex:0 0 260px; background:var(--soft); min-height:100vh;
           padding:1.2em .9em; font-size:.92em; }
nav.side h3 { font-size:.8em; text-transform:uppercase; letter-spacing:.06em; color:var(--muted);
              margin:1.2em .4em .3em; }
nav.side a { display:block; padding:.28em .6em; border-radius:6px; color:var(--ink); }
nav.side a:hover { background:var(--line); text-decoration:none; }
nav.side a.current { background:var(--brand); color:#fff; }
main.content { flex:1 1 auto; padding:2em 3em 4em; max-width:980px; min-width:0; }
main.content.single { margin:0 auto; float:none; }
.pagenav { margin-top:3em; display:flex; justify-content:space-between; gap:1em; }
.pagenav a { font-weight:600; }
@media (max-width: 900px) {
  .wrap { display:block; }
  nav.side { width:auto; min-height:0; padding:.7em 1em; }
  nav.side h3 { margin:.5em .4em .25em; }
  nav.side a { display:inline-block; margin:.1em .15em; }
  main.content { max-width:none; padding:1.5em 1.25em 3em; }
  .langbar { flex-wrap:wrap; gap:.5em .8em; padding:.6em 1em; }
  .langbar .spacer { display:none; }
  .table-wrap { overflow:visible; }
  .guide-hero { gap:1rem; padding:1rem; }
  .guide-hero h2 { font-size:1.45em; }
  .guide-features { grid-template-columns:1fr; }
  .guide-features article { display:grid; grid-template-columns:minmax(120px,.7fr) 1fr; column-gap:1rem; }
  .guide-features img { grid-row:span 3; height:100%; min-height:9rem; margin:0; }
  .table-wrap table, .table-wrap tbody { display:block; width:100%; }
  .table-wrap thead { position:absolute; width:1px; height:1px; padding:0; margin:-1px;
                      overflow:hidden; clip:rect(0, 0, 0, 0); white-space:nowrap; border:0; }
  .table-wrap tr { display:block; margin:0 0 1em; border:1px solid var(--line);
                   border-radius:8px; overflow:hidden; background:var(--bg); }
  .table-wrap td { display:block; padding:.6em .75em; border:0; border-bottom:1px solid var(--line); }
  .table-wrap td:last-child { border-bottom:0; }
  .table-wrap td::before { content:attr(data-label); display:block; margin-bottom:.15em;
                           color:var(--muted); font-size:.76em; font-weight:700;
                           text-transform:uppercase; letter-spacing:.03em; }
  .table-wrap td:first-child { background:var(--soft); font-weight:700; }
  .table-wrap td:first-child::before { content:none; }
  .pagenav { flex-wrap:wrap; }
}
@media (max-width: 420px) {
  main.content { padding:1.1em .9em 2.5em; }
  h1 { font-size:1.6em; }
  .mermaid { overflow-x:auto; }
  .guide-hero { display:block; }
  .guide-hero img { width:100%; margin-top:1rem; }
  .guide-features article { display:block; }
  .guide-features img { height:auto; max-height:12rem; margin-bottom:.8rem; }
}
"""


def md_to_html(text):
    html = markdown.markdown(text, extensions=MD_EXTENSIONS)

    def wrap_table(match):
        table = match.group(1)
        header = re.search(r"<thead\b[^>]*>.*?<tr\b[^>]*>(.*?)</tr>.*?</thead>", table, flags=re.S)
        labels = []
        if header:
            for cell in re.findall(r"<th\b[^>]*>(.*?)</th>", header.group(1), flags=re.S):
                label = re.sub(r"<[^>]+>", " ", cell)
                labels.append(html_lib.unescape(" ".join(label.split())))

        def label_row(row_match):
            index = 0

            def label_cell(cell_match):
                nonlocal index
                label = labels[index] if index < len(labels) else ""
                index += 1
                attr = ' data-label="%s"' % html_lib.escape(label, quote=True)
                return cell_match.group(1) + attr + ">"

            row = re.sub(r"(<td\b[^>]*)(>)", label_cell, row_match.group(0))
            return row

        if labels:
            body = re.search(r"(<tbody\b[^>]*>)(.*?)(</tbody>)", table, flags=re.S)
            if body:
                rows = re.sub(r"<tr\b[^>]*>.*?</tr>", label_row, body.group(2), flags=re.S)
                table = table[:body.start()] + body.group(1) + rows + body.group(3) + table[body.end():]
        return '<div class="table-wrap">%s</div>' % table

    return re.sub(r"(<table\b[^>]*>.*?</table>)", wrap_table, html, flags=re.S)


def langbar(lang, counterpart_href):
    other = LANGS[LANGS[lang]["switch_to"]]
    href = counterpart_href or "#"
    cls = ' style="opacity:.45;pointer-events:none;"' if not counterpart_href else ""
    return ('<div class="langbar"><span class="brand">Community Meetings</span>'
            f'{LANGS[lang]["title"].split("—")[-1].strip()}'
            f'<a href="{href}"{cls}>{LANGS[lang]["switch"]} →</a>'
            '<span class="spacer"></span>'
            '<button id="themeToggle" type="button" aria-label="Toggle theme"></button></div>')


def rewrite_links(html, page_rel, mode, single_slugs):
    """Rewrite .md links to .html (multi) or #anchors (single)."""
    def repl(m):
        href = m.group(1)
        if href.startswith(("http", "img/")):
            return m.group(0)
        target = href.split("#")[0]
        anchor = "#" + m.group(2) if m.group(2) else ""
        if mode == "multi":
            out = (target[:-3] + ".html") if target.endswith(".md") else target
            resolved = (Path(page_rel).parent / target).as_posix() if target else page_rel
            _ = resolved
            return f'href="{out}{anchor}"'
        slug = single_slugs.get(target, single_slugs.get("index.md", "index"))
        return f'href="{slug}.html{anchor}" if False else "#slug-{slug}{anchor}"'
    return re.sub(r'href="([^"]+?\.md)(#[^"]+)?"', lambda m: _rewrite_single(m, mode, single_slugs, page_rel), html)


def _rewrite_single(m, mode, single_slugs, page_rel):
    href, anchor = m.group(1), m.group(2) or ""
    if href.startswith(("http", "img/")):
        return m.group(0)
    if mode == "multi":
        return 'href="%s.html%s"' % (href[:-3], anchor)
    target = (Path(page_rel).parent / href).as_posix() if href else page_rel
    slug = single_slugs.get(target)
    return 'href="#slug-%s%s"' % (slug, anchor) if slug else m.group(0)


def slugify(rel):
    return re.sub(r"[^a-z0-9]+", "-", rel.lower()).strip("-")


def build_multi(lang):
    cfg = LANGS[lang]
    src, outdir = cfg["src"], OUTBASE / ("html-" + lang)
    pages = [p for p in PAGE_ORDER if (src / p).exists()]
    pages += [str(p.relative_to(src)) for p in sorted(src.rglob("*.md"))
              if str(p.relative_to(src)) not in pages]
    pages = [p for p in pages if not p.startswith("img/")]
    for rel in pages:
        depth = "../" * rel.count("/")
        text = (src / rel).read_text(encoding="utf-8")
        html = md_to_html(text)
        html = rewrite_links(html, rel, "multi", {})
        html = re.sub(r'(src="|href=")img/', lambda m: m.group(1) + depth + 'img/', html)
        counterpart = None
        other_src = LANGS[LANGS[lang]["switch_to"]]["src"]
        if (other_src / rel).exists():
            counterpart = depth + "../html-%s/%s.html" % (LANGS[lang]["switch_to"], rel[:-3])
        depth = "../" * (rel.count("/") )
        labels = NAV_LABELS.get(lang, {})
        nav_items = []
        for other_rel in pages:
            cls = ' class="current"' if other_rel == rel else ""
            label = labels.get(other_rel, Path(other_rel).stem.replace("-", " ").replace("_", " ").title())
            nav_items.append(f'<a{cls} href="{depth}{other_rel[:-3]}.html">{label}</a>')
        side = "".join(
            f'<h3>{t}</h3>{"".join(nav_items[a:b if b is not None else len(nav_items)])}'
            for t, a, b in GROUP_NAMES.get(lang, [("Menu", 0, None)]))
        doc = f"""<!doctype html><html lang="{lang}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">{THEME_JS}
<title>{Path(rel).stem.replace('-', ' ').title()} — {cfg['title']}</title>{MERMAID_JS}<style>{CSS}</style></head>
<body>{langbar(lang, counterpart)}<div class="wrap"><nav class="side">{side}</nav>
<main class="content">{html}</main></div></body></html>"""
        dest = outdir / (rel[:-3] + ".html")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(doc, encoding="utf-8")
    # copy images
    copy_imgs(src, outdir)
    return outdir


def build_single(lang):
    cfg = LANGS[lang]
    src, outdir = cfg["src"], OUTBASE / ("html-" + lang)
    pages = [p for p in PAGE_ORDER if (src / p).exists()]
    single_slugs = {rel: slugify(rel) for rel in pages}
    chunks, toc = [], []
    for rel in pages:
        text = (src / rel).read_text(encoding="utf-8")
        html = md_to_html(text)
        html = rewrite_links(html, rel, "single", single_slugs)
        chunks.append(f'<div id="slug-{single_slugs[rel]}">{html}<hr></div>')
        label = NAV_LABELS.get(lang, {}).get(rel, Path(rel).stem.replace("-", " ").title())
        toc.append(f'<a href="#slug-{single_slugs[rel]}">{label}</a>')
    other = "es" if lang == "en" else "en"
    counterpart = "../html-%s/single-%s.html" % (other, other)
    side = "".join(toc)
    doc = f"""<!doctype html><html lang="{lang}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">{THEME_JS}
<title>{cfg['title']}</title>{MERMAID_JS}<style>{CSS}</style></head><body>{langbar(lang, counterpart)}
<div class="wrap"><nav class="side"><h3>Contents</h3>{side}</nav>
<main class="content single">{"".join(chunks)}</main></div></body></html>"""
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / ("single-" + lang + ".html")).write_text(doc, encoding="utf-8")
    copy_imgs(src, outdir)
    return outdir


def copy_imgs(src, outdir):
    import shutil
    imgsrc = src / "img"
    if imgsrc.exists():
        (outdir / "img").mkdir(parents=True, exist_ok=True)
        for img in imgsrc.glob("*.png"):
            shutil.copy(img, outdir / "img" / img.name)


def build_root_redirect():
    """Root page: auto-redirect by browser language, fallback English."""
    (OUTBASE / "index.html").write_text(
        '<!doctype html><html><head><meta charset="utf-8">'
        '<script>location.replace(navigator.language.startsWith("es")'
        '? "html-es/index.html" : "html-en/index.html");</script>'
        '<meta http-equiv="refresh" content="0;url=html-en/index.html">'
        '</head><body><a href="html-en/index.html">English</a> · '
        '<a href="html-es/index.html">Español</a></body></html>', encoding="utf-8")
    (OUTBASE / ".nojekyll").write_text("", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--lang", choices=["en", "es", "both"], default="both")
    ap.add_argument("--mode", choices=["multi", "single", "both"], default="both")
    args = ap.parse_args()
    langs = ["en", "es"] if args.lang == "both" else [args.lang]
    for lang in langs:
        if not LANGS[lang]["src"].exists():
            print(f"[skip] {lang}: {LANGS[lang]['src']} not found")
            continue
        modes = ["multi", "single"] if args.mode == "both" else [args.mode]
        for mode in modes:
            out = build_single(lang) if mode == "single" else build_multi(lang)
            print(f"[ok] {lang}/{mode} → {out}")
    if args.lang == "both":
        build_root_redirect()
        print("[ok] root redirect → " + str(OUTBASE / "index.html"))


if __name__ == "__main__":
    main()
.concept-map { margin:1.5rem 0 2.25rem; padding:1.25rem; border:1px solid var(--line);
  border-radius:14px; background:var(--soft); }
.concept-map-caption { display:flex; align-items:baseline; justify-content:space-between; gap:1rem;
  margin-bottom:1rem; padding-bottom:.75rem; border-bottom:1px solid var(--line); }
.concept-map-caption span,.concept-map-label { color:var(--muted); font-size:.68em; font-weight:750;
  letter-spacing:.08em; line-height:1.35; text-transform:uppercase; }
.concept-map-caption strong { font-size:1.05em; }
.concept-setup-map { display:grid; grid-template-columns:minmax(0,1fr) 4.5rem minmax(0,.9fr);
  align-items:center; gap:.8rem; }
.concept-origins { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:.65rem; }
.concept-node { min-width:0; padding:.85rem .95rem; border:1px solid var(--line); border-radius:10px;
  background:var(--bg); }
.concept-node strong { display:block; margin:.2rem 0; font-size:1.05em; line-height:1.3; }
.concept-node p { margin:.25rem 0 0; color:var(--muted); font-size:.88em; line-height:1.45; }
.concept-standalone { border-style:dashed; }
.concept-map-arrow { display:grid; justify-items:center; color:var(--brand); font-size:.72em; font-weight:700;
  text-align:center; }
.concept-map-arrow b { font-size:2rem; font-weight:400; line-height:1; }
.concept-meeting-node,.concept-identity-node { border-color:var(--brand); }
.concept-meeting-meta { display:flex; flex-wrap:wrap; gap:.4rem; margin-top:.55rem; }
.concept-meeting-meta span { padding:.2rem .5rem; border-radius:999px; background:var(--soft);
  color:var(--muted); font-size:.78em; }
.concept-map-rule { display:flex; align-items:center; gap:.7rem; margin:1.2rem 0 .75rem;
  color:var(--muted); font-size:.7em; font-weight:750; letter-spacing:.08em; text-transform:uppercase; }
.concept-map-rule::after { content:""; flex:1; border-top:1px solid var(--line); }
.concept-point-map { display:grid; gap:.7rem; }
.concept-case { display:grid; grid-template-columns:minmax(9rem,.7fr) 5rem minmax(0,1.3fr);
  align-items:center; gap:.65rem; }
.concept-case-participations { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:.65rem; }
.concept-participation { border-top:2px solid var(--brand); }
.concept-map-outputs { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:.65rem;
  margin-top:.8rem; }
.concept-output { min-width:0; padding:.8rem .95rem; border-inline-start:2px solid var(--brand);
  background:var(--bg); }
.concept-output strong { display:block; margin:.18rem 0; font-size:.95em; }
.concept-output p { margin:.2rem 0 0; color:var(--muted); font-size:.84em; line-height:1.45; }
.object-diagram { display:flex; align-items:center; gap:.55rem; margin:.8rem 0 1.5rem;
  padding:.65rem .75rem; border-inline-start:2px solid var(--line); border-radius:0 8px 8px 0;
  background:var(--soft); }
.object-diagram-node { flex:1 1 0; min-width:0; padding:.5rem .6rem; border:1px solid var(--line);
  border-radius:8px; background:var(--bg); }
.object-diagram-node strong { display:block; font-size:.84em; line-height:1.35; }
.object-diagram-node small { display:block; margin-top:.12rem; color:var(--muted); font-size:.76em; line-height:1.4; }
.object-diagram-record { border-color:var(--brand); }
.object-diagram-branches { display:grid; flex:1.5 1 0; grid-template-columns:repeat(2,minmax(0,1fr)); gap:.45rem; }
.object-diagram-arrow { flex:0 0 auto; color:var(--brand); font-size:1.15em; font-weight:700; }
  .guide-section { margin:2.75rem 0; }
  .guide-section-head { grid-template-columns:1fr; gap:.2rem; }
  .guide-section-head h2 { font-size:1.5em; }
  .workflow-illustration { padding:1rem; }
  .workflow-entry { grid-template-columns:minmax(0,1fr); }
  .workflow-sources { grid-template-columns:repeat(2,minmax(0,1fr)); }
  .workflow-merge { transform:rotate(90deg); line-height:1; }
  .workflow-stages { grid-template-columns:repeat(2,minmax(0,1fr)); gap:.65rem; }
  .workflow-stages li::after { display:none; }
  .workflow-continuity { grid-template-columns:1fr; gap:.75rem; }
  .concept-map { padding:1rem; }
  .concept-setup-map { grid-template-columns:minmax(0,1fr); }
  .object-diagram { display:grid; grid-template-columns:minmax(0,1fr); justify-items:stretch; }
  .object-diagram-node { width:100%; }
  .object-diagram-arrow { justify-self:center; transform:rotate(90deg); }
  .object-diagram-branches { width:100%; }
  .concept-map-arrow { display:flex; flex-direction:column; align-items:center; justify-content:center; }
  .concept-map-arrow b { transform:rotate(90deg); }
  .guide-library-grid { grid-template-columns:1fr; gap:1.5rem; }
  .role-row { grid-template-columns:2rem minmax(0,1fr); gap:.45rem .75rem; }
  .role-action { grid-column:2; }
  .workflow-illustration { padding:.7rem; }
  .workflow-sources { grid-template-columns:minmax(0,1fr); }
  .workflow-merge { height:1.6rem; }
  .workflow-stages { grid-template-columns:minmax(0,1fr); gap:.4rem; margin-top:.9rem; }
  .workflow-stages li { padding:.7rem .8rem .8rem 3.2rem; border-top:0; border-inline-start:2px solid var(--line); }
  .workflow-stages li:not(:last-child)::after { display:block; top:auto; right:auto; bottom:-.45rem; left:.8rem;
    width:0; height:.5rem; border-top:0; border-left:1px solid var(--brand); }
  .workflow-step-number { position:absolute; top:.72rem; left:.55rem; width:1.8rem; height:1.8rem; margin:0; }
  .workflow-continuity { padding:.8rem; }
  .workflow-meeting-pair { grid-template-columns:minmax(0,1fr); }
  .workflow-carry b { transform:rotate(90deg); }
  .concept-map { padding:.7rem; }
  .concept-map-caption { display:block; }
  .concept-map-caption strong { display:block; margin-top:.2rem; }
  .concept-origins,.concept-case,.concept-case-participations,.concept-map-outputs { grid-template-columns:minmax(0,1fr); }
  .object-diagram-branches { grid-template-columns:minmax(0,1fr); }
