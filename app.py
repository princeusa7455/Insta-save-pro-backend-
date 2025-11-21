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
app.config['MAX_CONTENT_LENGTH'] = 64 * 1024 * 1024  # 64MB max request size
app.config['DOWNLOAD_FOLDER'] = 'downloads'
app.config['CLEANUP_AGE'] = 3600  # Cleanup files older than 1 hour

# Ensure download directory exists
os.makedirs(app.config['DOWNLOAD_FOLDER'], exist_ok=True)

def clean_old_files():
    """Remove files older than CLEANUP_AGE seconds"""
    try:
        now = datetime.datetime.now().timestamp()
        for filename in os.listdir(app.config['DOWNLOAD_FOLDER']):
            file_path = os.path.join(app.config['DOWNLOAD_FOLDER'], filename)
            if os.path.isfile(file_path):
                file_age = now - os.path.getmtime(file_path)
                if file_age > app.config['CLEANUP_AGE']:
                    os.remove(file_path)
                    app.logger.info(f"Removed old file: {filename}")
    except Exception as e:
        app.logger.error(f"Error during cleanup: {e}")

def validate_instagram_url(url):
    parsed = urlparse(url)
    if parsed.netloc not in ['www.instagram.com', 'instagram.com', 'instagram.com.']:
        return False
    path = parsed.path
    if not re.match(r'^/(reel|p)/[\w\-]+', path) and not re.match(r'^/[A-Za-z0-9_.-]+/((stories)|(reel))?', path):
        return False
    return True

def extract_video_id(url):
    parsed = urlparse(url)
    path = parsed.path
    match = re.search(r'/(reel|p)/([^/?]+)', path)
    if match:
        return match.group(2)
    return None

def download_reel(video_url, filename):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
    }
    try:
        response = requests.get(video_url, headers=headers, stream=True, timeout=30)
        response.raise_for_status()
        filepath = os.path.join(app.config['DOWNLOAD_FOLDER'], filename)
        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        return filepath
    except requests.exceptions.RequestException as e:
        raise Exception(f"Download failed: {str(e)}")

def get_video_url(instagram_url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
    }
    try:
        response = requests.get(instagram_url, headers=headers, timeout=30)
        response.raise_for_status()
        html_content = response.text
        # Try common JSON-LD or video_url patterns
        # 1) video_url key in page
        pattern1 = r'"video_url"\s*:\s*"(https?://[^"]+\.mp4[^"]*)"'
        m1 = re.findall(pattern1, html_content)
        if m1:
            return m1[0].encode().decode('unicode_escape')
        # 2) og:video meta
        m2 = re.search(r'<meta property="og:video" content="([^"]+)">', html_content)
        if m2:
            return m2.group(1)
        # 3) look for MP4 urls as fallback
        m3 = re.findall(r'(https?://[\w\d\-./:_]+\.mp4[\w\d\-./:_]*)', html_content)
        if m3:
            return m3[0]
        raise Exception("Video URL not found in page. Instagram may have changed markup or content is private.")
    except requests.exceptions.RequestException as e:
        raise Exception(f"Failed to fetch Instagram page: {str(e)}")

@app.route('/download', methods=['POST'])
def download_reel_endpoint():
    clean_old_files()
    data = request.get_json(silent=True)
    if not data or 'url' not in data:
        return jsonify({'error': 'URL is required'}), 400
    url = data['url'].strip()
    if not validate_instagram_url(url):
        return jsonify({'error': 'Invalid Instagram URL or unsupported format'}), 400
    try:
        video_url = get_video_url(url)
        if not video_url:
            return jsonify({'error': 'Video URL could not be extracted'}), 500
        video_id = extract_video_id(url) or str(uuid.uuid4())[:8]
        filename = f"reel_{video_id}_{int(datetime.datetime.now().timestamp())}.mp4"
        filename = secure_filename(filename)
        filepath = download_reel(video_url, filename)
        # send file with filename set
        response = make_response(send_file(filepath, as_attachment=True))
        response.headers['Content-Disposition'] = f'attachment; filename=instagram_reel_{video_id}.mp4'
        return response
    except Exception as e:
        app.logger.error(str(e))
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy', 'timestamp': datetime.datetime.now().isoformat()})

if __name__ == '__main__':
    clean_old_files()
    app.run(debug=False, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
