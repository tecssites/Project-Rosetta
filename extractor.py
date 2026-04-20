import fitz
import base64


def extract_pdf(pdf_bytes):
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages = []
    for page_num in range(len(doc)):
        pages.append(extract_page(doc[page_num], doc))
    doc.close()
    return {"pages": pages}


def extract_page(page, doc):
    width = page.rect.width
    height = page.rect.height

    raw_blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]

    text_blocks = []
    for block in raw_blocks:
        if block["type"] == 0:
            processed = process_text_block(block)
            if processed:
                text_blocks.append(processed)

    images = extract_images(page, doc)
    links = extract_links(page)
    columns = detect_columns(text_blocks, width)

    for block in text_blocks:
        block["column"] = assign_column(block["x0"], columns)

    # Images that span full width get column=None
    for img in images:
        img_width = img["x1"] - img["x0"]
        if img_width > width * 0.6:
            img["column"] = None
        else:
            img["column"] = assign_column(img["x0"], columns)

    all_blocks = text_blocks + images
    all_blocks.sort(key=lambda b: (round(b["y0"] / 10), b.get("column") or 0, b["x0"]))

    for i, block in enumerate(all_blocks):
        block["order"] = i

    return {
        "width": round(width, 2),
        "height": round(height, 2),
        "columns": len(columns),
        "column_bounds": [[round(c[0], 2), round(c[1], 2)] for c in columns],
        "blocks": all_blocks,
        "links": links,
    }


def process_text_block(block):
    spans_data = []
    full_text = ""

    for line in block["lines"]:
        line_text = ""
        for span in line["spans"]:
            text = span["text"]
            if not text:
                continue

            color_int = span["color"]
            r = (color_int >> 16) & 0xFF
            g = (color_int >> 8) & 0xFF
            b = color_int & 0xFF
            color_hex = f"#{r:02x}{g:02x}{b:02x}"

            flags = span["flags"]
            bold = bool(flags & (1 << 4))
            italic = bool(flags & (1 << 1))

            spans_data.append({
                "text": text,
                "font": span["font"],
                "size": round(span["size"], 2),
                "bold": bold,
                "italic": italic,
                "color": color_hex,
            })
            line_text += text

        full_text += line_text + "\n"

    full_text = full_text.strip()
    if not full_text:
        return None

    return {
        "type": "text",
        "x0": round(block["bbox"][0], 2),
        "y0": round(block["bbox"][1], 2),
        "x1": round(block["bbox"][2], 2),
        "y1": round(block["bbox"][3], 2),
        "content": full_text,
        "spans": spans_data,
        "column": 0,
    }


def extract_images(page, doc):
    images = []
    seen_xrefs = set()

    for img in page.get_images(full=True):
        xref = img[0]
        if xref in seen_xrefs:
            continue
        seen_xrefs.add(xref)

        rects = page.get_image_rects(xref)
        if not rects:
            continue

        try:
            base_image = doc.extract_image(xref)
            img_data = base64.b64encode(base_image["image"]).decode()
            ext = base_image["ext"]
        except Exception:
            continue

        for rect in rects:
            images.append({
                "type": "image",
                "x0": round(rect.x0, 2),
                "y0": round(rect.y0, 2),
                "x1": round(rect.x1, 2),
                "y1": round(rect.y1, 2),
                "width": round(rect.width, 2),
                "height": round(rect.height, 2),
                "data": img_data,
                "ext": ext,
                "column": None,
                "order": 0,
            })

    return images


def extract_links(page):
    links = []
    for link in page.get_links():
        rect = fitz.Rect(link["from"])
        text = page.get_textbox(rect).strip()

        link_data = {
            "text": text,
            "rect": [round(x, 2) for x in list(link["from"])],
            "kind": link.get("kind", 0),
        }

        if link.get("uri"):
            link_data["url"] = link["uri"]
        if link.get("page") is not None:
            link_data["page"] = link["page"]

        links.append(link_data)

    return links


def detect_columns(text_blocks, page_width):
    if not text_blocks:
        return [(0, page_width)]

    # Blocks that span more than 60% of page width = full width
    full_width = [b for b in text_blocks if (b["x1"] - b["x0"]) > page_width * 0.6]

    if len(full_width) > len(text_blocks) * 0.4:
        return [(0, page_width)]

    mid = page_width / 2
    left = [b for b in text_blocks if b["x0"] < mid * 0.7]
    right = [b for b in text_blocks if b["x0"] >= mid * 0.7]

    if not left or not right:
        return [(0, page_width)]

    # Find the gap between columns
    left_max_x = max(b["x1"] for b in left)
    right_min_x = min(b["x0"] for b in right)

    if right_min_x <= left_max_x:
        return [(0, page_width)]

    return [(0, left_max_x), (right_min_x, page_width)]


def assign_column(x0, columns):
    for i, (col_start, col_end) in enumerate(columns):
        if col_start - 10 <= x0 <= col_end + 10:
            return i
    return 0
