import re
from weasyprint import HTML


def is_cjk_text(text):
    return bool(re.search(r'[\u3000-\u9fff\uac00-\ud7af\uf900-\ufaff]', text))


def generate_pdf(data):
    pages = data["pages"]
    html_pages = [render_page(page) for page in pages]

    full_html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}

    @page {{
      margin: 56pt 56pt 56pt 56pt;
    }}

    body {{
      font-size: 11pt;
      line-height: 1.4;
      color: #000;
      text-align: left;
    }}

    .page {{
      page-break-after: always;
    }}

    .page:last-child {{
      page-break-after: avoid;
    }}

    .full-width {{
      width: 100%;
      margin-bottom: 12pt;
    }}

    .two-columns {{
      column-count: 2;
      column-gap: 24pt;
      width: 100%;
    }}

    .one-column {{
      width: 100%;
    }}

    p {{
      margin-bottom: 0.4em;
      text-align: left;
      break-inside: avoid;
    }}

    h1 {{ font-size: 1.6em; text-align: center; margin: 1.2em 0 0.8em; break-after: avoid; }}
    h2 {{ font-size: 1.3em; text-align: center; margin: 1em 0 0.6em; break-after: avoid; }}
    h3 {{ font-size: 1.1em; margin: 0.8em 0 0.4em; break-after: avoid; }}

    .block-image {{
      text-align: center;
      margin: 8pt 0;
      break-inside: avoid;
    }}

    .block-image img {{
      max-width: 100%;
      height: auto;
    }}

    /* Imagem de pagina inteira — sem margem, ocupa tudo */
    .block-image-fullpage {{
      position: relative;
      width: calc(100% + 112pt);
      margin-left: -56pt;
      margin-top: -56pt;
      margin-bottom: -56pt;
      text-align: center;
      break-before: always;
      break-after: always;
    }}

    .block-image-fullpage img {{
      width: 100%;
      height: auto;
      display: block;
    }}

    .block-image-full {{
      text-align: center;
      margin: 12pt 0;
      width: 100%;
    }}

    .block-image-full img {{
      max-width: 100%;
      height: auto;
    }}

    /* Links azuis como no original */
    a {{ color: #0000EE; text-decoration: underline; }}

    .cjk {{
      font-family: "Noto Sans CJK JP", "Noto Sans JP", sans-serif;
      line-height: 1.8;
      word-break: normal;
      overflow-wrap: break-word;
    }}
  </style>
</head>
<body>
{''.join(html_pages)}
</body>
</html>"""

    return HTML(string=full_html).write_pdf()


def render_page(page):
    num_columns = page.get("columns", 1)
    blocks = sorted(page.get("blocks", []), key=lambda b: b.get("order", 0))
    links = {l["text"]: l for l in page.get("links", []) if l.get("text")}

    # Detecta se a página é só imagem (fullpage)
    non_empty_text = [b for b in blocks if b.get("type") == "text" and b.get("content", "").strip()]
    images = [b for b in blocks if b["type"] in ("image", "image_ref")]

    if images and not non_empty_text:
        # Página só de imagem — renderiza fullpage
        img_html = "".join(render_block(b, links, fullpage=True) for b in images)
        return f'<div class="page">{img_html}</div>'

    if num_columns <= 1:
        content = render_blocks(blocks, links)
        return f'<div class="page"><div class="one-column">{content}</div></div>'

    col_orders = [b["order"] for b in blocks if b.get("column") is not None]
    first_col_order = min(col_orders) if col_orders else 0

    full_width_before = []
    full_width_after = []
    col_blocks = []

    for b in blocks:
        if b.get("column") is None:
            if b["order"] < first_col_order:
                full_width_before.append(b)
            else:
                full_width_after.append(b)
        else:
            col_blocks.append(b)

    col0 = sorted([b for b in col_blocks if b.get("column") == 0], key=lambda b: b["y0"])
    col1 = sorted([b for b in col_blocks if b.get("column") == 1], key=lambda b: b["y0"])
    ordered_col_blocks = col0 + col1

    before_html = render_blocks(full_width_before, links, full_width=True)
    after_html = render_blocks(full_width_after, links, full_width=True)
    col_html = render_blocks(ordered_col_blocks, links)

    return f"""<div class="page">
  {before_html}
  <div class="two-columns">{col_html}</div>
  {after_html}
</div>"""


def render_blocks(blocks, links, full_width=False):
    return "".join(render_block(b, links, full_width=full_width) for b in blocks)


def render_block(block, links, full_width=False, fullpage=False):
    if block["type"] in ("image", "image_ref"):
        if block["type"] == "image_ref":
            return ""  # sem imagem disponível
        ext = block.get("ext", "png")
        if fullpage:
            return f'<div class="block-image-fullpage"><img src="data:image/{ext};base64,{block["data"]}"></div>'
        if full_width:
            return f'<div class="block-image-full"><img src="data:image/{ext};base64,{block["data"]}"></div>'
        return f'<div class="block-image"><img src="data:image/{ext};base64,{block["data"]}"></div>'
    elif block["type"] == "text":
        return render_text_block(block, links)
    return ""


def render_text_block(block, links):
    spans = block.get("spans", [])
    content = block.get("content", "").strip()

    if not content:
        return ""

    sizes = [s["size"] for s in spans if s.get("size")]
    avg_size = sum(sizes) / len(sizes) if sizes else 11
    all_bold = all(s.get("bold") for s in spans)

    is_title = (
        avg_size > 14
        or (len(content) < 80 and all_bold and len(content.split()) <= 12)
    )

    # Estilo dominante do bloco
    dominant = spans[0] if spans else {}
    dom_font = dominant.get("font", "")
    dom_size = dominant.get("size", avg_size)
    dom_color = dominant.get("color", "#000000")

    p_style_parts = [
        f"font-size:{dom_size}pt",
        "text-align:left",
    ]
    if dom_font:
        p_style_parts.append(f'font-family:"{dom_font}", serif')
    if dom_color not in ("#000000", "#000", "#2b2e33"):
        p_style_parts.append(f"color:{dom_color}")

    # Monta inner HTML dos spans
    inner = ""
    for span in spans:
        text = escape_html(span["text"])
        if not text:
            continue

        span_style = []
        if span.get("font") and span["font"] != dom_font:
            span_style.append(f'font-family:"{span["font"]}", serif')
        if span.get("size") and abs(span["size"] - dom_size) > 0.5:
            span_style.append(f'font-size:{span["size"]}pt')
        if span.get("color") and span["color"] not in ("#000000", "#000", "#2b2e33") and span["color"] != dom_color:
            span_style.append(f'color:{span["color"]}')

        if span.get("bold") and span.get("italic"):
            text = f"<strong><em>{text}</em></strong>"
        elif span.get("bold"):
            text = f"<strong>{text}</strong>"
        elif span.get("italic"):
            text = f"<em>{text}</em>"

        if span_style:
            text = f'<span style="{";".join(span_style)}">{text}</span>'

        inner += text

    # Aplica link se existir
    if content in links:
        link = links[content]
        url = link.get("url", "#")
        inner = f'<a href="{escape_html(url)}">{inner}</a>'

    if is_title:
        level = "h1" if avg_size > 18 else "h2"
        return f"<{level}>{inner}</{level}>"

    cjk = is_cjk_text(content)
    cjk_class = ' class="cjk"' if cjk else ""
    p_style = ";".join(p_style_parts)

    # Rejunta linhas quebradas pelo PDF
    def rejoin_lines(text):
        if cjk:
            return [l.strip() for l in text.split("\n") if l.strip()]
        raw_lines = text.split("\n")
        result = []
        current = ""
        for line in raw_lines:
            line = line.strip()
            if not line:
                if current:
                    result.append(current)
                    current = ""
                continue
            if not current:
                current = line
            elif not any(current.endswith(p) for p in ('.', '!', '?', '"', '\u201d', '\u2026', ',')):
                current += " " + line
            else:
                result.append(current)
                current = line
        if current:
            result.append(current)
        return result

    lines = rejoin_lines(content)
    if len(lines) > 1:
        return "".join(f'<p{cjk_class} style="{p_style}">{escape_html(line)}</p>' for line in lines)

    return f'<p{cjk_class} style="{p_style}">{inner}</p>'


def escape_html(text):
    return (
        text
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
