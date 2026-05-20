import cgi
import json
import os
import socket
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

from .downloader import Downloader
from .merger import Merger
from .task import TaskManager
from .utils import format_bytes, get_local_ip


class TaskHandler(BaseHTTPRequestHandler):
    task_manager = None
    output_dir = "."
    task_path = None
    auto_merge = True

    def log_message(self, format, *args):
        pass

    def _send_json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == "/task":
            task = self.task_manager.get_task()
            if task:
                self._send_json(task)
            else:
                self._send_json({"error": "No task loaded"}, 404)

        elif parsed.path == "/task/status":
            progress = self.task_manager.get_progress()
            self._send_json(progress)

        else:
            self._send_json({"error": "Not found"}, 404)

    def do_POST(self):
        parsed = urlparse(self.path)

        if parsed.path == "/task/claim":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length) if content_length > 0 else b""

            client_id = None
            if body:
                try:
                    data = json.loads(body.decode("utf-8"))
                    client_id = data.get("client_id")
                except (json.JSONDecodeError, UnicodeDecodeError):
                    pass

            if not client_id:
                client_id = self.client_address[0]

            part = self.task_manager.claim_part(client_id)
            if part:
                if self.task_path:
                    self.task_manager.save_task(self.task_path)
                self._send_json({"part": part})
            else:
                self._send_json({"error": "No pending parts"}, 404)

        elif parsed.path == "/task/complete":
            content_type = self.headers.get("Content-Type", "")

            if "multipart/form-data" in content_type:
                form = cgi.FieldStorage(
                    fp=self.rfile,
                    headers=self.headers,
                    environ={
                        "REQUEST_METHOD": "POST",
                        "CONTENT_TYPE": content_type,
                    },
                )

                part_number = int(form["part_number"].value)
                checksum = form["checksum"].value

                if "file" in form:
                    file_item = form["file"]
                    filename = file_item.filename
                    filepath = os.path.join(self.output_dir, filename)

                    with open(filepath, "wb") as f:
                        f.write(file_item.file.read())

                    self.task_manager.complete_part(part_number, checksum)
                    if self.task_path:
                        self.task_manager.save_task(self.task_path)

                    progress = self.task_manager.get_progress()
                    print(f"Part {part_number} 完成 "
                          f"({progress['completed']}/{progress['total']})")

                    if self.task_manager.is_all_completed() and self.auto_merge:
                        print("所有分拆已完成，開始合併...")
                        merger = Merger(self.output_dir)
                        try:
                            result = merger.merge(self.task_path)
                            print(f"合併完成: {result}")
                        except Exception as e:
                            print(f"合併失敗: {e}")

                    self._send_json({
                        "status": "completed",
                        "part_number": part_number,
                        "progress": progress,
                    })
                else:
                    self._send_json({"error": "No file uploaded"}, 400)
            else:
                content_length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(content_length) if content_length > 0 else b""
                try:
                    data = json.loads(body.decode("utf-8"))
                    part_number = data["part_number"]
                    checksum = data["checksum"]
                    self.task_manager.complete_part(part_number, checksum)
                    if self.task_path:
                        self.task_manager.save_task(self.task_path)
                    self._send_json({"status": "completed"})
                except (json.JSONDecodeError, KeyError) as e:
                    self._send_json({"error": str(e)}, 400)
        else:
            self._send_json({"error": "Not found"}, 404)


class DownloadServer:
    def __init__(self, task_path, output_dir=".", port=8080, auto_merge=True, redownload_parts=None):
        self.task_path = task_path
        self.output_dir = output_dir
        self.port = port
        self.auto_merge = auto_merge
        self.redownload_parts = redownload_parts or []
        self.task_manager = TaskManager()
        self.task_manager.load_task(task_path)
        self._server = None
        self._server_thread = None

    def start(self, also_download=True):
        TaskHandler.task_manager = self.task_manager
        TaskHandler.output_dir = self.output_dir
        TaskHandler.task_path = self.task_path
        TaskHandler.auto_merge = self.auto_merge

        if self.redownload_parts:
            reset_list = self.task_manager.reset_parts(self.redownload_parts)
            if reset_list:
                print(f"已重設分拆: {', '.join(str(p) for p in reset_list)}")
                if self.task_path:
                    self.task_manager.save_task(self.task_path)

        self._server = HTTPServer(("0.0.0.0", self.port), TaskHandler)
        local_ip = get_local_ip()

        print(f"伺服器已啟動: http://{local_ip}:{self.port}")
        print(f"任務檔: {self.task_path}")
        task = self.task_manager.get_task()
        print(f"檔案: {task['filename']} ({format_bytes(task['file_size'])})")
        print(f"分拆數: {task['total_parts']}")
        print(f"客戶端連線: sdownloader download --host {local_ip}:{self.port}")

        self._server_thread = threading.Thread(
            target=self._server.serve_forever, daemon=True
        )
        self._server_thread.start()

        if also_download:
            self._host_download()

        try:
            print("\n伺服器運行中，按 Ctrl+C 停止...")
            while True:
                import time
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n伺服器已停止")
            self._server.shutdown()

    def _host_download(self):
        downloader = Downloader(self.output_dir)
        task = self.task_manager.get_task()

        def download_loop():
            while not self.task_manager.is_all_completed():
                part = self.task_manager.claim_part("host")
                if not part:
                    import time
                    time.sleep(2)
                    continue

                try:
                    url = task["url"]
                    filepath, checksum = downloader.download_part(url, part)
                    self.task_manager.complete_part(part["part_number"], checksum)
                    if self.task_path:
                        self.task_manager.save_task(self.task_path)

                    progress = self.task_manager.get_progress()
                    print(f"[主機] Part {part['part_number']} 完成 "
                          f"({progress['completed']}/{progress['total']})")
                except Exception as e:
                    print(f"[主機] Part {part['part_number']} 失敗: {e}")
                    self.task_manager.fail_part(part["part_number"])

        host_thread = threading.Thread(target=download_loop, daemon=True)
        host_thread.start()
