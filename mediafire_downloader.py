import requests
import re
import os.path as osp
import tempfile
import shutil
import os
from concurrent.futures import ThreadPoolExecutor, Future
from threading import Lock, Event
from dataclasses import dataclass
from typing import Optional, Dict, List
import time
import logging
from enum import Enum

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('downloader.log'),
        logging.StreamHandler()
    ]
)

class DownloadStatus(Enum):
    QUEUED = "queued"
    DOWNLOADING = "downloading"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

@dataclass
class DownloadInfo:
    filename: str
    total_size: int
    downloaded: int
    status: DownloadStatus
    speed: float
    progress: float
    error: Optional[str] = None
    pause_event: Optional[Event] = None
    future: Optional[Future] = None
    temp_file: Optional[str] = None

    def to_dict(self):
        """Convert the DownloadInfo to a dictionary for JSON serialization"""
        return {
            'filename': self.filename,
            'total_size': self.total_size,
            'downloaded': self.downloaded,
            'status': self.status.value,  # Convert enum to string
            'speed': self.speed,
            'progress': self.progress,
            'error': self.error
        }

class DownloadError(Exception):
    def __init__(self, message: str, error_type: str, is_recoverable: bool = True):
        super().__init__(message)
        self.error_type = error_type
        self.is_recoverable = is_recoverable

class MediaFireDownloader:
    def __init__(self, max_workers=5, max_retries=3):
        self.max_workers = max_workers
        self.max_retries = max_retries
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.downloads: Dict[str, DownloadInfo] = {}
        self.lock = Lock()
        self.logger = logging.getLogger(__name__)

    def extract_download_link(self, contents):
        try:
            for line in contents.splitlines():
                m = re.search(r'href="((http|https)://download[^"]+)', line)
                if m:
                    return m.groups()[0]
            raise DownloadError("Download link not found", "LINK_EXTRACTION_ERROR")
        except Exception as e:
            self.logger.error(f"Error extracting download link: {str(e)}")
            raise DownloadError(f"Failed to extract download link: {str(e)}", "LINK_EXTRACTION_ERROR")

    def download_file(self, url: str, output_dir: str, download_id: str) -> str:
        retry_count = 0
        while retry_count < self.max_retries:
            try:
                return self._attempt_download(url, output_dir, download_id, retry_count)
            except DownloadError as e:
                if not e.is_recoverable or retry_count >= self.max_retries - 1:
                    with self.lock:
                        self.downloads[download_id].status = DownloadStatus.FAILED
                        self.downloads[download_id].error = str(e)
                    raise
                retry_count += 1
                self.logger.warning(f"Retry {retry_count} for download {download_id}")
                time.sleep(2 ** retry_count)  # Exponential backoff

    def _attempt_download(self, url: str, output_dir: str, download_id: str, retry_count: int) -> str:
        sess = requests.session()
        sess.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

        try:
            # Follow redirects to get the final download link
            while True:
                res = sess.get(url, stream=True)
                if 'Content-Disposition' in res.headers:
                    break
                url = self.extract_download_link(res.text)
                if url is None:
                    raise DownloadError("Permission denied or invalid link", "PERMISSION_ERROR", False)

            # Get filename from headers
            m = re.search('filename="(.*)"', res.headers['Content-Disposition'])
            if not m:
                raise DownloadError("Cannot extract filename", "FILENAME_ERROR")
            
            filename = m.groups()[0].encode('iso8859').decode('utf-8')
            output_path = osp.join(output_dir, filename)
            total_size = int(res.headers.get('Content-Length', 0))

            # Create temporary file
            tmp_file = tempfile.mktemp(suffix=tempfile.template, prefix=filename, dir=output_dir)

            with self.lock:
                self.downloads[download_id].filename = filename
                self.downloads[download_id].total_size = total_size
                self.downloads[download_id].temp_file = tmp_file

            start_time = time.time()
            downloaded = 0

            with open(tmp_file, 'wb') as f:
                for chunk in res.iter_content(chunk_size=1024*1024):
                    # Check for pause/cancel
                    if self.downloads[download_id].pause_event.is_set():
                        return download_id

                    if self.downloads[download_id].status == DownloadStatus.CANCELLED:
                        os.remove(tmp_file)
                        return download_id

                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        elapsed = time.time() - start_time
                        speed = downloaded / elapsed if elapsed > 0 else 0
                        progress = (downloaded / total_size * 100) if total_size > 0 else 0

                        with self.lock:
                            self.downloads[download_id].downloaded = downloaded
                            self.downloads[download_id].speed = speed
                            self.downloads[download_id].progress = progress

            # Move temporary file to final destination
            shutil.move(tmp_file, output_path)
            
            with self.lock:
                self.downloads[download_id].status = DownloadStatus.COMPLETED
                self.downloads[download_id].temp_file = None
            
            return download_id

        except requests.exceptions.RequestException as e:
            raise DownloadError(f"Network error: {str(e)}", "NETWORK_ERROR")
        except OSError as e:
            raise DownloadError(f"File system error: {str(e)}", "FILESYSTEM_ERROR")
        except Exception as e:
            raise DownloadError(f"Unexpected error: {str(e)}", "UNKNOWN_ERROR", False)

    def start_download(self, url: str, output_dir: str) -> str:
        download_id = str(int(time.time() * 1000))
        
        with self.lock:
            self.downloads[download_id] = DownloadInfo(
                filename="Initializing...",
                total_size=0,
                downloaded=0,
                status=DownloadStatus.QUEUED,
                speed=0,
                progress=0,
                pause_event=Event(),
                future=None,
                temp_file=None
            )

        future = self.executor.submit(self.download_file, url, output_dir, download_id)
        self.downloads[download_id].future = future
        self.downloads[download_id].status = DownloadStatus.DOWNLOADING
        return download_id

    def pause_download(self, download_id: str) -> bool:
        with self.lock:
            if download_id not in self.downloads:
                return False
            download = self.downloads[download_id]
            if download.status == DownloadStatus.DOWNLOADING:
                download.pause_event.set()
                download.status = DownloadStatus.PAUSED
                return True
        return False

    def resume_download(self, download_id: str) -> bool:
        with self.lock:
            if download_id not in self.downloads:
                return False
            download = self.downloads[download_id]
            if download.status == DownloadStatus.PAUSED:
                download.pause_event.clear()
                download.status = DownloadStatus.DOWNLOADING
                return True
        return False

    def cancel_download(self, download_id: str) -> bool:
        with self.lock:
            if download_id not in self.downloads:
                return False
            download = self.downloads[download_id]
            if download.status in [DownloadStatus.DOWNLOADING, DownloadStatus.PAUSED]:
                download.status = DownloadStatus.CANCELLED
                if download.future:
                    download.future.cancel()
                if download.temp_file and os.path.exists(download.temp_file):
                    try:
                        os.remove(download.temp_file)
                    except OSError:
                        pass
                return True
        return False

    def get_status(self, download_id: str) -> Optional[DownloadInfo]:
        with self.lock:
            return self.downloads.get(download_id)

    def get_all_status(self) -> Dict[str, DownloadInfo]:
        with self.lock:
            return self.downloads.copy() 