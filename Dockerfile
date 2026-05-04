# Gunakan image Python yang ringan
FROM python:3.9-slim

# Set folder kerja di dalam kontainer
WORKDIR /app

# Salin file requirements.txt dan install library
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Salin semua sisa source code ke dalam kontainer
COPY . .

# Beritahu Docker kalau Flask jalan di port 5000
EXPOSE 5000

# Perintah untuk menjalankan aplikasi
CMD ["python", "app.py"]