"""
Bilibili 指定UP主动态获取脚本
获取指定UID的UP主首页动态（最近更新的动态）

使用方法:
    python bilibili_feed_user.py --uid 2137589551                    # 获取指定UP主的动态
    python bilibili_feed_user.py --uid 2137589551 --limit 20         # 限制获取数量
    python bilibili_feed_user.py --uid 2137589551 --cookie-file /path/to/cookie.txt

API 接口:
    https://api.vc.bilibili.com/dynamic_svr/v1/dynamic_svr/space_history?host_uid={uid}
"""

import argparse
import asyncio
import json
import os
import random
import re
import sys
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from urllib.parse import urlencode

from playwright.async_api import async_playwright


# 必需的 Cookie 名称
REQUIRED_COOKIES = ["SESSDATA", "DedeUserID", "DedeUserID__ckMd5", "bili_jct"]


@dataclass
class UserDynamicItem:
    """UP主动态项数据结构"""
    dynamic_id: str
    dynamic_type: str  # 动态类型
    timestamp: int     # 时间戳
    time_text: str     # 格式化的时间
    content: str       # 动态内容
    pics: List[str]    # 图片列表
    video_title: Optional[str] = None
    video_desc: Optional[str] = None
    video_bvid: Optional[str] = None
    repost_content: Optional[str] = None  # 转发的内容
    origin_user: Optional[str] = None     # 原动态作者


def parse_cookie_file(file_path: str) -> Dict[str, str]:
    """
    解析 cookie 文件，提取必需的 cookie

    文件格式: key=value; key2=value2; ...
    支持从浏览器直接复制的 cookie 字符串格式
    """
    path = Path(file_path)

    # 检查文件是否存在
    if not path.exists():
        raise FileNotFoundError(f"Cookie 文件不存在: {file_path}\n"
                                f"请创建该文件并将从浏览器复制的 cookie 粘贴进去。\n"
                                f"获取方法: 浏览器开发者工具 -> Application -> Cookies -> https://t.bilibili.com")

    # 检查文件是否为空
    if path.stat().st_size == 0:
        raise ValueError(f"Cookie 文件为空: {file_path}\n"
                         f"请将 cookie 内容粘贴到该文件中。")

    # 读取文件内容
    content = path.read_text(encoding='utf-8').strip()

    if not content:
        raise ValueError(f"Cookie 文件内容为空: {file_path}\n"
                         f"请将 cookie 内容粘贴到该文件中。")

    # 解析 cookie（格式: key=value; key2=value2; ...）
    cookies = {}

    # 按分号分割，但注意 value 中可能包含分号（如 URL 编码的字符）
    # 使用正则表达式匹配 key=value 对
    # 支持 value 被引号包围的情况
    pattern = r'([^=;]+)=([^;]*)(?:;|$)'
    matches = re.findall(pattern, content)

    for key, value in matches:
        key = key.strip()
        value = value.strip()
        if key:
            cookies[key] = value

    # 检查是否包含所有必需的 cookie
    missing_cookies = [name for name in REQUIRED_COOKIES if name not in cookies]

    if missing_cookies:
        raise ValueError(f"Cookie 文件缺少必需的字段: {', '.join(missing_cookies)}\n"
                         f"已找到的字段: {', '.join(cookies.keys())}\n\n"
                         f"请确保文件中包含以下 4 个必需字段:\n"
                         f"  - SESSDATA\n"
                         f"  - DedeUserID\n"
                         f"  - DedeUserID__ckMd5\n"
                         f"  - bili_jct\n\n"
                         f"获取方法: 浏览器登录 bilibili.com 后，\n"
                         f"  按 F12 -> Application -> Cookies -> https://t.bilibili.com\n"
                         f"  复制这 4 个字段的值，保存到文件中。")

    return {name: cookies[name] for name in REQUIRED_COOKIES}


def build_cookie_list(cookie_dict: Dict[str, str]) -> List[Dict]:
    """将 cookie 字典转换为 playwright 需要的格式"""
    return [
        {
            "name": name,
            "value": value,
            "domain": ".bilibili.com",
            "path": "/",
        }
        for name, value in cookie_dict.items()
    ]


async def random_delay(min_ms: int = 500, max_ms: int = 2000):
    """随机延迟，模拟人类操作"""
    delay = random.randint(min_ms, max_ms) / 1000
    await asyncio.sleep(delay)


def format_timestamp(ts: int) -> str:
    """将时间戳格式化为可读字符串"""
    from datetime import datetime
    try:
        dt = datetime.fromtimestamp(ts)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except:
        return str(ts)


def parse_dynamic_content(item: Dict) -> UserDynamicItem:
    """解析单条动态数据"""
    # 从 desc 中获取基本信息
    desc = item.get("desc", {})

    dynamic_id = str(desc.get("dynamic_id", ""))
    dynamic_type = str(desc.get("type", ""))
    timestamp = desc.get("timestamp", 0)
    time_text = format_timestamp(timestamp)

    # 获取卡片信息（card 是 JSON 字符串）
    card_str = item.get("card", "{}")
    try:
        card = json.loads(card_str) if isinstance(card_str, str) else card_str
    except:
        card = {}

    content = ""
    pics = []
    video_title = None
    video_desc = None
    video_bvid = desc.get("bvid", "")  # BV号在 desc 中
    repost_content = None
    origin_user = None

    # 根据动态类型解析内容
    # 1: 转发, 2: 图文, 4: 文字, 8: 视频, 64: 专栏, 256: 音频, 2048: 专题, 4200: 直播

    if dynamic_type == "1":  # 转发
        # 获取转发内容
        item_content = card.get("item", {})
        content = item_content.get("content", "")

        # 获取原动态信息
        origin = card.get("origin", "{}")
        try:
            origin_card = json.loads(origin) if isinstance(origin, str) else origin
        except:
            origin_card = {}

        # 原动态作者
        origin_user_info = card.get("origin_user", {}).get("info", {})
        origin_user = origin_user_info.get("uname", "")

        # 原动态内容
        if origin_card:
            origin_item = origin_card.get("item", {})
            repost_content = origin_item.get("description", "") or origin_item.get("content", "")
            if not repost_content:
                repost_content = origin_card.get("dynamic", "")

    elif dynamic_type == "2":  # 图文动态
        item_content = card.get("item", {})
        content = item_content.get("description", "") or item_content.get("content", "")
        pics = [pic.get("img_src", "") for pic in item_content.get("pictures", [])]

    elif dynamic_type == "4":  # 文字动态
        item_content = card.get("item", {})
        content = item_content.get("content", "")

    elif dynamic_type == "8":  # 视频投稿
        content = card.get("dynamic", "")
        video_title = card.get("title", "")
        video_desc = card.get("desc", "")
        # video_bvid 已经从 desc 中获取

    elif dynamic_type == "64":  # 专栏
        content = card.get("dynamic", "")
        video_title = card.get("title", "")  # 专栏标题
        video_desc = card.get("summary", "")  # 专栏摘要

    else:  # 其他类型
        content = card.get("dynamic", "") or card.get("desc", "")

    return UserDynamicItem(
        dynamic_id=dynamic_id,
        dynamic_type=dynamic_type,
        timestamp=timestamp,
        time_text=time_text,
        content=content,
        pics=pics,
        video_title=video_title,
        video_desc=video_desc,
        video_bvid=video_bvid,
        repost_content=repost_content,
        origin_user=origin_user
    )


async def fetch_user_dynamics(page, uid: str, limit: int = 20) -> List[UserDynamicItem]:
    """
    获取指定UP主的动态列表
    """
    dynamics = []
    offset = ""
    count = 0

    print(f"开始获取 UP主 {uid} 的动态...")

    # 先访问主页建立会话
    print("正在建立会话...")
    await page.goto("https://bilibili.com", wait_until="networkidle")
    await random_delay(1000, 2000)

    while count < limit:
        # 构建 API 请求参数
        params = {
            "host_uid": uid,
            "need_top": "1",
        }
        if offset:
            params["offset_dynamic_id"] = offset

        api_url = f"https://api.vc.bilibili.com/dynamic_svr/v1/dynamic_svr/space_history?{urlencode(params)}"
        print(f"正在获取动态... (已获取 {count} 条)")

        # 使用页面执行 fetch 请求（携带当前页面的 cookie）
        response_data = await page.evaluate(f"""
            async () => {{
                try {{
                    const response = await fetch("{api_url}", {{
                        method: 'GET',
                        credentials: 'include'
                    }});
                    return await response.json();
                }} catch (e) {{
                    return {{ error: e.message }};
                }}
            }}
        """)

        if not response_data or response_data.get("code") != 0:
            error_msg = response_data.get("message", "未知错误") if response_data else "无响应"
            print(f"API 请求失败: {error_msg}")
            break

        data = response_data.get("data", {})
        cards = data.get("cards", [])
        has_more = data.get("has_more", 0)

        if not cards:
            print("没有更多动态了")
            break

        for card in cards:
            if count >= limit:
                break

            try:
                dynamic = parse_dynamic_content(card)
                dynamics.append(dynamic)
                count += 1

                # 更新 offset 用于下一页 - 从 desc 中获取 dynamic_id_str
                desc = card.get("desc", {})
                offset = str(desc.get("dynamic_id_str", ""))
            except Exception as e:
                print(f"解析动态时出错: {e}")
                continue

        print(f"本页获取到 {len(cards)} 条动态，共 {count} 条")

        if not has_more or count >= limit:
            break

        await random_delay(800, 1500)  # 分页之间添加延迟

    print(f"共获取到 {len(dynamics)} 条动态")
    return dynamics


def get_dynamic_type_name(dynamic_type: str) -> str:
    """获取动态类型的中文名称"""
    type_map = {
        "1": "转发",
        "2": "图文",
        "4": "文字",
        "8": "视频",
        "64": "专栏",
        "256": "音频",
        "2048": "专题",
        "4200": "直播",
        "4308": "直播",
    }
    return type_map.get(dynamic_type, f"未知({dynamic_type})")


def format_dynamics(dynamics: List[UserDynamicItem], output_format: str = "text") -> str:
    """格式化动态列表为字符串"""
    if output_format == "json":
        data = [
            {
                "dynamic_id": dyn.dynamic_id,
                "dynamic_type": dyn.dynamic_type,
                "dynamic_type_name": get_dynamic_type_name(dyn.dynamic_type),
                "timestamp": dyn.timestamp,
                "time_text": dyn.time_text,
                "content": dyn.content,
                "pics": dyn.pics,
                "video_title": dyn.video_title,
                "video_desc": dyn.video_desc,
                "video_bvid": dyn.video_bvid,
                "repost_content": dyn.repost_content,
                "origin_user": dyn.origin_user,
            }
            for dyn in dynamics
        ]
        return json.dumps(data, ensure_ascii=False, indent=2)
    else:
        # 文本格式
        lines = []
        lines.append(f"共 {len(dynamics)} 条动态\n")
        lines.append("=" * 50)

        for i, dyn in enumerate(dynamics, 1):
            lines.append(f"\n【{i}】{get_dynamic_type_name(dyn.dynamic_type)}  {dyn.time_text}")
            lines.append("-" * 50)

            if dyn.content:
                lines.append(f"内容: {dyn.content}")

            if dyn.video_title:
                lines.append(f"视频标题: {dyn.video_title}")
                if dyn.video_bvid:
                    lines.append(f"BV号: {dyn.video_bvid}")
                if dyn.video_desc:
                    lines.append(f"视频简介: {dyn.video_desc}")

            if dyn.pics:
                lines.append(f"图片: {len(dyn.pics)} 张")
                for pic in dyn.pics[:3]:  # 只显示前3张图片链接
                    lines.append(f"  - {pic}")
                if len(dyn.pics) > 3:
                    lines.append(f"  ... 还有 {len(dyn.pics) - 3} 张")

            if dyn.origin_user:
                lines.append(f"转发自: @{dyn.origin_user}")
                if dyn.repost_content:
                    lines.append(f"原内容: {dyn.repost_content}")

            lines.append("")

        return "\n".join(lines)


async def main():
    # 获取脚本所在目录
    script_dir = Path(__file__).parent.absolute()
    default_cookie_file = script_dir / ".bilibili.cookie"

    # 解析命令行参数
    parser = argparse.ArgumentParser(
        description="获取指定 Bilibili UP主 的动态",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python bilibili_feed_user.py --uid 2137589551                    # 获取指定UP主的动态
  python bilibili_feed_user.py --uid 2137589551 --limit 50         # 获取50条动态
  python bilibili_feed_user.py --uid 2137589551 --output dynamics.json  # 保存到文件
  python bilibili_feed_user.py --uid 2137589551 --format json      # JSON格式输出

动态类型说明:
  1: 转发    2: 图文    4: 文字    8: 视频    64: 专栏
        """
    )
    parser.add_argument(
        "--uid",
        "-u",
        type=str,
        required=True,
        help="UP主的 UID（必需）"
    )
    parser.add_argument(
        "--cookie-file",
        type=str,
        default=str(default_cookie_file),
        help=f"Cookie 文件路径 (默认: {default_cookie_file})"
    )
    parser.add_argument(
        "--limit",
        "-l",
        type=int,
        default=20,
        help="获取动态数量限制 (默认: 20)"
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        help="输出文件路径（如果不指定则输出到控制台）"
    )
    parser.add_argument(
        "--format",
        type=str,
        choices=["text", "json"],
        default="text",
        help="输出格式: text 或 json (默认: text)"
    )
    args = parser.parse_args()

    # 常量：终端输出最大字符数
    MAX_TERMINAL_OUTPUT = 3000

    # 解析 cookie 文件
    try:
        cookie_dict = parse_cookie_file(args.cookie_file)
        print(f"成功从 {args.cookie_file} 加载 {len(cookie_dict)} 个必需 Cookie")
    except (FileNotFoundError, ValueError) as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)

    async with async_playwright() as p:
        # 启动浏览器 - 使用反检测参数
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-web-security",
                "--disable-features=IsolateOrigins,site-per-process",
                "--disable-site-isolation-trials",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-infobars",
                "--window-size=1280,800",
                "--start-maximized",
                "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            ]
        )

        # 创建上下文 - 模拟真实浏览器环境
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            screen={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
        )

        # 添加 cookies
        cookies = build_cookie_list(cookie_dict)
        await context.add_cookies(cookies)
        print(f"已加载 {len(cookies)} 个 Cookie")

        page = await context.new_page()

        # 注入反检测脚本
        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            Object.defineProperty(navigator, 'plugins', {
                get: () => [
                    {name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer'},
                    {name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai'},
                    {name: 'Native Client', filename: 'internal-nacl-plugin'}
                ]
            });
            Object.defineProperty(navigator, 'languages', {
                get: () => ['zh-CN', 'zh', 'en']
            });
            delete navigator.__proto__.webdriver;
        """)

        try:
            dynamics = await fetch_user_dynamics(page, args.uid, limit=args.limit)

            if dynamics:
                formatted = format_dynamics(dynamics, output_format=args.format)

                if args.output:
                    # 写入文件
                    output_path = Path(args.output)
                    output_path.write_text(formatted, encoding='utf-8')
                    print(f"\n结果已保存到: {args.output}")
                    print(f"共 {len(dynamics)} 条动态")
                else:
                    # 输出到控制台，检查长度限制
                    if len(formatted) > MAX_TERMINAL_OUTPUT:
                        # 截断输出并提示
                        truncated = formatted[:MAX_TERMINAL_OUTPUT]
                        # 尝试在最后一个完整行截断
                        last_newline = truncated.rfind('\n')
                        if last_newline > MAX_TERMINAL_OUTPUT * 0.8:
                            truncated = truncated[:last_newline]
                        print("\n" + "="*50)
                        print(truncated)
                        print("\n" + "="*50)
                        print(f"\n⚠️  输出内容过长（{len(formatted)} 字符），已截断显示")
                        print(f"💡 提示：使用 --output <文件路径> 参数可将完整结果保存到文件")
                        print(f"   例如: python {Path(__file__).name} --uid {args.uid} --output result.json")
                    else:
                        # 输出到控制台
                        print("\n" + "="*50)
                        print(formatted)
                        print("="*50)
            else:
                print("未获取到任何动态")

        except Exception as e:
            print(f"执行出错: {e}")
            import traceback
            traceback.print_exc()

        finally:
            await browser.close()
            print("\n浏览器已关闭")


if __name__ == "__main__":
    asyncio.run(main())
