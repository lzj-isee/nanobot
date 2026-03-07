---
name: bilibili
description: Extract and display Bilibili followings dynamics (关注动态). Use when the user wants to check updates from followed UP masters on Bilibili, view recent posts/videos from their follow feed at https://t.bilibili.com/, or retrieve timeline content from Bilibili subscriptions.
metadata: {"nanobot":{"emoji":"📺","requires":{"bins":["python"],"pip":["playwright"]}}}
---

# Bilibili Followings

Extract dynamics from Bilibili follow feed (https://t.bilibili.com/). Retrieves recent posts, videos, and updates from followed UP masters.

## Cookie Setup

Cookie file location: `{baseDir}/scripts/.bilibili.cookie`

Required cookies: `SESSDATA`, `DedeUserID`, `DedeUserID__ckMd5`, `bili_jct`

Get from browser: Login to https://t.bilibili.com/ → F12 → Application → Cookies → Copy the 4 values.

If the script reports missing or invalid cookies, prompt the user to create/update the cookie file. If the user provides cookie content directly, create the file automatically.

## Usage

Default (no parameters needed):

```bash
python {baseDir}/scripts/bilibili_followings.py
```

**Parameters:**

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--cookie-file` | `{baseDir}/scripts/.bilibili.cookie` | Custom cookie file path (optional) |

## Output Format

The script outputs formatted dynamics with fields:
- `up_name` - UP master name
- `time_text` - Post time and type
- `content` - Text content (for articles/posts)
- `video_title` - Video title (for video posts)
- `video_desc` - Video description (for video posts)

Output is limited to 20 items and 3000 characters total.

## Error Handling

The script validates cookies before execution and reports:
- Missing cookie file
- Missing required cookie fields
- Expired session (login required)
