---
name: bilibili
description: Extract and display Bilibili content including followings dynamics, specific UP master feeds, and following list with fuzzy search. Use when the user wants to check updates from followed UP masters, view specific user's posts, or search their following list.
metadata: {"nanobot":{"emoji":"📺","requires":{"bins":["python"],"pip":["playwright"]}}}
---

# Bilibili Tools

Three scripts for extracting Bilibili content:

1. **bilibili_feed_following.py** - Get followings feed (关注动态流) - retrieves recent posts from all followed UP masters
2. **bilibili_feed_user.py** - Get specific UP master's dynamics (指定UP主动态) - retrieves posts from a specific user by UID
3. **bilibili_following_list.py** - Get following list with fuzzy search (关注列表) - retrieves all followed UP masters with nickname search

---

## Cookie Setup

Cookie file location: `{baseDir}/scripts/.bilibili.cookie`

Required cookies: `SESSDATA`, `DedeUserID`, `DedeUserID__ckMd5`, `bili_jct`

Get from browser: Login to https://t.bilibili.com/ → F12 → Application → Cookies → Copy the 4 values.

If the script reports missing or invalid cookies, prompt the user to create/update the cookie file. If the user provides cookie content directly, create the file automatically.

---

## Script 1: bilibili_feed_following.py

Extract dynamics from Bilibili follow feed (https://t.bilibili.com/). Retrieves recent posts, videos, and updates from all followed UP masters.

### Usage

```bash
python {baseDir}/scripts/bilibili_feed_following.py
```

### Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--cookie-file` | `{baseDir}/scripts/.bilibili.cookie` | Custom cookie file path |
| `--use-page` | `False` | Use page scraping mode (default uses API mode) |
| `--output`, `-o` | - | Output file path (saves to file instead of console) |

### Output Format

Fields in output:
- `up_name` - UP master name
- `time_text` - Post time
- `content` - Text content
- `video_title` - Video title (for video posts)
- `video_desc` - Video description

---

## Script 2: bilibili_feed_user.py

Get dynamics from a specific UP master by UID.

### Usage

```bash
python {baseDir}/scripts/bilibili_feed_user.py --uid 2137589551
```

### Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--uid`, `-u` | **Required** | UP master's UID |
| `--cookie-file` | `{baseDir}/scripts/.bilibili.cookie` | Custom cookie file path |
| `--limit`, `-l` | `20` | Maximum number of dynamics to retrieve |
| `--output`, `-o` | - | Output file path (saves to file instead of console) |
| `--format` | `text` | Output format: `text` or `json` |

### Dynamic Types

| Type | Description |
|------|-------------|
| 1 | 转发 (Repost) |
| 2 | 图文 (Image/Text) |
| 4 | 文字 (Text) |
| 8 | 视频 (Video) |
| 64 | 专栏 (Article) |
| 256 | 音频 (Audio) |
| 4200/4308 | 直播 (Live) |

---

## Script 3: bilibili_following_list.py

Get all followed UP masters list with fuzzy search support.

### Usage

```bash
# Get all followings
python {baseDir}/scripts/bilibili_following_list.py

# Fuzzy search by nickname (default top 10 results)
python {baseDir}/scripts/bilibili_following_list.py --name "老番茄"

# Show top 5 most similar results
python {baseDir}/scripts/bilibili_following_list.py --name "老番茄" --top 5

# Show all search results (no limit)
python {baseDir}/scripts/bilibili_following_list.py --name "老番茄" --top 0

# Save results to file
python {baseDir}/scripts/bilibili_following_list.py --name "老番茄" --output result.json
```

### Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--cookie-file` | `{baseDir}/scripts/.bilibili.cookie` | Custom cookie file path |
| `--name`, `-n` | - | Fuzzy search by nickname (partial match supported) |
| `--top`, `-t` | `10` | Show top N most similar results (0 = no limit) |
| `--output`, `-o` | - | Output file path |
| `--format` | `text` | Output format: `text` or `json` |

### Similarity Algorithm

When using `--name` search, results are sorted by similarity:
- **Exact match** → 100%
- **Substring match** → Up to 90% (position-weighted)
- **Prefix match** → Bonus points
- **Edit distance** → Based on `difflib.SequenceMatcher`

Similarity is displayed with star rating (★★★★★) and percentage.

### Output Fields

- `uid` - UP master UID
- `nickname` - UP master name
- `face` - Avatar URL
- `sign` - Personal signature
- `official_verify` - Verification badge
- `similarity` - Match similarity (when using name search)

---

## Output Length Limit

All scripts limit terminal output to **3000 characters**. If exceeded:
- Output is truncated at the last complete line
- Warning message: `⚠️ 输出内容过长（XXX 字符），已截断显示`
- Hint to use `--output` parameter to save full results to file

---

## Error Handling

If any error occurs (cookie issues, network problems, etc.), the script will display an error message. Inform the user of the error details and suggest solutions (e.g., updating cookies, checking network).

---

## Notes

- **Terminal output is usually sufficient** - The 3000-character limit covers most use cases. Only use `--output` when you need to save large amounts of data or process results programmatically.
- All scripts include anti-detection measures (random delays, browser fingerprint spoofing, API-first approach) to avoid 412 errors
