import os
from io import BytesIO
from flask import Flask, render_template, request, jsonify, send_file
from werkzeug.utils import secure_filename
from ocr import process_exam_paper

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload():
    if 'files' not in request.files:
        return jsonify({'error': 'No files uploaded'}), 400
    
    api_key = request.form.get('api_key')
    if not api_key:
        return jsonify({'error': 'OpenAI API key is required'}), 400
        
    include_images = request.form.get('include_images') == 'true'
    
    # We only process one file per request to avoid Vercel timeouts
    file = request.files.getlist('files')[0]  
    
    if file.filename == '':
        return jsonify({'error': 'Empty filename'}), 400
        
    try:
        # Read the file directly into memory
        file_bytes = file.read()
        filename = secure_filename(file.filename)
        ext = os.path.splitext(filename)[1].lower()
        
        # Process and get the Docx as a BytesIO stream
        docx_stream = process_exam_paper(file_bytes, ext, api_key, include_images)
        
        output_filename = f"{os.path.splitext(filename)[0]}_transcribed.docx"
        
        # Stream the file directly back to the user
        return send_file(
            docx_stream,
            as_attachment=True,
            download_name=output_filename,
            mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500
