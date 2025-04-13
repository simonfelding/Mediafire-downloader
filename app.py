from flask import Flask, request, jsonify, render_template
import os
from mediafire_downloader import MediaFireDownloader

app = Flask(__name__)
# Initialize with default max_workers, will be updated based on user selection
downloader = None

# Ensure downloads directory exists
DOWNLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'downloads')
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/download', methods=['POST'])
def start_download():
    global downloader
    
    urls = request.json.get('urls', [])
    max_workers = int(request.json.get('max_workers', 5))
    
    if not urls:
        return jsonify({'error': 'No URLs provided'}), 400

    # Create new downloader instance with user-selected max_workers
    downloader = MediaFireDownloader(max_workers=max_workers)
    
    download_ids = []
    for url in urls:
        try:
            future = downloader.start_download(url, DOWNLOAD_DIR)
            download_ids.append(future)
        except Exception as e:
            return jsonify({'error': str(e)}), 400

    return jsonify({'message': 'Downloads started', 'count': len(download_ids)})

@app.route('/api/status')
def get_status():
    if downloader is None:
        return jsonify({'downloads': {}})
    
    all_status = downloader.get_all_status()
    return jsonify({
        'downloads': {
            id_: {
                'filename': status.filename,
                'total_size': status.total_size,
                'downloaded': status.downloaded,
                'status': status.status.value,  # Convert enum to string
                'speed': status.speed,
                'progress': status.progress,
                'error': status.error
            }
            for id_, status in all_status.items()
        }
    })

@app.route('/api/download/control', methods=['POST'])
def control_download():
    if not downloader:
        return jsonify({'error': 'No active downloader'}), 400

    action = request.json.get('action')
    download_id = request.json.get('download_id')

    if not action or not download_id:
        return jsonify({'error': 'Missing action or download_id'}), 400

    success = False
    if action == 'pause':
        success = downloader.pause_download(download_id)
    elif action == 'resume':
        success = downloader.resume_download(download_id)
    elif action == 'cancel':
        success = downloader.cancel_download(download_id)
    else:
        return jsonify({'error': 'Invalid action'}), 400

    return jsonify({'success': success})

if __name__ == '__main__':
    app.run(debug=True if os.getenv("DEBUG") == "true" else False) 
