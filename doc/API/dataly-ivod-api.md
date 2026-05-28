# Dataly iVOD / LYAPI 使用筆記

觀察頁面：

<https://dataly.openfun.app/collection/list/ivod/table?agg=%E5%B1%86&agg=%E5%BD%B1%E7%89%87%E7%A8%AE%E9%A1%9E>

Dataly 是前端資料瀏覽介面，表格資料實際由 LYAPI v2 提供。官方入口與文件：

- LYAPI: <https://ly.govapi.tw/v2/>
- Swagger: <https://ly.govapi.tw/v2/swagger>
- OpenAPI YAML: <https://ly.govapi.tw/v2/swagger.yaml>

## 列表 API

```http
GET https://ly.govapi.tw/v2/ivods
```

頁面初始請求：

```http
GET https://ly.govapi.tw/v2/ivods?limit=10&page=1&agg=%E5%B1%86&agg=%E5%BD%B1%E7%89%87%E7%A8%AE%E9%A1%9E
```

解碼後：

```text
limit=10
page=1
agg=屆
agg=影片種類
```

## 常用查詢參數

| 參數 | 用途 |
| --- | --- |
| `limit` | 每頁筆數。`0` 代表不取資料列，常用於只取統計或欄位資訊。 |
| `page` | 頁數，從 `1` 開始。 |
| `q` | 全文搜尋字串。Dataly 前端會把每個空白切開的關鍵字包成 `"關鍵字"` 後送出。 |
| `agg` | facet / 聚合欄位，可重複帶多個。 |
| `output_fields` | 指定輸出欄位，OpenAPI 有列出，但 Dataly 表格頁沒有使用。 |

## 支援篩選欄位

`GET /v2/ivods?limit=0` 回傳的 `supported_filter_fields` 目前包含：

```text
屆
會期
會議.會議代碼
委員名稱
會議資料.委員會代碼
會議資料.會議代碼
日期
影片種類
```

其中 `影片種類` 常見值：

```text
Clip
Full
```

## 範例

取前 10 筆，並取得 `屆`、`影片種類` 聚合統計：

```http
GET https://ly.govapi.tw/v2/ivods?limit=10&page=1&agg=屆&agg=影片種類
```

篩選第 11 屆：

```http
GET https://ly.govapi.tw/v2/ivods?limit=10&page=1&屆=11
```

篩選第 11 屆，並回傳影片種類聚合：

```http
GET https://ly.govapi.tw/v2/ivods?limit=10&page=1&agg=影片種類&屆=11
```

搜尋委員名稱或全文關鍵字：

```http
GET https://ly.govapi.tw/v2/ivods?limit=10&page=1&q=%22翁曉玲%22&agg=屆
```

使用篩選欄位查委員：

```http
GET https://ly.govapi.tw/v2/ivods?limit=10&page=1&委員名稱=翁曉玲
```

只取欄位與統計資訊，不取列表資料：

```http
GET https://ly.govapi.tw/v2/ivods?limit=0&agg=屆
```

## 列表回傳格式

`GET /v2/ivods` 回傳大致格式：

```json
{
  "total": 102979,
  "total_page": 51490,
  "page": 1,
  "limit": 2,
  "filter": {},
  "id_fields": ["IVOD_ID"],
  "sort": ["會議時間"],
  "output_fields": [
    "video_url",
    "會議時間",
    "會議名稱",
    "委員名稱",
    "影片長度",
    "委員發言時間",
    "IVOD_ID",
    "IVOD_URL",
    "日期",
    "會議資料",
    "影片種類",
    "開始時間",
    "結束時間",
    "支援功能"
  ],
  "ivods": [
    {
      "IVOD_ID": 169665,
      "IVOD_URL": "https://ivod.ly.gov.tw/Play/Clip/1M/169665",
      "日期": "2026-05-28",
      "影片種類": "Clip",
      "開始時間": "2026-05-28T09:18:22+08:00",
      "結束時間": "2026-05-28T09:30:47+08:00",
      "影片長度": 745,
      "支援功能": ["ai-transcript"],
      "video_url": "https://.../playlist.m3u8",
      "委員名稱": "翁曉玲",
      "委員發言時間": "09:18:22 - 09:30:47",
      "會議時間": "2026-05-28T09:00:00+08:00",
      "會議名稱": "立法院第11屆第5會期司法及法制委員會第15次全體委員會議..."
    }
  ],
  "aggs": [
    {
      "agg": "屆",
      "agg_fields": ["屆"],
      "buckets": [
        {"屆": 11, "count": 21217}
      ]
    }
  ],
  "supported_filter_fields": [
    "屆",
    "會期",
    "會議.會議代碼",
    "委員名稱",
    "會議資料.委員會代碼",
    "會議資料.會議代碼",
    "日期",
    "影片種類"
  ]
}
```

## 單筆 API

Dataly 列表每筆資料會連到：

```text
/collection/item/ivod/{IVOD_ID}
```

對應 LYAPI 單筆資料：

```http
GET https://ly.govapi.tw/v2/ivods/{IVOD_ID}
```

範例：

```http
GET https://ly.govapi.tw/v2/ivods/169665
```

單筆回傳會包在 `data`：

```json
{
  "error": false,
  "id": ["169665"],
  "data": {
    "IVOD_ID": 169665,
    "IVOD_URL": "https://ivod.ly.gov.tw/Play/Clip/1M/169665",
    "video_url": "https://.../playlist.m3u8",
    "日期": "2026-05-28",
    "委員名稱": "翁曉玲",
    "影片種類": "Clip",
    "影片長度": "00:12:25",
    "transcript": {
      "pyannote": []
    }
  }
}
```

注意：列表 API 的 `影片長度` 是秒數整數，單筆 API 觀察到的是 `HH:MM:SS` 字串。

## Dataly 前端行為

Dataly 表格使用 server-side DataTables。頁面內嵌的初始化設定包含：

```js
var table_config = {
  type: "ivod",
  aggs: ["屆", "影片種類"],
  data_column: "ivods",
  columns: ["IVOD_ID", "日期", "委員發言時間", "委員名稱", "會議名稱"],
  filter: []
};
```

表格列資料來自 `ret[table_config.data_column]`，也就是 `ret.ivods`。

前端顯示欄位：

```text
IVOD_ID
日期
委員發言時間
委員名稱
會議名稱
連結
```

`連結` 欄位由 `IVOD_ID` 組成：

```text
/collection/item/ivod/{IVOD_ID}
```

## Facet / 篩選更新規則

如果沒有篩選，頁面只打一個主查詢：

```http
GET https://ly.govapi.tw/v2/ivods?limit=10&page=1&agg=屆&agg=影片種類
```

如果使用者勾選 `屆=11`，頁面會：

1. 主查詢排除正在被篩選的 facet `屆`，只查其他聚合欄位。
2. 額外打一個 `limit=0&agg=屆` 來更新 `屆` facet 的選項統計。

實際觀察到的請求：

```http
GET https://ly.govapi.tw/v2/ivods?limit=10&page=1&agg=影片種類&屆=11
GET https://ly.govapi.tw/v2/ivods?limit=0&agg=屆
```

如果篩選多個欄位，Dataly 會為每個被篩選的 facet 額外發出一個 `limit=0&agg={field}` 請求，且該 facet 自己的統計請求會排除同欄位篩選，保留其他欄位篩選。

## URL 對照

Dataly 頁面 URL 使用自己的參數格式：

```text
agg=屆
agg=影片種類
filter=屆:11
q=翁曉玲
page=2
limit=25
```

LYAPI 實際請求會轉成：

```text
agg=屆
agg=影片種類
屆=11
q=%22翁曉玲%22
page=2
limit=25
```

也就是 Dataly 的 `filter=欄位:值` 只是前端 URL 狀態，打 API 時會變成真正的 query parameter：`欄位=值`。
