import os
from flask import Flask, render_template, request, redirect, url_for
import mysql.connector

app = Flask(__name__)

# Ambil data dari Environment Variables yang kita set di ECS tadi
db_host = os.environ.get('DB_HOST', 'localhost')
db_user = os.environ.get('DB_USER', 'root')
db_pass = os.environ.get('DB_PASS', '')
db_name = os.environ.get('DB_NAME', 'logistics_db')

# Contoh jika menggunakan Flask-SQLAlchemy dengan MySQL
app.config['SQLALCHEMY_DATABASE_URI'] = f"mysql+pymysql://{db_user}:{db_pass}@{db_host}:3306/{db_name}"

# Folder lokal untuk upload (Pengganti S3 sementara) [cite: 38, 45]
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

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
    # Fitur Upload Bukti [cite: 45]
    file = request.files.get('file')
    if file and file.filename != '':
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(file_path)
        
        # Simpan metadata ke MySQL [cite: 47]
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('INSERT INTO logs (filename, status) VALUES (%s, %s)', (file.filename, 'Uploaded Locally'))
        conn.commit()
        cur.close()
        conn.close()
    return redirect(url_for('index'))

@app.route('/report', methods=['POST'])
def report_issue():
    # Fitur Lapor Kendala [cite: 21, 25, 44]
    issue = request.form.get('issue')
    if issue:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('INSERT INTO reports (description) VALUES (%s)', (issue,))
        conn.commit()
        cur.close()
        conn.close()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)