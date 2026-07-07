import os
import uuid
import threading
from flask import Flask, render_template, request, jsonify, send_file
from werkzeug.utils import secure_filename
from ocr import process_exam_paper

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['OUTPUT_FOLDER'] = 'output'

# Ensure directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)

# In-memory job registry
jobs = {}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload():
    if 'files' not in request.files:
        return jsonify({'error': 'No files uploaded'}), 400
    
    # Extract the API key passed from the frontend
    api_key = request.form.get('api_key')
    if not api_key:
        return jsonify({'error': 'OpenAI API key is required'}), 400
        
    include_images = request.form.get('include_images') == 'true'
    files = request.files.getlist('files')
    job_ids = []
    
    for file in files:
        if file.filename == '':
            continue
            
        job_id = str(uuid.uuid4())
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], f"{job_id}_{filename}")
        file.save(filepath)
        
        # Register the job
        jobs[job_id] = {
            'status': 'processing', 
            'progress': 0, 
            'filename': filename, 
            'result': None, 
            'error': None
        }
        job_ids.append(job_id)
        
        # Pass the API key explicitly to the worker thread
        thread = threading.Thread(
            target=run_ocr_job,
            args=(job_id, filepath, filename, api_key, include_images)
        )
        thread.start()
        
    return jsonify({'job_ids': job_ids})

def run_ocr_job(job_id, filepath, filename, api_key, include_images):
    try:
        output_filename = f"{os.path.splitext(filename)[0]}_transcribed.docx"
        output_path = os.path.join(app.config['OUTPUT_FOLDER'], f"{job_id}_{output_filename}")
        
        def progress_callback(pct):
            jobs[job_id]['progress'] = pct
            
        # Process the document
        process_exam_paper(filepath, output_path, api_key, include_images, progress_callback)
        
        jobs[job_id]['status'] = 'completed'
        jobs[job_id]['progress'] = 100
        jobs[job_id]['result'] = f"{job_id}_{output_filename}"
        
        # Cleanup original upload
        if os.path.exists(filepath):
            os.remove(filepath)
            
    except Exception as e:
        jobs[job_id]['status'] = 'error'
        jobs[job_id]['error'] = str(e)

@app.route('/status/<job_id>')
def status(job_id):
    if job_id not in jobs:
        return jsonify({'error': 'Job not found'}), 404
    return jsonify(jobs[job_id])

@app.route('/download/<filename>')
def download(filename):
    filepath = os.path.join(app.config['OUTPUT_FOLDER'], secure_filename(filename))
    if not os.path.exists(filepath):
        return "File not found", 404
    return send_file(filepath, as_attachment=True)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)