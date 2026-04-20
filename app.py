from flask import Flask, request, jsonify, send_file
import io
from extractor import extract_pdf
from generator import generate_pdf

app = Flask(__name__)

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "up"})

@app.route('/extract', methods=['POST'])
def extract():
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400
    pdf_bytes = request.files['file'].read()
    try:
        result = extract_pdf(pdf_bytes)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/generate', methods=['POST'])
def generate():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No JSON provided"}), 400
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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
