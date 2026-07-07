import base64
import json
import fitz  # PyMuPDF
from PIL import Image
from io import BytesIO
from docx import Document
from docx.shared import RGBColor, Inches
from openai import OpenAI

def encode_image(img):
    buffered = BytesIO()
    img.save(buffered, format="JPEG")
    return base64.b64encode(buffered.getvalue()).decode('utf-8')

def extract_pages(file_bytes, ext):
    images = []
    
    if ext == '.pdf':
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            pix = page.get_pixmap(dpi=300)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            images.append(img)
    elif ext in ['.png', '.jpg', '.jpeg']:
        img = Image.open(BytesIO(file_bytes)).convert('RGB')
        img.thumbnail((2000, 2000))
        images.append(img)
        
    return images

def process_exam_paper(file_bytes, ext, api_key, include_images):
    client = OpenAI(api_key=api_key)
    images = extract_pages(file_bytes, ext)
    doc = Document()
    
    for i, img in enumerate(images):
        if include_images:
            img_copy = img.copy()
            img_copy.thumbnail((600, 600))
            img_byte_arr = BytesIO()
            img_copy.save(img_byte_arr, format='JPEG')
            img_byte_arr.seek(0)
            doc.add_picture(img_byte_arr, width=Inches(6.0))
            
        base64_image = encode_image(img)
        
        response = client.chat.completions.create(
            model="gpt-4o",
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": "You are a transcriber converting scanned exam papers. Return a JSON object with a 'blocks' array. Each block must have 'type' ('printed' for standard question text, 'handwritten' for student answers/working) and 'text'. Include crossed out text wrapped in ~~. Describe sketches in brackets."
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Transcribe this exam page."},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                    ]
                }
            ],
            max_tokens=4000
        )
        
        try:
            content = json.loads(response.choices[0].message.content)
            blocks = content.get('blocks', [])
            for block in blocks:
                p = doc.add_paragraph()
                run = p.add_run(block.get('text', ''))
                if block.get('type') == 'handwritten':
                    run.font.color.rgb = RGBColor(0, 0, 255)
                    run.italic = True
                else:
                    run.font.color.rgb = RGBColor(0, 0, 0)
        except json.JSONDecodeError:
            doc.add_paragraph("[Error parsing transcription JSON structure for this page]")
            
        if i < len(images) - 1:
            doc.add_page_break()
            
    output_stream = BytesIO()
    doc.save(output_stream)
    output_stream.seek(0)
    return output_stream
