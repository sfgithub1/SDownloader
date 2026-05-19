import hashlib
import os
import urllib.request

from tqdm import tqdm

from .utils import format_bytes


class Downloader:
    CHUNK_SIZE = 8192

    def __init__(self, output_dir=".", progress_callback=None):
        self.output_dir = output_dir
        self.progress_callback = progress_callback

    def download_part(self, url, part_info, resume=True):
        part_number = part_info["part_number"]
        start_byte = part_info["start_byte"]
        end_byte = part_info["end_byte"]
        filename = part_info["filename"]
        total_size = end_byte - start_byte + 1

        filepath = os.path.join(self.output_dir, filename)
        tmp_path = filepath + ".tmp"

        downloaded = 0
        if resume and os.path.exists(tmp_path):
            downloaded = os.path.getsize(tmp_path)

        if downloaded >= total_size:
            return self._finalize(tmp_path, filepath)

        actual_start = start_byte + downloaded
        headers = {
            "Range": f"bytes={actual_start}-{end_byte}",
        }

        req = urllib.request.Request(url, headers=headers)
        mode = "ab" if downloaded > 0 else "wb"

        with urllib.request.urlopen(req, timeout=30) as response:
            md5 = hashlib.md5()

            if downloaded > 0:
                with open(tmp_path, "rb") as f:
                    while True:
                        chunk = f.read(self.CHUNK_SIZE)
                        if not chunk:
                            break
                        md5.update(chunk)

            pbar = tqdm(
                total=total_size,
                initial=downloaded,
                unit="B",
                unit_scale=True,
                desc=f"Part {part_number}",
                ncols=80,
            )

            with open(tmp_path, mode) as f:
                while True:
                    chunk = response.read(self.CHUNK_SIZE)
                    if not chunk:
                        break
                    f.write(chunk)
                    md5.update(chunk)
                    downloaded += len(chunk)
                    pbar.update(len(chunk))

                    if self.progress_callback:
                        self.progress_callback(part_number, downloaded, total_size)

            pbar.close()

        return self._finalize(tmp_path, filepath), md5.hexdigest()

    def _finalize(self, tmp_path, filepath):
        if os.path.exists(filepath):
            os.remove(filepath)
        os.rename(tmp_path, filepath)
        return filepath

    def download_part_from_server(self, host, port, output_dir=None):
        import json
        import socket

        if output_dir:
            self.output_dir = output_dir

        task_url = f"http://{host}:{port}/task"
        req = urllib.request.Request(task_url)
        with urllib.request.urlopen(req, timeout=10) as response:
            task_data = json.loads(response.read().decode("utf-8"))

        claim_url = f"http://{host}:{port}/task/claim"
        client_id = socket.gethostname()
        claim_data = json.dumps({"client_id": client_id}).encode("utf-8")
        req = urllib.request.Request(
            claim_url,
            data=claim_data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                result = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                print("沒有待下載的分拆任務")
                return None, None
            raise

        part_info = result["part"]
        url = task_data["url"]

        print(f"領取到 Part {part_info['part_number']}: "
              f"{format_bytes(part_info['end_byte'] - part_info['start_byte'] + 1)}")

        filepath, checksum = self.download_part(url, part_info)

        complete_url = f"http://{host}:{port}/task/complete"
        boundary = "----SDownloaderBoundary"
        part_number = part_info["part_number"]

        body = b""
        body += f"--{boundary}\r\n".encode()
        body += f'Content-Disposition: form-data; name="part_number"\r\n\r\n'.encode()
        body += f"{part_number}\r\n".encode()
        body += f"--{boundary}\r\n".encode()
        body += f'Content-Disposition: form-data; name="checksum"\r\n\r\n'.encode()
        body += f"{checksum}\r\n".encode()
        body += f"--{boundary}\r\n".encode()
        body += f'Content-Disposition: form-data; name="file"; filename="{os.path.basename(filepath)}"\r\n'.encode()
        body += b"Content-Type: application/octet-stream\r\n\r\n"

        with open(filepath, "rb") as f:
            body += f.read()

        body += f"\r\n--{boundary}--\r\n".encode()

        req = urllib.request.Request(
            complete_url,
            data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=60) as response:
            result = json.loads(response.read().decode("utf-8"))

        print(f"Part {part_number} 已上傳回主機")
        return filepath, checksum
