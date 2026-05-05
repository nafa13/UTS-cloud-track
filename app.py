import os
import boto3
from flask import Flask, render_template, request, redirect, url_for
import mysql.connector
from werkzeug.utils import secure_filename

app = Flask(__name__)

# Ambil data dari Environment Variables
db_host = os.environ.get('DB_HOST', 'citylogistics-db.cv0qooiiyisv.ap-southeast-2.rds.amazonaws.com')
db_user = os.environ.get('DB_USER', 'admin')
db_pass = os.environ.get('DB_PASS', 'Fal130404')
db_name = os.environ.get('DB_NAME', 'citylogistics')
s3_bucket = os.environ.get('S3_BUCKET_NAME', 'citylogistics-assets-nafa')

# --- KONFIGURASI CDN CLOUDFRONT ---
# GANTI ini dengan URL CloudFront yang kamu copy tadi! (Pakai https:// dan hapus garis miring di akhir)
CLOUDFRONT_DOMAIN = os.environ.get('CLOUDFRONT_DOMAIN', 'https://d2jaf5rgtzj7d1.cloudfront.net')
S3_REGION = 'ap-southeast-2'

s3_client = boto3.client('s3', region_name=S3_REGION)

def get_db_connection():
    return mysql.connector.connect(
        host=db_host,
        user=db_user,
        password=db_pass,
        database=db_name
    )

@app.route('/')
def index():
    # Fitur Search 
    search_query = request.args.get('search')
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        if search_query:
            query = "SELECT resi, status, lokasi FROM shipments WHERE resi LIKE %s OR lokasi LIKE %s"
            cur.execute(query, (f"%{search_query}%", f"%{search_query}%"))
        else:
            cur.execute('SELECT resi, status, lokasi FROM shipments')
        shipments = cur.fetchall()
        cur.close()
        conn.close()
        return render_template('index.html', shipments=shipments)
    except Exception as e:
        return f"Database Error: {e}"

@app.route('/upload', methods=['POST'])
def upload_file():
    # Fitur Upload Bukti ke S3 dan CDN
    file = request.files.get('file')
    if file and file.filename != '':
        # Amankan nama file dari karakter aneh/spasi
        filename = secure_filename(file.filename)
        try:
            # 1. Upload file ke S3
            s3_client.upload_fileobj(
                file, 
                s3_bucket, 
                filename,
                ExtraArgs={'ContentType': file.content_type} # Penting agar gambar bisa dirender browser
            )
            
            # 2. Rangkai URL CloudFront
            file_url = f"{CLOUDFRONT_DOMAIN}/{filename}"
            
            # 3. Simpan URL CloudFront ke MySQL
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute('INSERT INTO logs (filename, status) VALUES (%s, %s)', (file_url, 'Uploaded via CDN'))
            conn.commit()
            cur.close()
            conn.close()
        except Exception as e:
            print(f"S3 Upload Error: {e}")
            return f"Upload Error: {e}"
            
    return redirect(url_for('index'))

@app.route('/report', methods=['POST'])
def report_issue():
    # Fitur Lapor Kendala
    issue = request.form.get('issue')
    if issue:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('INSERT INTO reports (description) VALUES (%s)', (issue,))
        conn.commit()
        cur.close()
        conn.close()
    return redirect(url_for('index'))

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/admin')
def admin():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Ambil data logs (id, filename, status)
        cur.execute('SELECT * FROM logs ORDER BY id DESC')
        logs = cur.fetchall()
        
        # Ambil data reports (id, description)
        cur.execute('SELECT * FROM reports ORDER BY id DESC')
        reports = cur.fetchall()
        
        cur.close()
        conn.close()
        return render_template('admin.html', logs=logs, reports=reports)
    except Exception as e:
        return f"Database Error pada Admin Panel: {e}"

@app.route('/admin/report/edit/<int:id>', methods=['POST'])
def edit_report(id):
    description = request.form.get('description')
    if description:
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute('UPDATE reports SET description = %s WHERE id = %s', (description, id))
            conn.commit()
            cur.close()
            conn.close()
        except Exception as e:
            print(f"Update Report Error: {e}")
    return redirect(url_for('admin'))

@app.route('/admin/report/delete/<int:id>', methods=['POST'])
def delete_report(id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('DELETE FROM reports WHERE id = %s', (id,))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Delete Report Error: {e}")
    return redirect(url_for('admin'))

@app.route('/admin/log/edit/<int:id>', methods=['POST'])
def edit_log(id):
    status = request.form.get('status')
    if status:
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute('UPDATE logs SET status = %s WHERE id = %s', (status, id))
            conn.commit()
            cur.close()
            conn.close()
        except Exception as e:
            print(f"Update Log Error: {e}")
    return redirect(url_for('admin'))

@app.route('/admin/log/delete/<int:id>', methods=['POST'])
def delete_log(id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        # Hapus file dari S3
        cur.execute('SELECT filename FROM logs WHERE id = %s', (id,))
        log = cur.fetchone()
        if log:
            file_url = log[0]
            # filename adalah bagian terakhir dari URL
            filename = file_url.split('/')[-1]
            try:
                s3_client.delete_object(Bucket=s3_bucket, Key=filename)
            except Exception as s3_e:
                print(f"S3 Delete Error: {s3_e}")

        cur.execute('DELETE FROM logs WHERE id = %s', (id,))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Delete Log Error: {e}")
    return redirect(url_for('admin'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)