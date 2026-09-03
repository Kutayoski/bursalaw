#!/usr/bin/env python3
"""Build the static BURSALAW blog from Markdown sources without dependencies."""

from __future__ import annotations

import ast
import html
import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content" / "blog"
SITE_URL = "https://bursalaw.com"


def slugify(value: str) -> str:
    table = str.maketrans({"ı": "i", "İ": "i", "ş": "s", "Ş": "s", "ğ": "g", "Ğ": "g", "ü": "u", "Ü": "u", "ö": "o", "Ö": "o", "ç": "c", "Ç": "c"})
    value = unicodedata.normalize("NFKD", value.translate(table)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", value).strip("-")


def parse_value(raw: str):
    raw = raw.strip()
    if raw.startswith("[") and raw.endswith("]"):
        try:
            return ast.literal_eval(raw)
        except (SyntaxError, ValueError):
            return [part.strip().strip('"\'') for part in raw[1:-1].split(",") if part.strip()]
    return raw.strip('"\'')


def parse_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---\n"):
        return {}, text
    front, body = text[4:].split("\n---\n", 1)
    data: dict[str, object] = {}
    active_list: str | None = None
    for line in front.splitlines():
        if line.startswith("  - ") and active_list:
            data.setdefault(active_list, []).append(parse_value(line[4:]))
            continue
        match = re.match(r"^([a-zA-Z_]+):\s*(.*)$", line)
        if not match:
            continue
        key, raw = match.groups()
        if raw:
            data[key] = parse_value(raw)
            active_list = None
        else:
            data[key] = []
            active_list = key
    return data, body.strip()


def parse_legacy_metadata(text: str) -> tuple[dict, str]:
    """Read the labelled metadata used by the newer KVKK draft files."""
    labels = {
        "SEO başlığı": "seo_basligi",
        "Meta açıklaması": "meta_aciklamasi",
        "Önerilen URL": "onerilen_url",
        "Birincil anahtar kelime": "birincil_anahtar_kelime",
        "İkincil sorgular": "ikincil_sorgular",
    }
    data: dict[str, object] = {}
    body_lines: list[str] = []
    for line in text.splitlines():
        matched = False
        for label, key in labels.items():
            prefix = f"{label}:"
            if line.startswith(prefix):
                value = line[len(prefix):].strip()
                data[key] = [part.strip() for part in value.split(";") if part.strip()] if key == "ikincil_sorgular" else value
                matched = True
                break
        if not matched:
            body_lines.append(line)

    checked = re.search(r"^Son hukuki kontrol tarihi:\s*(.+)$", text, re.MULTILINE)
    checked_label = checked.group(1).strip() if checked else "2 Eylül 2026"
    month_numbers = {
        "Ocak": "01", "Şubat": "02", "Mart": "03", "Nisan": "04",
        "Mayıs": "05", "Haziran": "06", "Temmuz": "07", "Ağustos": "08",
        "Eylül": "09", "Ekim": "10", "Kasım": "11", "Aralık": "12",
    }
    date_match = re.fullmatch(r"(\d{1,2})\s+(\S+)\s+(\d{4})", checked_label)
    if date_match and date_match.group(2) in month_numbers:
        published = f"{date_match.group(3)}-{month_numbers[date_match.group(2)]}-{int(date_match.group(1)):02d}"
    else:
        published = "2026-09-02"

    article_path = str(data.get("onerilen_url", ""))
    if article_path.startswith("/icra-hukuku/"):
        area = "İcra Hukuku"
    elif article_path.startswith("/kvkk/"):
        area = "KVKK"
    else:
        area = "Hukuk"
    data.update({
        "son_hukuki_kontrol": checked_label,
        "yayin_tarihi": published,
        "hukuk_alani": area,
        "yayin_durumu": "Yayında",
    })
    return data, "\n".join(body_lines).strip()


@dataclass
class Article:
    source: Path
    meta: dict
    markdown: str
    title: str
    description: str
    path: str
    keyword: str
    checked: str
    published: str
    area: str
    order: int

    @property
    def canonical(self) -> str:
        return f"{SITE_URL}{self.path}/"

    @property
    def output(self) -> Path:
        return ROOT / self.path.lstrip("/") / "index.html"


def load_articles() -> list[Article]:
    articles: list[Article] = []
    for source in sorted(CONTENT.glob("[0-9][0-9]-*.md")):
        raw = source.read_text(encoding="utf-8")
        meta, body = parse_frontmatter(raw)
        if not meta:
            meta, body = parse_legacy_metadata(raw)
        h1 = re.search(r"^#\s+(.+)$", body, re.MULTILINE)
        if not h1:
            raise ValueError(f"H1 bulunamadı: {source}")
        order_match = re.match(r"(\d+)-", source.name)
        path = str(meta.get("onerilen_url", "")).rstrip("/")
        if not path.startswith("/"):
            raise ValueError(f"Geçersiz URL: {source}")
        articles.append(Article(
            source=source,
            meta=meta,
            markdown=body,
            title=h1.group(1).strip(),
            description=str(meta.get("meta_aciklamasi", "")),
            path=path,
            keyword=str(meta.get("birincil_anahtar_kelime", "Miras hukuku")),
            checked=str(meta.get("son_hukuki_kontrol", "1 Eylül 2026")),
            published=str(meta.get("yayin_tarihi", "2026-09-01")),
            area=str(meta.get("hukuk_alani", "Miras Hukuku")),
            order=int(order_match.group(1)) if order_match else 999,
        ))
    return articles


def inline(text: str) -> str:
    placeholders: list[str] = []

    def keep_link(match: re.Match) -> str:
        label = html.escape(match.group(1), quote=False)
        href = html.escape(match.group(2), quote=True)
        external = urlparse(match.group(2)).scheme in {"http", "https"}
        attrs = ' target="_blank" rel="noopener noreferrer"' if external else ""
        placeholders.append(f'<a href="{href}"{attrs}>{label}</a>')
        return f"\x00{len(placeholders)-1}\x00"

    text = re.sub(r"\[([^]]+)]\(([^)]+)\)", keep_link, text)
    text = html.escape(text, quote=False)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    for index, value in enumerate(placeholders):
        text = text.replace(f"\x00{index}\x00", value)
    return text


def normalized_title(value: str) -> str:
    value = value.strip().strip("“”\"'")
    value = re.sub(r"^(sonraki döngü|ilgili yazı):\s*", "", value, flags=re.I)
    return slugify(value)


def resolve_related(label: str, articles: list[Article]) -> Article | None:
    needle = normalized_title(label)
    if len(needle) < 8:
        return None
    best: Article | None = None
    best_score = 0
    for article in articles:
        candidates = [normalized_title(article.title), normalized_title(str(article.meta.get("seo_basligi", "")))]
        for candidate in candidates:
            if needle == candidate:
                return article
            words_a, words_b = set(needle.split("-")), set(candidate.split("-"))
            score = len(words_a & words_b)
            if score > best_score and score >= 4:
                best, best_score = article, score
    return best


def render_markdown(article: Article, articles: list[Article]) -> tuple[str, list[tuple[int, str, str]], list[dict]]:
    lines = article.markdown.splitlines()
    blocks: list[str] = []
    toc: list[tuple[int, str, str]] = []
    faqs: list[dict] = []
    paragraph: list[str] = []
    list_items: list[tuple[bool, str]] = []
    lead_done = False
    current_h2 = ""
    faq_question: str | None = None

    def flush_paragraph() -> None:
        nonlocal paragraph, lead_done, faq_question
        if not paragraph:
            return
        raw = " ".join(part.strip() for part in paragraph)
        cls = ' class="lead"' if not lead_done else ""
        blocks.append(f"<p{cls}>{inline(raw)}</p>")
        if not lead_done:
            lead_done = True
        if faq_question and slugify(current_h2) == "sik-sorulan-sorular":
            faqs.append({"@type": "Question", "name": faq_question, "acceptedAnswer": {"@type": "Answer", "text": re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", inline(raw)))}})
            faq_question = None
        paragraph = []

    def flush_list() -> None:
        nonlocal list_items
        if not list_items:
            return
        ordered = list_items[0][0]
        tag = "ol" if ordered else "ul"
        items: list[str] = []
        for _, raw in list_items:
            item_html = inline(raw)
            if slugify(current_h2) in {"ic-baglanti-onerileri", "ilgili-yazilara-ic-baglanti-onerileri"}:
                target = resolve_related(re.sub(r"^[“\"]|[”\"]$", "", raw), articles)
                if target and target.path != article.path:
                    display = raw.strip().replace("“", "").replace("”", "").replace('"', "")
                    item_html = f'<a href="{html.escape(target.path, quote=True)}/">{html.escape(display, quote=False)}</a>'
            items.append(f"<li>{item_html}</li>")
        blocks.append(f"<{tag}>" + "".join(items) + f"</{tag}>")
        list_items = []

    for line in lines:
        if line.startswith("# "):
            continue
        heading = re.match(r"^(##|###)\s+(.+)$", line)
        unordered = re.match(r"^-\s+(.+)$", line)
        ordered = re.match(r"^\d+\.\s+(.+)$", line)
        if heading:
            flush_paragraph(); flush_list()
            level = 2 if heading.group(1) == "##" else 3
            title = heading.group(2).strip()
            anchor = slugify(title)
            if level == 2:
                current_h2 = title
            elif slugify(current_h2) == "sik-sorulan-sorular":
                faq_question = title
            toc.append((level, title, anchor))
            blocks.append(f'<h{level} id="{anchor}">{inline(title)}<a class="anchor" href="#{anchor}" aria-label="Bu başlığa bağlantı">#</a></h{level}>')
        elif unordered or ordered:
            flush_paragraph()
            item = (False, unordered.group(1)) if unordered else (True, ordered.group(1))
            if list_items and list_items[-1][0] != item[0]:
                flush_list()
            list_items.append(item)
        elif not line.strip():
            flush_paragraph(); flush_list()
        else:
            paragraph.append(line)
    flush_paragraph(); flush_list()
    return "\n".join(blocks), toc, faqs


def nav(path_prefix: str = "") -> str:
    return f'''<nav class="site-nav" aria-label="Ana menü">
  <a class="brand" href="{path_prefix}/"><span>BURSA</span><b>LAW</b></a>
  <div class="nav-links">
    <a href="{path_prefix}/#alanlar">Alanlar</a>
    <a href="{path_prefix}/blog/">Bilgi Notları</a>
    <a href="{path_prefix}/#iletisim">İletişim</a>
  </div>
</nav>'''


def footer() -> str:
    return '''<footer class="site-footer">
  <div><span class="eyebrow">Bir dosyanız mı var?</span><a class="email" href="mailto:info@bursalaw.com">info@bursalaw.com</a></div>
  <div class="footer-meta"><span>Bursa, Türkiye</span><span>Pzt–Cum · 09.00–18.00</span><span>© 2026 BURSALAW</span></div>
</footer>'''


def page_head(title: str, description: str, canonical: str, kind: str = "website", json_ld: list[dict] | None = None) -> str:
    schemas = "\n".join(f'<script type="application/ld+json">{html.escape(json.dumps(item, ensure_ascii=False), quote=False)}</script>' for item in (json_ld or []))
    return f'''<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{html.escape(title)}</title>
<meta name="description" content="{html.escape(description, quote=True)}">
<meta name="robots" content="index,follow,max-image-preview:large">
<link rel="canonical" href="{canonical}">
<meta property="og:locale" content="tr_TR">
<meta property="og:type" content="{kind}">
<meta property="og:title" content="{html.escape(title, quote=True)}">
<meta property="og:description" content="{html.escape(description, quote=True)}">
<meta property="og:url" content="{canonical}">
<meta property="og:site_name" content="BURSALAW">
<meta name="twitter:card" content="summary">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,300;0,9..144,400;0,9..144,600;1,9..144,400&family=Manrope:wght@300;400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/assets/blog.css">
{schemas}'''


def render_article(article: Article, articles: list[Article]) -> str:
    body, toc, faqs = render_markdown(article, articles)
    toc_html = "".join(f'<li class="level-{level}"><a href="#{anchor}">{html.escape(title)}</a></li>' for level, title, anchor in toc if level == 2)
    same_area = [a for a in articles if a.path != article.path and a.area == article.area]
    related_pool = same_area or [a for a in articles if a.path != article.path]
    related = sorted(related_pool, key=lambda a: abs(a.order - article.order))[:3]
    related_html = "".join(f'<a class="related-card" href="{a.path}/"><span>{a.order:02d}</span><h3>{html.escape(a.title)}</h3><p>Yazıyı oku →</p></a>' for a in related)
    schemas = [
        {
            "@context": "https://schema.org", "@type": "Article",
            "headline": str(article.meta.get("seo_basligi", article.title)),
            "description": article.description, "inLanguage": "tr-TR",
            "datePublished": article.published, "dateModified": article.published,
            "mainEntityOfPage": article.canonical,
            "author": {"@type": "Organization", "name": "BURSALAW"},
            "publisher": {"@type": "Organization", "name": "BURSALAW", "url": SITE_URL},
        },
        {
            "@context": "https://schema.org", "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "Ana Sayfa", "item": f"{SITE_URL}/"},
                {"@type": "ListItem", "position": 2, "name": "Bilgi Notları", "item": f"{SITE_URL}/blog/"},
                {"@type": "ListItem", "position": 3, "name": article.title, "item": article.canonical},
            ],
        },
    ]
    if faqs:
        schemas.append({"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": faqs})
    title = str(article.meta.get("seo_basligi", article.title))
    return f'''<!DOCTYPE html>
<html lang="tr">
<head>
{page_head(title, article.description, article.canonical, "article", schemas)}
</head>
<body>
<a class="skip-link" href="#icerik">İçeriğe geç</a>
{nav()}
<header class="article-hero">
  <div class="thread-field" aria-hidden="true"></div>
  <div class="hero-inner">
    <a class="breadcrumb" href="/blog/">Bilgi Notları / {html.escape(article.area)}</a>
    <h1>{html.escape(article.title)}</h1>
    <p>{html.escape(article.description)}</p>
    <div class="article-meta"><span>Son hukuki kontrol: {html.escape(article.checked)}</span><span>Yaklaşık {max(4, len(re.findall(r'\w+', article.markdown)) // 210)} dakika okuma</span></div>
  </div>
</header>
<main class="article-shell" id="icerik">
  <aside class="toc"><span class="eyebrow">Bu yazıda</span><ol>{toc_html}</ol></aside>
  <article class="prose">{body}
    <div class="legal-note"><strong>Bilgilendirme notu</strong><p>Bu metin genel hukuki bilgi amacıyla hazırlanmıştır. Somut uyuşmazlığın özellikleri, süreler ve başvuru yolu ayrıca değerlendirilmelidir.</p></div>
  </article>
</main>
<section class="related"><span class="eyebrow">İlgili bilgi notları</span><div class="related-grid">{related_html}</div></section>
{footer()}
<script src="/assets/blog.js" defer></script>
</body>
</html>'''


def render_index(articles: list[Article]) -> str:
    index_articles = sorted(articles, key=lambda a: (a.published, -a.order), reverse=True)
    area_label = " · ".join(dict.fromkeys(article.area for article in index_articles))
    cards = "".join(f'''<article class="blog-card" data-search="{html.escape((a.title + ' ' + a.keyword).casefold(), quote=True)}">
  <a href="{a.path}/">
    <div class="card-top"><span>{a.order:02d}</span><span>{html.escape(a.area)}</span></div>
    <h2>{html.escape(a.title)}</h2>
    <p>{html.escape(a.description)}</p>
    <div class="card-bottom"><span>{html.escape(a.checked)}</span><b>Oku →</b></div>
  </a>
</article>''' for a in index_articles)
    desc = "Türkiye'de farklı hukuk alanları hakkında güncel mevzuat ve doğrulanmış kararlarla hazırlanan BURSALAW bilgi notları."
    schema = [{"@context": "https://schema.org", "@type": "CollectionPage", "name": "BURSALAW Bilgi Notları", "url": f"{SITE_URL}/blog/", "inLanguage": "tr-TR"}]
    return f'''<!DOCTYPE html>
<html lang="tr">
<head>
{page_head("Hukuk Yazıları ve Bilgi Notları | BURSALAW", desc, f"{SITE_URL}/blog/", "website", schema)}
</head>
<body>
<a class="skip-link" href="#yazilar">Yazılara geç</a>
{nav()}
<header class="blog-hero">
  <div class="thread-field" aria-hidden="true"></div>
  <div class="hero-inner"><span class="eyebrow">Hukuki Bilgi · Güncel İçtihat</span><h1>Bilgi<br><em>notları.</em></h1><p>Soruyu geciktirmeden cevaplayan; mevzuat, süre ve kararları birlikte ele alan hukuk yazıları.</p></div>
</header>
<main class="blog-main" id="yazilar">
  <div class="blog-tools"><div><span class="eyebrow">{html.escape(area_label)}</span><h2>{len(articles)} güncel yazı</h2></div><label><span class="sr-only">Yazılarda ara</span><input id="blog-search" type="search" placeholder="Konu ara…" autocomplete="off"></label></div>
  <div class="blog-grid" id="blog-grid">{cards}</div>
  <p class="no-results" id="no-results" hidden>Bu aramayla eşleşen yazı bulunamadı.</p>
</main>
{footer()}
<script src="/assets/blog.js" defer></script>
</body>
</html>'''


def write_outputs(articles: list[Article]) -> None:
    blog_dir = ROOT / "blog"
    blog_dir.mkdir(parents=True, exist_ok=True)
    (blog_dir / "index.html").write_text(render_index(articles), encoding="utf-8")
    for article in articles:
        article.output.parent.mkdir(parents=True, exist_ok=True)
        article.output.write_text(render_article(article, articles), encoding="utf-8")

    latest = max(article.published for article in articles)
    urls = [(f"{SITE_URL}/", latest), (f"{SITE_URL}/blog/", latest)] + [
        (article.canonical, article.published) for article in articles
    ]
    sitemap = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "\n".join(
        f"  <url><loc>{html.escape(url)}</loc><lastmod>{lastmod}</lastmod></url>" for url, lastmod in urls
    ) + "\n</urlset>\n"
    (ROOT / "sitemap.xml").write_text(sitemap, encoding="utf-8")
    (ROOT / "robots.txt").write_text(f"User-agent: *\nAllow: /\n\nSitemap: {SITE_URL}/sitemap.xml\n", encoding="utf-8")


if __name__ == "__main__":
    items = load_articles()
    if len(items) < 20:
        raise SystemExit(f"En az 20 yazı bekleniyordu, {len(items)} bulundu.")
    write_outputs(items)
    print(f"{len(items)} yazı ve blog ana sayfası üretildi.")
