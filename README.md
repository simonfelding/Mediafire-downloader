# MediaFire Bulk Downloader

A modern, fast, and efficient bulk downloader for MediaFire links with a clean web interface. Built with Python Flask and modern web technologies.

<p align="center">
  <img src="https://i.ibb.co/Jjc4dDM1/Screenshot-2025-01-29-055521.png" alt="MediaFire Bulk Downloader Interface">
</p>

## Created By
**Aamir**
- GitHub: [github.com/aamir](https://github.com/aamirxs)

## Features

- 🚀 Multi-threaded downloads for maximum speed
- 📦 Bulk download support
- ⏯️ Pause/Resume functionality
- ❌ Cancel specific downloads
- 📊 Real-time progress tracking
- 🎛️ Adjustable simultaneous downloads (1-20)
- 🔄 Automatic retry on failures
- 💾 Temporary file handling for safe downloads
- 📝 Comprehensive error logging

## Quick Start
`docker run --rm -v ./:/download -p 5000:5000 ghcr.io/simonfelding/mediafire-downloader:latest` 

### Usage

1. Open your web browser and navigate to <code>http://localhost:5000</code>
2. Enter the MediaFire link and click "Download"
3. Adjust the number of simultaneous downloads and click "Start"
4. Monitor the progress and status of your downloads
