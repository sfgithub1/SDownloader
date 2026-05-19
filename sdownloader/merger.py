import hashlib
import json
import os

from tqdm import tqdm

from .utils import format_bytes


class Merger:
    CHUNK_SIZE = 8192

    def __init__(self, output_dir="."):
        self.output_dir = output_dir

    def merge(self, task_path):
        with open(task_path, "r", encoding="utf-8") as f:
            task = json.load(f)

        filename = task["filename"]
        file_size = task["file_size"]
        parts = sorted(task["parts"], key=lambda p: p["part_number"])

        self._verify_parts(parts)

        output_path = os.path.join(self.output_dir, filename)
        md5 = hashlib.md5()

        print(f"合併 {len(parts)} 個分拆檔 -> {filename}")

        with tqdm(total=file_size, unit="B", unit_scale=True,
                  desc="合併中", ncols=80) as pbar:
            with open(output_path, "wb") as out_f:
                for part in parts:
                    part_path = os.path.join(self.output_dir, part["filename"])
                    if not os.path.exists(part_path):
                        raise FileNotFoundError(
                            f"分拆檔不存在: {part_path}"
                        )

                    with open(part_path, "rb") as in_f:
                        while True:
                            chunk = in_f.read(self.CHUNK_SIZE)
                            if not chunk:
                                break
                            out_f.write(chunk)
                            md5.update(chunk)
                            pbar.update(len(chunk))

        merged_md5 = md5.hexdigest()
        merged_size = os.path.getsize(output_path)

        print(f"\n合併完成:")
        print(f"  檔案: {output_path}")
        print(f"  大小: {format_bytes(merged_size)}")
        print(f"  MD5: {merged_md5}")

        if merged_size != file_size:
            print(f"  警告: 檔案大小不符 (預期 {format_bytes(file_size)})")

        print(f"\n請自行比對 MD5 以確認檔案完整性")

        return output_path

    def _verify_parts(self, parts):
        from .utils import calculate_md5

        print("驗證分拆檔 MD5...")
        missing = []
        mismatch = []

        for part in parts:
            part_path = os.path.join(self.output_dir, part["filename"])

            if not os.path.exists(part_path):
                missing.append(part["filename"])
                continue

            if part.get("checksum"):
                actual_md5 = calculate_md5(part_path)
                if actual_md5 != part["checksum"]:
                    mismatch.append(
                        f"{part['filename']}: "
                        f"預期 {part['checksum']}, 實際 {actual_md5}"
                    )

        if missing:
            raise FileNotFoundError(
                f"缺少分拆檔: {', '.join(missing)}"
            )

        if mismatch:
            raise ValueError(
                f"MD5 驗證失敗:\n" + "\n".join(mismatch)
            )

        print("所有分拆檔驗證通過")
