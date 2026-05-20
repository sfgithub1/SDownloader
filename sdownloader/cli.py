import argparse
import sys

from .downloader import Downloader
from .merger import Merger
from .server import DownloadServer
from .task import TaskManager
from .utils import format_bytes


def parse_part_numbers(parts_str):
    if not parts_str:
        return []
    result = []
    for part in parts_str.split(","):
        part = part.strip()
        if part.isdigit():
            result.append(int(part))
    return result


def cmd_create(args):
    tm = TaskManager()
    task_path, file_size, supports_range = tm.create_task(
        args.url, args.parts, args.output
    )

    if not supports_range:
        print(f"警告: 目標伺服器不支援 Range Requests")
        print(f"將降級為單線程下載（分拆數量無效）")
        print(f"檔案大小: {format_bytes(file_size)}")
        print(f"\n使用以下命令直接下載:")
        print(f"  curl -L -o {tm.get_filename_from_url(args.url)} {args.url}")
        return

    print(f"任務檔已建立: {task_path}")
    print(f"檔案: {tm.get_task()['filename']} ({format_bytes(file_size)})")
    print(f"分拆數: {args.parts}")
    print(f"\n下一步:")
    print(f"  1. 啟動伺服器: sdownloader serve --task {task_path}")
    print(f"  2. 其他電腦執行: sdownloader download --host <本機IP:{args.port or 8080}>")


def cmd_serve(args):
    redownload_parts = parse_part_numbers(args.redownload) if args.redownload else []
    server = DownloadServer(
        task_path=args.task,
        output_dir=args.output,
        port=args.port,
        auto_merge=not args.no_auto_merge,
        redownload_parts=redownload_parts,
    )
    server.start(also_download=not args.no_download)


def cmd_download(args):
    host_port = args.host.split(":")
    host = host_port[0]
    port = int(host_port[1]) if len(host_port) > 1 else 8080

    downloader = Downloader(args.output)

    while True:
        try:
            result = downloader.download_part_from_server(host, port, args.output)
            if result == (None, None):
                break

            filepath, checksum = result
            if filepath:
                print(f"已下載: {filepath} (MD5: {checksum})")
        except KeyboardInterrupt:
            print("\n下載已中斷")
            break
        except Exception as e:
            print(f"錯誤: {e}")
            break

    print("所有可用分拆已完成")


def cmd_merge(args):
    merger = Merger(args.output)
    try:
        output_path = merger.merge(args.task)
        print(f"\n還原檔案: {output_path}")
    except FileNotFoundError as e:
        print(f"錯誤: {e}")
        sys.exit(1)
    except ValueError as e:
        print(f"錯誤: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        prog="sdownloader",
        description="SDownloader - 智能分拆下載器，支援多機協作下載",
    )
    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    create_parser = subparsers.add_parser(
        "create", help="建立下載任務（產生 JSON 任務檔）"
    )
    create_parser.add_argument("--url", required=True, help="下載 URL")
    create_parser.add_argument(
        "--parts", type=int, required=True, help="分拆數量"
    )
    create_parser.add_argument(
        "--output", default=".", help="輸出目錄（預設: 目前目錄）"
    )
    create_parser.add_argument(
        "--port", type=int, default=8080, help="伺服器埠號（預設: 8080）"
    )

    serve_parser = subparsers.add_parser(
        "serve", help="啟動伺服器（分發任務 + 自動下載）"
    )
    serve_parser.add_argument("--task", required=True, help="任務檔路徑")
    serve_parser.add_argument(
        "--port", type=int, default=8080, help="伺服器埠號（預設: 8080）"
    )
    serve_parser.add_argument(
        "--output", default=".", help="輸出目錄（預設: 目前目錄）"
    )
    serve_parser.add_argument(
        "--no-download", action="store_true", help="主機不下載，只做協調"
    )
    serve_parser.add_argument(
        "--no-auto-merge", action="store_true", help="完成後不自動合併"
    )
    serve_parser.add_argument(
        "--redownload", help="重新下載指定的分拆（逗號分隔，如：1,3,5）"
    )

    download_parser = subparsers.add_parser(
        "download", help="從主機下載分拆檔"
    )
    download_parser.add_argument(
        "--host", required=True, help="主機地址（格式: IP:port）"
    )
    download_parser.add_argument(
        "--output", default=".", help="輸出目錄（預設: 目前目錄）"
    )

    merge_parser = subparsers.add_parser(
        "merge", help="合併分拆檔還原原始檔案"
    )
    merge_parser.add_argument("--task", required=True, help="任務檔路徑")
    merge_parser.add_argument(
        "--output", default=".", help="輸出目錄（預設: 目前目錄）"
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    commands = {
        "create": cmd_create,
        "serve": cmd_serve,
        "download": cmd_download,
        "merge": cmd_merge,
    }

    commands[args.command](args)


if __name__ == "__main__":
    main()
