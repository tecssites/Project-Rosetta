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

    .layout-single {{
      width: 100%;
    }}

    .layout-two-columns {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      column-gap: 24pt;
      align-items: start;
    }}

    .column {{
      width: 100%;
    }}

    p {{
      margin-bottom: 0.5em;
      text-align: justify;
    }}

    p + p {{
      text-indent: 1.2em;
    }}

    h1 {{ font-size: 1.8em; text-align: center; margin: 1.5em 0 1em; }}
    h2 {{ font-size: 1.4em; text-align: center; margin: 1.2em 0 0.8em; }}
    h3 {{ font-size: 1.1em; margin: 1em 0 0.5em; }}

    .block-image {{
      text-align: center;
      margin: 12pt 0;
    }}

    .block-image img {{
      max-width: 100%;
      height: auto;
    }}

    .block-image-full {{
      text-align: center;
      margin: 16pt 0;
      grid-column: 1 / -1;
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
    columns = page.get("columns", 1)
    blocks = sorted(page.get("blocks", []), key=lambda b: b.get("order", 0))
    links = {l["text"]: l for l in page.get("links", []) if l.get("text")}

    if columns == 1:
        content = render_blocks(blocks, links)
        return f'<div class="page"><div class="layout-single">{content}</div></div>'
    else:
        col0_blocks = [b for b in blocks if b.get("column") == 0]
        col1_blocks = [b for b in blocks if b.get("column") == 1]
        full_blocks = [b for b in blocks if b.get("column") is None]

        col0_html = render_blocks(col0_blocks, links)
        col1_html = render_blocks(col1_blocks, links)
        full_html = render_blocks(full_blocks, links, full_width=True)

        return f"""<div class="page">
  {full_html}
  <div class="layout-two-columns">
    <div class="column">{col0_html}</div>
    <div class="column">{col1_html}</div>
  </div>
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

    # Dominant font size in block
    sizes = [s["size"] for s in spans if s.get("size")]
    avg_size = sum(sizes) / len(sizes) if sizes else 11
    all_bold = all(s.get("bold") for s in spans)

    is_title = (
        avg_size > 14
        or (len(content) < 80 and all_bold and len(content.split()) <= 12)
    )

    # Build inner HTML from spans
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
        if span.get("color") and span["color"] not in ("#000000", "#000"):
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

    # Re-attach links by matching text
    if content in links:
        link = links[content]
        url = link.get("url", "#")
        inner = f'<a href="{escape_html(url)}">{inner}</a>'

    if is_title:
        level = "h1" if avg_size > 18 else "h2"
        return f"<{level}>{inner}</{level}>"

    return f"<p>{inner}</p>"


def escape_html(text):
    return (
        text
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
