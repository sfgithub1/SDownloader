import json
import os
import uuid
from datetime import datetime
from threading import Lock

from .utils import check_range_support, get_filename_from_url


class TaskStatus:
    PENDING = "pending"
    DOWNLOADING = "downloading"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskManager:
    def __init__(self):
        self._lock = Lock()
        self._task = None

    def create_task(self, url, num_parts, output_dir="."):
        supports_range, file_size = check_range_support(url)

        if not supports_range:
            return None, file_size, False

        filename = get_filename_from_url(url)
        task_id = uuid.uuid4().hex[:8]
        part_size = file_size // num_parts
        parts = []

        for i in range(num_parts):
            start_byte = i * part_size
            if i == num_parts - 1:
                end_byte = file_size - 1
            else:
                end_byte = (i + 1) * part_size - 1

            parts.append({
                "part_number": i + 1,
                "start_byte": start_byte,
                "end_byte": end_byte,
                "filename": f"{filename}.part{i + 1}",
                "status": TaskStatus.PENDING,
                "checksum": None,
                "claimed_by": None,
            })

        task = {
            "task_id": task_id,
            "url": url,
            "filename": filename,
            "file_size": file_size,
            "total_parts": num_parts,
            "range_supported": True,
            "parts": parts,
            "created_at": datetime.now().isoformat(),
            "completed_at": None,
        }

        task_path = os.path.join(output_dir, f"{filename}.task.json")
        with open(task_path, "w", encoding="utf-8") as f:
            json.dump(task, f, indent=2, ensure_ascii=False)

        self._task = task
        return task_path, file_size, True

    def load_task(self, task_path):
        with open(task_path, "r", encoding="utf-8") as f:
            self._task = json.load(f)
        return self._task

    def save_task(self, task_path):
        with open(task_path, "w", encoding="utf-8") as f:
            json.dump(self._task, f, indent=2, ensure_ascii=False)

    def get_task(self):
        return self._task

    def claim_part(self, client_id=None):
        with self._lock:
            if not self._task:
                return None

            for part in self._task["parts"]:
                if part["status"] == TaskStatus.PENDING:
                    part["status"] == TaskStatus.DOWNLOADING
                    part["status"] = TaskStatus.DOWNLOADING
                    part["claimed_by"] = client_id
                    return part

            return None

    def complete_part(self, part_number, checksum):
        with self._lock:
            if not self._task:
                return False

            for part in self._task["parts"]:
                if part["part_number"] == part_number:
                    part["status"] = TaskStatus.COMPLETED
                    part["checksum"] = checksum
                    break

            all_completed = all(
                p["status"] == TaskStatus.COMPLETED
                for p in self._task["parts"]
            )
            if all_completed:
                self._task["completed_at"] = datetime.now().isoformat()

            return True

    def fail_part(self, part_number):
        with self._lock:
            if not self._task:
                return False

            for part in self._task["parts"]:
                if part["part_number"] == part_number:
                    part["status"] = TaskStatus.FAILED
                    break
            return True

    def reset_parts(self, part_numbers):
        with self._lock:
            if not self._task:
                return []

            reset_list = []
            for part in self._task["parts"]:
                if part["part_number"] in part_numbers:
                    part["status"] = TaskStatus.PENDING
                    part["checksum"] = None
                    part["claimed_by"] = None
                    reset_list.append(part["part_number"])

            self._task["completed_at"] = None
            return reset_list

    def get_pending_count(self):
        with self._lock:
            if not self._task:
                return 0
            return sum(
                1 for p in self._task["parts"]
                if p["status"] == TaskStatus.PENDING
            )

    def is_all_completed(self):
        with self._lock:
            if not self._task:
                return False
            return all(
                p["status"] == TaskStatus.COMPLETED
                for p in self._task["parts"]
            )

    def get_progress(self):
        with self._lock:
            if not self._task:
                return {}

            total = self._task["total_parts"]
            completed = sum(
                1 for p in self._task["parts"]
                if p["status"] == TaskStatus.COMPLETED
            )
            downloading = sum(
                1 for p in self._task["parts"]
                if p["status"] == TaskStatus.DOWNLOADING
            )
            pending = sum(
                1 for p in self._task["parts"]
                if p["status"] == TaskStatus.PENDING
            )

            return {
                "total": total,
                "completed": completed,
                "downloading": downloading,
                "pending": pending,
                "progress_percent": (completed / total * 100) if total > 0 else 0,
            }
