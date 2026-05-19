# SDownloader - 智能分拆下載器

解決單機網路限速問題的多機協作下載工具。透過將檔案分拆成多個區塊，分配給多台電腦同時下載，最後合併還原原始檔案。

## 功能特色

- 自動分拆下載任務，動態分配給多台電腦
- 支援 HTTP Range Requests，不支援時自動降級為單線程
- 斷點續傳，中斷後可繼續下載
- 內建 HTTP Server，客戶端自動領取任務、下載、回傳
- 雙重 MD5 驗證（分拆驗證 + 合併後整體驗證）
- tqdm 即時進度條顯示

## 環境需求

- Python 3.7+
- Anaconda3（推薦）或 pip

## 安裝步驟

### 方式一：使用 Anaconda（推薦）

```bash
# 1. 建立 conda 環境
conda create -n downloader python=3.11 -y

# 2. 啟動環境
conda activate downloader

# 3. 安裝依賴
pip install tqdm

# 4. 安裝 SDownloader
cd SDownloader
pip install -e .
```

### 方式二：使用 pip

```bash
# 1. 建立虛擬環境（選用）
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux/Mac

# 2. 安裝依賴
pip install tqdm

# 3. 安裝 SDownloader
cd SDownloader
pip install -e .
```

## 使用方式

### 完整流程（多機協作）

假設有 4 個分拆，2 台電腦（主機 A + 客戶端 B）：

```
主機 A                              客戶端 B
──────                              ────────
1. create --parts 4                 
2. serve --port 8080                
                                    3. download --host <A的IP>:8080
   (主機 A 自動下載 part1)            (自動領取 part2 並下載)
   (完成 part1，領取 part3)           (完成 part2，領取 part4)
   (完成 part3)                      (完成 part4，回傳主機)
4. 自動合併 或 手動 merge
```

### 命令說明

#### 1. 建立任務（主機端）

```bash
sdownloader create --url <下載URL> --parts <分拆數量>
```

參數：
- `--url`：目標檔案的下載 URL（必填）
- `--parts`：分拆數量（必填）
- `--output`：輸出目錄，預設為目前目錄
- `--port`：伺服器埠號，預設為 8080

範例：
```bash
sdownloader create --url "https://releases.ubuntu.com/22.04/ubuntu-22.04-desktop-amd64.iso" --parts 4
```

產生 `ubuntu-22.04-desktop-amd64.iso.task.json` 任務檔。

#### 2. 啟動伺服器（主機端）

```bash
sdownloader serve --task <任務檔路徑>
```

參數：
- `--task`：任務檔路徑（必填）
- `--port`：伺服器埠號，預設為 8080
- `--output`：分拆檔儲存目錄，預設為目前目錄
- `--no-download`：主機只做協調，不下載分拆
- `--no-auto-merge`：所有分拆完成後不自動合併

範例：
```bash
sdownloader serve --task ubuntu-22.04-desktop-amd64.iso.task.json --port 8080
```

伺服器啟動後會：
- 顯示主機 IP 和連線資訊
- 主機自動領取並下載分拆
- 動態分發任務給連線的客戶端
- 收到所有分拆後自動合併

#### 3. 下載分拆（客戶端）

```bash
sdownloader download --host <主機IP:埠號>
```

參數：
- `--host`：主機地址，格式為 `IP:port`（必填）
- `--output`：分拆檔儲存目錄，預設為目前目錄

範例：
```bash
sdownloader download --host 192.168.1.100:8080
```

客戶端會自動：
- 從主機取得任務資訊
- 領取一個待下載的分拆
- 下載分拆檔（支援斷點續傳）
- 上傳分拆檔回主機
- 繼續領取下一個可用分拆

#### 4. 合併檔案（主機端）

```bash
sdownloader merge --task <任務檔路徑>
```

參數：
- `--task`：任務檔路徑（必填）
- `--output`：輸出目錄，預設為目前目錄

範例：
```bash
sdownloader merge --task ubuntu-22.04-desktop-amd64.iso.task.json
```

合併流程：
1. 驗證每個分拆檔的 MD5
2. 按順序合併所有分拆檔
3. 計算合併後檔案的整體 MD5
4. 輸出結果（分拆檔保留，不會自動刪除）

## 任務檔格式（JSON）

```json
{
  "task_id": "a1b2c3d4",
  "url": "https://example.com/bigfile.zip",
  "filename": "bigfile.zip",
  "file_size": 1073741824,
  "total_parts": 4,
  "range_supported": true,
  "parts": [
    {
      "part_number": 1,
      "start_byte": 0,
      "end_byte": 268435455,
      "filename": "bigfile.zip.part1",
      "status": "completed",
      "checksum": "d41d8cd98f00b204e9800998ecf8427e",
      "claimed_by": "host"
    }
  ],
  "created_at": "2026-05-19T10:00:00",
  "completed_at": "2026-05-19T10:15:00"
}
```

狀態值：
- `pending`：待下載
- `downloading`：下載中
- `completed`：已完成
- `failed`：失敗

## HTTP API

主機伺服器提供以下 API：

| 端點 | 方法 | 說明 |
|------|------|------|
| `/task` | GET | 取得任務檔 JSON |
| `/task/claim` | POST | 領取一個待下載的分拆 |
| `/task/complete` | POST | 回報分拆完成 + 上傳檔案 |
| `/task/status` | GET | 查看即時進度 |

## 常見問題

### Q: 目標伺服器不支援 Range Requests 怎麼辦？

執行 `create` 時會自動偵測並提示。降級為單線程下載，分拆功能無效。

### Q: 客戶端下載中斷了怎麼辦？

客戶端支援斷點續傳。重新執行 `download` 命令即可從斷點繼續。

### Q: 分拆數量要設多少？

建議設定為參與下載的電腦數量。例如 3 台電腦就設 `--parts 3`。

### Q: 主機 IP 怎麼查？

啟動 `serve` 後會自動顯示主機 IP。或在 Windows 執行 `ipconfig`，Linux/Mac 執行 `ifconfig`。

### Q: 防火牆需要開放嗎？

主機端需要開放 `--port` 指定的埠號（預設 8080）。Windows 防火牆設定：
1. 控制台 → 系統及安全性 → Windows Defender 防火牆
2. 進階設定 → 輸入規則 → 新增規則
3. 連接埠 → TCP → 特定本機連接埠 → 8080

## 專案結構

```
SDownloader/
├── sdownloader/
│   ├── __init__.py        # 版本號
│   ├── cli.py             # CLI 入口
│   ├── task.py            # 任務檔管理 + 動態分發
│   ├── downloader.py      # 下載引擎
│   ├── server.py          # HTTP Server
│   ├── merger.py          # 合併 + 驗證
│   └── utils.py           # 工具函數
├── setup.py
├── requirements.txt
└── README.md
```

## 授權

MIT License
