# Insta Save Pro - Backend

Simple Flask backend that downloads public Instagram reels/posts and returns the media file.

## Files included
- `app.py` - Flask application
- `requirements.txt` - Python dependencies
- `.gitignore` - ignores downloads & env files

## Quick start (local)
1. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate     # macOS / Linux
   venv\Scripts\activate      # Windows
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run:
   ```bash
   python app.py
   ```
4. POST to `/download` with JSON body:
   ```json
   { "url": "https://www.instagram.com/reel/xxxxx/" }
   ```

## Deploy to Render
1. Create GitHub repo and push these files.
2. On Render.com, create a **Web Service** connected to the repo.
3. Build Command:
   ```
   pip install -r requirements.txt
   ```
4. Start Command:
   ```
   python app.py
   ```

## Notes & legal
- This tool only works with **public** Instagram content.
- Respect Instagram's terms of service and copyright.
- Instagram may change HTML structure; if downloads fail, update scraping logic.
