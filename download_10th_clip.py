#!/usr/bin/env python3
"""Download 10th Legislative Yuan Clip iVOD audio and raw API JSON.

Directory layout:

    output_dir/
      第10屆/
        第1會期/
          123456/
            123456.json
            123456.wav

The JSON file is fetched from the singular endpoint `/v2/ivod/{id}` because it
contains the full detail payload, including fields such as `data.gazette` when
available.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


LIST_API = "https://ly.govapi.tw/v2/ivods"
DETAIL_API_TEMPLATE = "https://ly.govapi.tw/v2/ivod/{ivod_id}"
TERM = 10
VIDEO_KIND = "Clip"


class DownloadError(Exception):
    """Raised when one iVOD item cannot be downloaded."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download 第10屆 Clip iVOD audio and full API JSON."
    )
    parser.add_argument(
        "--output-dir",
        default="downloads/ivod_clip",
        help="Base output directory. Default: downloads/ivod_clip",
    )
    parser.add_argument(
        "--start-date",
        default="2020-02-01",
        help="Start date for 第10屆 scan. Default: 2020-02-01",
    )
    parser.add_argument(
        "--end-date",
        default="2024-01-31",
        help="End date for 第10屆 scan. Default: 2024-01-31",
    )
    parser.add_argument(
        "--page-size",
        type=int,
        default=100,
        help="API page size for list queries. Default: 100",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=2,
        help="Concurrent download workers. ffmpeg is heavy; keep this low. Default: 2",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Process at most N items, useful for testing. Default: 0 means all.",
    )
    parser.add_argument(
        "--ffmpeg-bin",
        default="ffmpeg",
        help="ffmpeg executable path/name. Default: ffmpeg",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing JSON and WAV files.",
    )
    parser.add_argument(
        "--skip-audio",
        action="store_true",
        help="Only save API JSON, do not run ffmpeg.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch the list and print planned targets, but do not save/download.",
    )
    parser.add_argument(
        "--request-sleep",
        type=float,
        default=0.0,
        help="Seconds to sleep between list API date requests. Default: 0.",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=3,
        help="HTTP retry count. Default: 3",
    )
    return parser.parse_args()


def parse_date(value: str) -> dt.date:
    try:
        return dt.date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Invalid ISO date: {value}") from exc


def date_range(start: dt.date, end: dt.date):
    current = start
    while current <= end:
        yield current
        current += dt.timedelta(days=1)


def url_with_params(url: str, params: dict[str, Any]) -> str:
    query = urllib.parse.urlencode(params, doseq=True)
    return f"{url}?{query}"


def fetch_json(url: str, params: dict[str, Any] | None = None, retries: int = 3) -> Any:
    target = url_with_params(url, params) if params else url
    last_error: Exception | None = None

    for attempt in range(1, retries + 1):
        try:
            request = urllib.request.Request(
                target,
                headers={
                    "Accept": "application/json",
                    "User-Agent": "ly-download/1.0",
                },
            )
            with urllib.request.urlopen(request, timeout=30) as response:
                charset = response.headers.get_content_charset() or "utf-8"
                return json.loads(response.read().decode(charset))
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(min(2 ** (attempt - 1), 8))

    raise DownloadError(f"HTTP failed after {retries} attempts: {target}: {last_error}")


def fetch_list_page(day: dt.date, page: int, page_size: int, retries: int) -> dict[str, Any]:
    params = {
        "limit": page_size,
        "page": page,
        "影片種類": VIDEO_KIND,
        "屆": TERM,
        "日期": day.isoformat(),
    }
    data = fetch_json(LIST_API, params=params, retries=retries)
    if data.get("error"):
        raise DownloadError(f"List API error for {day} page {page}: {data.get('message')}")
    return data


def collect_clip_entries(args: argparse.Namespace) -> list[dict[str, Any]]:
    start = parse_date(args.start_date)
    end = parse_date(args.end_date)
    if start > end:
        raise ValueError("--start-date must be earlier than or equal to --end-date")

    by_id: dict[int, dict[str, Any]] = {}
    total_days = (end - start).days + 1

    for index, day in enumerate(date_range(start, end), start=1):
        first_page = fetch_list_page(day, 1, args.page_size, args.retries)
        total = int(first_page.get("total") or 0)
        total_page = int(first_page.get("total_page") or first_page.get("total_pages") or 0)
        if total:
            print(f"[list] {day} has {total} clips across {total_page} page(s)")

        for record in first_page.get("ivods") or []:
            ivod_id = record.get("IVOD_ID")
            if ivod_id is not None:
                by_id[int(ivod_id)] = record

        for page in range(2, total_page + 1):
            data = fetch_list_page(day, page, args.page_size, args.retries)
            for record in data.get("ivods") or []:
                ivod_id = record.get("IVOD_ID")
                if ivod_id is not None:
                    by_id[int(ivod_id)] = record

        if args.request_sleep > 0:
            time.sleep(args.request_sleep)

        if index % 100 == 0:
            print(f"[list] scanned {index}/{total_days} day(s), collected {len(by_id)} unique clips")

    entries = list(by_id.values())
    entries.sort(key=lambda item: int(item["IVOD_ID"]))
    if args.limit > 0:
        entries = entries[: args.limit]
    return entries


def get_session(record: dict[str, Any], detail: dict[str, Any] | None = None) -> int | str:
    sources = [record]
    if detail:
        sources.insert(0, detail.get("data") or {})

    for source in sources:
        meeting = source.get("會議資料") or {}
        session = meeting.get("會期")
        if session is not None:
            return session
    return "unknown"


def item_dir(output_dir: Path, record: dict[str, Any], detail: dict[str, Any] | None = None) -> Path:
    ivod_id = int(record["IVOD_ID"])
    session = get_session(record, detail)
    session_name = f"第{session}會期" if session != "unknown" else "未知會期"
    return output_dir / f"第{TERM}屆" / session_name / str(ivod_id)


def atomic_write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)
        file.write("\n")
    os.replace(tmp_path, path)


def load_existing_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except (OSError, json.JSONDecodeError):
        return None


def fetch_detail(ivod_id: int, retries: int) -> dict[str, Any]:
    data = fetch_json(DETAIL_API_TEMPLATE.format(ivod_id=ivod_id), retries=retries)
    if data.get("error"):
        raise DownloadError(f"Detail API error for {ivod_id}: {data.get('message')}")
    if not isinstance(data.get("data"), dict):
        raise DownloadError(f"Detail API missing data for {ivod_id}")
    return data


def run_ffmpeg(ffmpeg_bin: str, video_url: str, output_path: Path, overwrite: bool) -> None:
    if not video_url:
        raise DownloadError("missing video_url")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = output_path.with_suffix(".part.wav")
    if temp_path.exists():
        temp_path.unlink()

    cmd = [
        ffmpeg_bin,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y" if overwrite else "-n",
        "-i",
        video_url,
        "-vn",
        "-acodec",
        "pcm_s16le",
        "-ac",
        "1",
        "-f",
        "wav",
        str(temp_path),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        if temp_path.exists():
            temp_path.unlink()
        stderr = result.stderr.strip() or result.stdout.strip()
        raise DownloadError(f"ffmpeg failed: {stderr}")

    os.replace(temp_path, output_path)


def process_item(record: dict[str, Any], args: argparse.Namespace, output_dir: Path) -> dict[str, Any]:
    ivod_id = int(record["IVOD_ID"])

    # Initial path from list data. If detail has a different session value, recompute after fetch.
    target_dir = item_dir(output_dir, record)
    json_path = target_dir / f"{ivod_id}.json"
    wav_path = target_dir / f"{ivod_id}.wav"

    detail = None if args.overwrite else load_existing_json(json_path)
    if detail is None:
        detail = fetch_detail(ivod_id, args.retries)

    detail_dir = item_dir(output_dir, record, detail)
    if detail_dir != target_dir:
        target_dir = detail_dir
        json_path = target_dir / f"{ivod_id}.json"
        wav_path = target_dir / f"{ivod_id}.wav"

    target_dir.mkdir(parents=True, exist_ok=True)
    if args.overwrite or not json_path.exists():
        atomic_write_json(json_path, detail)

    video_url = (detail.get("data") or {}).get("video_url") or record.get("video_url")
    if not args.skip_audio:
        if args.overwrite or not wav_path.exists():
            run_ffmpeg(args.ffmpeg_bin, video_url, wav_path, args.overwrite)

    return {
        "ivod_id": ivod_id,
        "json": str(json_path),
        "wav": str(wav_path),
        "session": get_session(record, detail),
        "has_gazette": (detail.get("data") or {}).get("gazette") is not None,
    }


def batched(items: list[dict[str, Any]], size: int):
    for start in range(0, len(items), size):
        yield items[start : start + size]


def process_entries(
    entries: list[dict[str, Any]],
    args: argparse.Namespace,
    output_dir: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    rows: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    completed = 0
    total = len(entries)
    batch_size = max(1, args.workers) * 4

    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        for batch in batched(entries, batch_size):
            future_to_id = {
                executor.submit(process_item, record, args, output_dir): int(record["IVOD_ID"])
                for record in batch
            }
            batch_rows: list[dict[str, Any]] = []

            for future in concurrent.futures.as_completed(future_to_id):
                ivod_id = future_to_id[future]
                completed += 1
                try:
                    row = future.result()
                    batch_rows.append(row)
                    print(f"[{completed}/{total}] ok {ivod_id} session={row['session']}")
                except Exception as exc:
                    message = str(exc)
                    failures.append({"ivod_id": str(ivod_id), "error": message})
                    print(f"[{completed}/{total}] failed {ivod_id}: {message}", file=sys.stderr)

            batch_rows.sort(key=lambda item: int(item["ivod_id"]))
            rows.extend(batch_rows)

    return rows, failures


def write_manifest(output_dir: Path, rows: list[dict[str, Any]]) -> None:
    manifest_path = output_dir / f"第{TERM}屆" / "manifest.json"
    atomic_write_json(
        manifest_path,
        {
            "term": TERM,
            "video_kind": VIDEO_KIND,
            "count": len(rows),
            "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
            "items": rows,
        },
    )


def write_summary(
    output_dir: Path,
    total_video_count: int,
    rows: list[dict[str, Any]],
    failures: list[dict[str, str]],
) -> None:
    missing_gazette_count = sum(1 for row in rows if not row.get("has_gazette"))

    summary_path = output_dir / "summury.txt"
    summary_path.parent.mkdir(parents=True, exist_ok=True)

    with summary_path.open("w", encoding="utf-8") as file:
        file.write(f"產生時間: {dt.datetime.now().isoformat(timespec='seconds')}\n")
        file.write(f"下載範圍: 第{TERM}屆 {VIDEO_KIND}\n")
        file.write(f"總共有多少個影片: {total_video_count}\n")
        file.write(f"已完成 API 檢查影片數: {len(rows)}\n")
        file.write(f"API 中沒有 gazette 的影片數: {missing_gazette_count}\n")
        file.write("\n")
        file.write("API 中沒有 gazette 的 IVOD_ID:\n")

        wrote_missing = False
        for row in rows:
            if not row.get("has_gazette"):
                file.write(f"{int(row['ivod_id'])}\n")
                wrote_missing = True
        if not wrote_missing:
            file.write("無\n")

        if failures:
            file.write("\n")
            file.write(f"處理失敗影片數: {len(failures)}\n")
            file.write("處理失敗 IVOD_ID:\n")
            for item in failures:
                file.write(f"{item['ivod_id']}: {item['error']}\n")


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir).expanduser().resolve()

    try:
        entries = collect_clip_entries(args)
    except Exception as exc:
        print(f"Failed to collect list: {exc}", file=sys.stderr)
        return 1

    print(f"Collected {len(entries)} 第{TERM}屆 {VIDEO_KIND} item(s)")
    if args.dry_run:
        for record in entries[:20]:
            ivod_id = int(record["IVOD_ID"])
            session = get_session(record)
            date = record.get("日期", "")
            member = record.get("委員名稱", "")
            print(f"{ivod_id}\t第{session}會期\t{date}\t{member}")
        if len(entries) > 20:
            print(f"... {len(entries) - 20} more item(s)")
        return 0

    rows, failures = process_entries(entries, args, output_dir)
    write_manifest(output_dir, rows)
    write_summary(output_dir, len(entries), rows, failures)

    if failures:
        failure_path = output_dir / f"第{TERM}屆" / "failures.json"
        atomic_write_json(failure_path, failures)
        print(f"Completed with {len(failures)} failure(s). See {failure_path}", file=sys.stderr)
        return 2

    print(f"Completed successfully. Output: {output_dir / f'第{TERM}屆'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
