# LY iVOD 第 10 屆 Clip 下載腳本

這個專案目前主要腳本是：

```bash
download_10th_clip.py
```

用途：

- 查詢 LYAPI 第 10 屆 `Clip` 類型 iVOD。
- 依照 `會期` 分資料夾。
- 每個 `IVOD_ID` 建立獨立資料夾。
- 保存完整 API JSON。
- 使用 `ffmpeg` 從 `video_url` 抽出單聲道 PCM WAV。
- 在輸出最外層產生 `summury.txt`，統計影片數與沒有 `gazette` 的 IVOD_ID。

## 需求

需要本機有：

```bash
python3
ffmpeg
ffprobe
```

Python 套件依賴：

```bash
pip install -r requirements.txt
```

目前腳本只使用 Python 標準函式庫，所以 `requirements.txt` 不會安裝額外套件。

確認 ffmpeg 是否存在：

```bash
command -v ffmpeg
```

## 基本執行

```bash
python3 download_10th_clip.py --output-dir downloads/ivod_clip
```

預設會掃描：

```text
第10屆
影片種類 Clip
日期 2020-02-01 到 2024-01-31
```

## 輸出結構

假設 `--output-dir downloads/ivod_clip`，輸出會像這樣：

```text
downloads/ivod_clip/
  summury.txt
  第10屆/
    manifest.json
    第1會期/
      123456/
        123456.json
        123456.wav
    第8會期/
      149077/
        149077.json
        149077.wav
```

每個 IVOD_ID 資料夾內：

- `{IVOD_ID}.json`: `https://ly.govapi.tw/v2/ivod/{IVOD_ID}` 的完整 API JSON。
- `{IVOD_ID}.wav`: 從 API 的 `data.video_url` 下載並轉出的音訊。

音訊格式：

```bash
ffmpeg -i VIDEO_URL -vn -acodec pcm_s16le -ac 1 output.wav
```

## summury.txt

`summury.txt` 會放在 `--output-dir` 最外層，例如：

```text
downloads/ivod_clip/summury.txt
```

內容包含：

- 產生時間
- 下載範圍
- 總共有多少個影片
- 已完成 API 檢查影片數
- API 中沒有 `gazette` 的影片數
- API 中沒有 `gazette` 的 IVOD_ID 清單
- 若有失敗，列出失敗 IVOD_ID 與錯誤訊息

## 常用參數

### 只測試清單，不下載

```bash
python3 download_10th_clip.py --dry-run --limit 10
```

### 只抓 JSON，不下載音訊

```bash
python3 download_10th_clip.py --skip-audio --limit 10 --output-dir downloads/test_json
```

### 限制只處理前 N 筆

```bash
python3 download_10th_clip.py --limit 100 --output-dir downloads/test_100
```

### 指定日期區間

```bash
python3 download_10th_clip.py \
  --start-date 2024-01-09 \
  --end-date 2024-01-09 \
  --output-dir downloads/one_day
```

### 調整同時下載數

```bash
python3 download_10th_clip.py --workers 2 --output-dir downloads/ivod_clip
```

`ffmpeg` 下載與轉檔很吃網路、CPU、磁碟 I/O。建議 `--workers` 不要設太高，通常 `1` 到 `3` 比較穩。

### 覆蓋既有檔案

```bash
python3 download_10th_clip.py --overwrite --output-dir downloads/ivod_clip
```

未加 `--overwrite` 時，已存在的 JSON 和 WAV 會盡量略過，方便斷點續跑。

### 指定 ffmpeg 路徑

```bash
python3 download_10th_clip.py \
  --ffmpeg-bin /opt/homebrew/bin/ffmpeg \
  --output-dir downloads/ivod_clip
```

## 建議流程

先做 dry-run：

```bash
python3 download_10th_clip.py --dry-run --limit 10
```

再測試少量 JSON：

```bash
python3 download_10th_clip.py --skip-audio --limit 10 --output-dir downloads/test_json
```

再測試少量音訊：

```bash
python3 download_10th_clip.py --limit 3 --workers 1 --output-dir downloads/test_audio
```

確認沒問題後跑完整下載：

```bash
python3 download_10th_clip.py --workers 2 --output-dir downloads/ivod_clip
```

## 注意事項

- LYAPI 對太深的分頁可能回傳錯誤，所以腳本採用逐日期查詢，避免直接拉很後面的 page。
- 單筆完整 JSON 使用 singular endpoint：`https://ly.govapi.tw/v2/ivod/{IVOD_ID}`。
- `gazette` 判斷方式是檢查完整 JSON 中的 `data.gazette` 是否存在。
- 完整下載第 10 屆 Clip 數量很大，會花較久時間並占用大量磁碟空間。

## 致謝

本專案感謝 [OPEN FUN](https://openfun.tw/) 統整並建立資料網頁與 API。
