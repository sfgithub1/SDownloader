import hashlib
import os


def calculate_md5(filepath, chunk_size=8192):
    md5 = hashlib.md5()
    with open(filepath, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            md5.update(chunk)
    return md5.hexdigest()


def calculate_md5_from_bytes(data):
    return hashlib.md5(data).hexdigest()


def format_bytes(size):
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} PB"


def get_filename_from_url(url):
    from urllib.parse import urlparse
    parsed = urlparse(url)
    filename = os.path.basename(parsed.path)
    if not filename:
        filename = "downloaded_file"
    return filename


def check_range_support(url):
    import urllib.request
    try:
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req, timeout=10) as response:
            accept_ranges = response.headers.get("Accept-Ranges", "")
            content_length = response.headers.get("Content-Length")
            if "bytes" in accept_ranges and content_length:
                return True, int(content_length)
            return False, int(content_length) if content_length else 0
    except Exception as e:
        raise ConnectionError(f"無法連接到 {url}: {e}")


def get_local_ip():
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"
