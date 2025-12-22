from flask import Flask, request, render_template, send_file, flash, Response, jsonify
import pandas as pd
import sqlite3
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import os
import uuid
import json

app = Flask(__name__)
app.secret_key = 'your_secret_key'
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Store progress data
progress_data = {}

@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload():
    file = request.files['file']
    task_id = request.form.get('task_id', str(uuid.uuid4()))
    
    if file and (file.filename.endswith('.csv') or file.filename.endswith('.txt')):
        filepath = os.path.join(UPLOAD_FOLDER, file.filename)
        file.save(filepath)
        
        try:
            # Initialize progress
            progress_data[task_id] = {'progress': 0, 'status': 'Processing', 'task_id': task_id}
            
            # Process CSV with progress tracking
            matches = process_csv(filepath, task_id)
            
            # Delete uploaded file after processing
            if os.path.exists(filepath):
                os.remove(filepath)
            
            if not matches:
                progress_data[task_id] = {'progress': 100, 'status': 'No matches found', 'task_id': task_id}
                return jsonify({'error': 'No matches found'}), 404
            
            # Generate PDF
            progress_data[task_id] = {'progress': 90, 'status': 'Generating PDF', 'task_id': task_id}
            pdf = generate_pdf(matches)
            progress_data[task_id] = {'progress': 100, 'status': 'Complete', 'task_id': task_id}
            
            return send_file(pdf, as_attachment=True, download_name='SNP_matches.pdf', mimetype='application/pdf')
        except Exception as e:
            # Delete uploaded file even on error
            if os.path.exists(filepath):
                os.remove(filepath)
            progress_data[task_id] = {'progress': 100, 'status': f'Error: {str(e)}', 'task_id': task_id}
            return jsonify({'error': str(e)}), 500
    return jsonify({'error': 'Invalid file. Please upload a CSV or TXT file.'}), 400

@app.route('/progress/<task_id>')
def progress(task_id):
    if task_id in progress_data:
        return jsonify(progress_data[task_id])
    return jsonify({'progress': 0, 'status': 'Starting...'})

def process_csv(csv_path, task_id=None):
    import csv
    # Detect delimiter and header
    with open(csv_path, 'r', encoding='utf-8') as f:
        lines = [line for line in f if not line.startswith('#') and line.strip()]
        sample = '\n'.join(lines[:10])
        sniffer = csv.Sniffer()
        delimiter = sniffer.sniff(sample).delimiter if lines else ','
    with open(csv_path, 'r', encoding='utf-8') as f:
        header_line = None
        for line in f:
            if not line.startswith('#') and line.strip():
                header_line = line.strip().split(delimiter)
                break
    if header_line and 'RSID' in header_line and 'RESULT' in header_line:
        df = pd.read_csv(csv_path, comment='#', delimiter=delimiter)
        snp_col = 'RSID'
        gen_col = 'RESULT'
    else:
        df = pd.read_csv(csv_path, comment='#', header=None, delimiter=delimiter)
        snp_col = 0
        gen_col = 3
    
    db_path = os.path.join(os.path.dirname(__file__), 'SNPdata.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    results = []
    seen_ids = set()  # Track unique entries to avoid duplicates
    total_rows = len(df)
    
    # Process in batches for better performance
    batch_size = 1000
    for batch_start in range(0, total_rows, batch_size):
        batch_end = min(batch_start + batch_size, total_rows)
        batch = df.iloc[batch_start:batch_end]
        
        # Collect SNP-Gen pairs for batch query
        snp_gen_pairs = []
        for idx, row in batch.iterrows():
            try:
                snp = row[snp_col]
                gen = row[gen_col]
                if pd.notna(snp) and pd.notna(gen):
                    snp_gen_pairs.append((str(snp), str(gen)))
            except Exception:
                continue
        
        # Update progress
        if task_id:
            progress_percent = int((batch_end) / total_rows * 80)
            progress_data[task_id] = {'progress': progress_percent, 'status': f'Processing row {batch_end}/{total_rows}', 'task_id': task_id}
        
        # Batch query using IN clause
        if snp_gen_pairs:
            placeholders = ','.join(['(?,?)'] * len(snp_gen_pairs))
            flat_params = [item for pair in snp_gen_pairs for item in pair]
            
            query = f"""
                SELECT DISTINCT * FROM snp_data 
                WHERE (SNP, Gen) IN (VALUES {placeholders})
                AND Color='Red' 
                AND LOWER(Summary) NOT IN ('normal', 'normal risk', 'common')
            """
            cursor.execute(query, flat_params)
            batch_results = cursor.fetchall()
            
            # Add only unique results (avoid duplicates based on SNP+Gen+Summary)
            for result in batch_results:
                # Create unique key from SNP, Gen, and Summary
                unique_key = (result[1], result[2], result[3])  # (SNP, Gen, Summary)
                if unique_key not in seen_ids:
                    seen_ids.add(unique_key)
                    results.append(result)
    
    conn.close()
    return results

def generate_pdf(matches):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    y = height - 40
    c.setFont('Helvetica-Bold', 16)
    c.drawString(40, y, 'SNP Report')
    y -= 30
    c.setFont('Helvetica', 12)
    c.drawString(40, y, f'Number of matching SNPs found: {len(matches)}')
    y -= 30
    
    max_width = width - 80  # Leave margins on both sides
    
    for match in matches:
        # match format: (id, SNP, Gen, Summary, Color)
        snp_header = f"{match[1]} | {match[2]}"
        summary = match[3]
        
        # Draw SNP header
        c.drawString(40, y, snp_header)
        y -= 15
        
        # Wrap and draw summary text
        from reportlab.pdfbase.pdfmetrics import stringWidth
        words = summary.split()
        lines = []
        current_line = ""
        
        for word in words:
            test_line = current_line + " " + word if current_line else word
            if stringWidth(test_line, 'Helvetica', 12) <= max_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word
        if current_line:
            lines.append(current_line)
        
        # Draw each line of the summary
        for line in lines:
            c.drawString(60, y, line)
            y -= 15
            if y < 40:
                c.showPage()
                y = height - 40
        
        y -= 10  # Extra space between entries
        if y < 40:
            c.showPage()
            y = height - 40
    
    c.save()
    buffer.seek(0)
    return buffer

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
