from weasyprint import HTML


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
      line-height: 1.6;
      color: #000;
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

    .block-image-full {{
      text-align: center;
      margin: 12pt 0;
      width: 100%;
    }}

    .block-image-full img {{
      max-width: 100%;
      height: auto;
    }}

    a {{ color: inherit; text-decoration: underline; }}
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

    if num_columns <= 1:
        content = render_blocks(blocks, links)
        return f'<div class="page"><div class="one-column">{content}</div></div>'

    full_width_before = []
    full_width_after = []
    col_blocks = []
    col_orders = [b["order"] for b in blocks if b.get("column") is not None]
    first_col_order = min(col_orders) if col_orders else 0
    last_col_order = max(col_orders) if col_orders else 0

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
    html = ""
    for block in blocks:
        if block["type"] == "image":
            css_class = "block-image-full" if full_width else "block-image"
            ext = block.get("ext", "png")
            html += f'<div class="{css_class}"><img src="data:image/{ext};base64,{block["data"]}"></div>'
        elif block["type"] == "text":
            html += render_text_block(block, links)
    return html


def render_text_block(block, links):
    spans = block.get("spans", [])
    content = block.get("content", "").strip()

    if not content:
        return ""

    if not spans:
        return f"<p>{escape_html(content)}</p>"

    sizes = [s["size"] for s in spans if s.get("size")]
    avg_size = sum(sizes) / len(sizes) if sizes else 11
    all_bold = all(s.get("bold") for s in spans)

    is_title = (
        avg_size > 14
        or (len(content) < 80 and all_bold and len(content.split()) <= 12)
    )

    inner = ""
    for span in spans:
        text = escape_html(span["text"])
        if not text:
            continue

        style_parts = []
        if span.get("font"):
            style_parts.append(f'font-family:"{span["font"]}", serif')
        if span.get("size") and abs(span["size"] - avg_size) > 1:
            style_parts.append(f'font-size:{span["size"]}pt')
        if span.get("color") and span["color"] not in ("#000000", "#000", "#2b2e33"):
            style_parts.append(f'color:{span["color"]}')

        if span.get("bold") and span.get("italic"):
            text = f"<strong><em>{text}</em></strong>"
        elif span.get("bold"):
            text = f"<strong>{text}</strong>"
        elif span.get("italic"):
            text = f"<em>{text}</em>"

        if style_parts:
            text = f'<span style="{";".join(style_parts)}">{text}</span>'

        inner += text

    if content in links:
        link = links[content]
        url = link.get("url", "#")
        inner = f'<a href="{escape_html(url)}">{inner}</a>'

    if is_title:
        level = "h1" if avg_size > 18 else "h2"
        return f"<{level}>{inner}</{level}>"

    # Split content by newlines — each line becomes its own paragraph
    lines = content.split("\n")
    if len(lines) > 1:
        return "".join(f"<p>{escape_html(line.strip())}</p>" for line in lines if line.strip())

    return f"<p>{inner}</p>"


def escape_html(text):
    return (
        text
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
