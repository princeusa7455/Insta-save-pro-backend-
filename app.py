import os
import re
import requests
from flask import Flask, request, jsonify, send_file, make_response
from urllib.parse import urlparse
import uuid
import datetime
from werkzeug.utils import secure_filename
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Configuration
app.config['MAX_CONTENT_LENGTH'] = 64 * 1024 * 1024
app.config['DOWNLOAD_FOLDER'] = 'downloads'
app.config['CLEANUP_AGE'] = 3600

os.makedirs(app.config['DOWNLOAD_FOLDER'], exist_ok=True)

# =============================
# 🔥 REAL BROWSER HEADERS (Fix 429)
# =============================
BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-User": "?1",
    "Sec-Fetch-Dest": "document",
}

def clean_old_files():
    try:
        now = datetime.datetime.now().timestamp()
        for filename in os.listdir(app.config['DOWNLOAD_FOLDER']):
            file_path = os.path.join(app.config['DOWNLOAD_FOLDER'], filename)
            if os.path.isfile(file_path):
                if now - os.path.getmtime(file_path) > app.config['CLEANUP_AGE']:
                    os.remove(file_path)
    except Exception as e:
        print("Cleanup error:", e)

def validate_instagram_url(url):
    parsed = urlparse(url)
    if parsed.netloc not in ['www.instagram.com', 'instagram.com']:
        return False
    path = parsed.path
    if not re.match(r'^/(reel|p)/[\w\-]+', path) and not re.match(r'^/[A-Za-z0-9_.-]+/(stories|reel)?', path):
        return False
    return True

def extract_video_id(url):
    match = re.search(r'/(reel|p)/([^/?]+)', url)
    return match.group(2) if match else None

# ======================================
# 🔥 FIXED FUNCTION: Fetch Instagram Page
# ======================================
def get_video_url(instagram_url):
    try:
        response = requests.get(instagram_url, headers=BROWSER_HEADERS, timeout=30)
        response.raise_for_status()
        html = response.text

        # pattern 1
        m1 = re.findall(r'"video_url"\s*:\s*"(https?://[^"]+\.mp4[^"]*)"', html)
        if m1:
            return m1[0].encode().decode('unicode_escape')

        # og:video
        m2 = re.search(r'<meta property="og:video" content="([^"]+)">', html)
        if m2:
            return m2.group(1)

        # fallback mp4
        m3 = re.findall(r'(https?://[\w\d\-./:_]+\.mp4[\w\d\-./:_]*)', html)
        if m3:
            return m3[0]

        raise Exception("Video URL not found. Content may be private.")

    except Exception as e:
        raise Exception(f"Instagram request failed: {str(e)}")

# ======================================
# 🔥 FIXED FILE DOWNLOAD (Headers added)
# ======================================
def download_reel(video_url, filename):
    try:
        r = requests.get(video_url, headers=BROWSER_HEADERS, stream=True, timeout=30)
        r.raise_for_status()

        filepath = os.path.join(app.config['DOWNLOAD_FOLDER'], filename)
        with open(filepath, "wb") as f:
            for chunk in r.iter_content(8192):
                if chunk:
                    f.write(chunk)
        return filepath

    except Exception as e:
        raise Exception("Download failed: " + str(e))

@app.route('/download', methods=['POST'])
def download_reel_endpoint():
    clean_old_files()

    data = request.get_json(silent=True)
    if not data or 'url' not in data:
        return jsonify({"error": "URL required"}), 400

    url = data['url'].strip()
    if not validate_instagram_url(url):
        return jsonify({"error": "Invalid Instagram URL"}), 400

    try:
        video_url = get_video_url(url)
        video_id = extract_video_id(url) or str(uuid.uuid4())[:8]

        filename = secure_filename(f"reel_{video_id}_{int(datetime.datetime.now().timestamp())}.mp4")
        filepath = download_reel(video_url, filename)

        resp = make_response(send_file(filepath, as_attachment=True))
        resp.headers['Content-Disposition'] = f'attachment; filename=instagram_{video_id}.mp4'
        return resp

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/health')
def health():
    return jsonify({"status": "OK", "time": datetime.datetime.now().isoformat()})

if __name__ == "__main__":
    clean_old_files()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
