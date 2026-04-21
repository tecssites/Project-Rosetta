import uuid
import time
import threading
from flask import Flask, request, jsonify, send_file
import io
from extractor import extract_pdf
from generator import generate_pdf

app = Flask(__name__)

# Memória interna: {job_id: {images, expires_at}}
_jobs = {}
_lock = threading.Lock()
JOB_TTL_SECONDS = 60 * 60  # 1 hora


def _cleanup_old_jobs():
    """Remove jobs expirados da memória."""
    while True:
        time.sleep(300)  # roda a cada 5 minutos
        now = time.time()
        with _lock:
            expired = [k for k, v in _jobs.items() if v['expires_at'] < now]
            for k in expired:
                del _jobs[k]


# Inicia limpeza em background
threading.Thread(target=_cleanup_old_jobs, daemon=True).start()


@app.route('/health', methods=['GET'])
def health():
    with _lock:
        job_count = len(_jobs)
    return jsonify({"status": "up", "active_jobs": job_count})


@app.route('/extract', methods=['POST'])
def extract():
    """
    Recebe o PDF, extrai texto + imagens.
    Guarda as imagens internamente.
    Devolve só o texto (leve) + job_id.
    """
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400

    pdf_bytes = request.files['file'].read()

    try:
        # Extrai tudo
        full_result = extract_pdf(pdf_bytes)

        # Gera um ID único para este job
        job_id = str(uuid.uuid4())

        # Separa imagens do texto
        images_store = {}  # {page_index: {block_index: image_data}}
        text_result = {"pages": []}

        for page_idx, page in enumerate(full_result["pages"]):
            text_page = {
                "width": page["width"],
                "height": page["height"],
                "columns": page["columns"],
                "column_bounds": page["column_bounds"],
                "links": page["links"],
                "blocks": []
            }

            images_store[page_idx] = {}

            for block_idx, block in enumerate(page["blocks"]):
                if block["type"] == "image":
                    # Guarda imagem internamente, só manda referência ao n8n
                    images_store[page_idx][block_idx] = {
                        "data": block["data"],
                        "ext": block.get("ext", "png"),
                        "width": block.get("width"),
                        "height": block.get("height"),
                    }
                    # No lugar da imagem, manda só uma referência leve
                    text_page["blocks"].append({
                        "type": "image_ref",
                        "page_index": page_idx,
                        "block_index": block_idx,
                        "x0": block["x0"],
                        "y0": block["y0"],
                        "x1": block["x1"],
                        "y1": block["y1"],
                        "column": block.get("column"),
                        "order": block.get("order", 0),
                    })
                else:
                    text_page["blocks"].append(block)

            text_result["pages"].append(text_page)

        # Salva imagens na memória
        with _lock:
            _jobs[job_id] = {
                "images": images_store,
                "expires_at": time.time() + JOB_TTL_SECONDS
            }

        # Devolve texto leve + job_id
        text_result["job_id"] = job_id
        return jsonify(text_result)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/generate', methods=['POST'])
def generate():
    """
    Recebe o JSON traduzido (com job_id).
    Reinjeta as imagens do job_id.
    Gera e devolve o PDF.
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "No JSON provided"}), 400

    job_id = data.get("job_id")

    # Reinjeta imagens se tiver job_id
    if job_id:
        with _lock:
            job = _jobs.get(job_id)

        if job:
            images_store = job["images"]
            for page_idx, page in enumerate(data["pages"]):
                restored_blocks = []
                for block in page["blocks"]:
                    if block.get("type") == "image_ref":
                        b_idx = block["block_index"]
                        p_idx = block["page_index"]
                        img = images_store.get(p_idx, {}).get(b_idx)
                        if img:
                            restored_blocks.append({
                                "type": "image",
                                "x0": block["x0"],
                                "y0": block["y0"],
                                "x1": block["x1"],
                                "y1": block["y1"],
                                "column": block.get("column"),
                                "order": block.get("order", 0),
                                "data": img["data"],
                                "ext": img["ext"],
                                "width": img["width"],
                                "height": img["height"],
                            })
                    else:
                        restored_blocks.append(block)
                page["blocks"] = restored_blocks

    try:
        pdf_bytes = generate_pdf(data)
        return send_file(
            io.BytesIO(pdf_bytes),
            mimetype='application/pdf',
            as_attachment=True,
            download_name='translated.pdf'
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/jobs', methods=['GET'])
def list_jobs():
    """Lista jobs ativos (útil para debug)."""
    with _lock:
        jobs = {
            k: {
                "expires_in": int(v["expires_at"] - time.time()),
                "pages_with_images": len(v["images"])
            }
            for k, v in _jobs.items()
        }
    return jsonify(jobs)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
