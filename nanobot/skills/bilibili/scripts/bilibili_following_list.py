"""
Bilibili 关注列表获取脚本
获取当前登录用户关注的所有UP主列表（UID和昵称）

使用方法:
    python bilibili_following_list.py                          # 使用默认的 .bilibili.cookie 文件
    python bilibili_following_list.py --cookie-file /path/to/cookie.txt  # 指定 cookie 文件路径
    python bilibili_following_list.py --output followings.json  # 指定输出文件
    python bilibili_following_list.py --name "老番茄"            # 按昵称模糊搜索
    python bilibili_following_list.py --name "老番茄" --top 5    # 只显示最相似的5个

API 接口:
    https://api.bilibili.com/x/relation/followings?vmid={uid}&pn={page}&ps=100&order=desc
"""

import argparse
import asyncio
import difflib
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
class FollowingUser:
    """关注的UP主数据结构"""
    uid: int
    nickname: str
    face: str  # 头像URL
    sign: str  # 个性签名
    official_verify: str  # 认证信息
    similarity: float = 0.0  # 昵称相似度（用于搜索排序）


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


def calculate_similarity(query: str, target: str) -> float:
    """
    计算查询字符串与目标字符串的相似度
    使用多种算法综合评分：
    1. 包含匹配（子串匹配）- 最高优先级
    2. 编辑距离比率（difflib.SequenceMatcher）
    3. 前缀匹配奖励
    """
    query = query.lower().strip()
    target = target.lower().strip()

    if not query or not target:
        return 0.0

    # 完全匹配
    if query == target:
        return 1.0

    # 包含匹配（查询词是目标的子串）
    if query in target:
        # 根据位置给予不同权重，开头的匹配更相关
        position_bonus = 1.0 - (target.find(query) / len(target)) * 0.3
        return 0.9 * position_bonus

    # 反向包含（目标是查询词的子串）
    if target in query:
        return 0.8

    # 使用 difflib 计算序列相似度
    seq_ratio = difflib.SequenceMatcher(None, query, target).ratio()

    # 前缀匹配奖励
    prefix_len = 0
    for i, (c1, c2) in enumerate(zip(query, target)):
        if c1 == c2:
            prefix_len += 1
        else:
            break
    prefix_bonus = min(prefix_len / max(len(query), 1), 1.0) * 0.1

    # 综合评分
    final_score = seq_ratio * 0.7 + prefix_bonus

    return final_score


def filter_and_sort_by_name(followings: List[FollowingUser], query: str, top_n: Optional[int] = None) -> List[FollowingUser]:
    """
    根据昵称模糊搜索并排序

    Args:
        followings: 关注列表
        query: 搜索关键词
        top_n: 只返回前N个最相似的结果，None表示返回所有

    Returns:
        按相似度排序后的列表
    """
    # 计算每个用户的相似度
    for user in followings:
        user.similarity = calculate_similarity(query, user.nickname)

    # 按相似度降序排序
    sorted_followings = sorted(followings, key=lambda x: x.similarity, reverse=True)

    # 如果指定了 top_n，只返回前N个
    if top_n is not None and top_n > 0:
        return sorted_followings[:top_n]

    return sorted_followings


async def fetch_followings(page, cookie_dict: Dict[str, str]) -> List[FollowingUser]:
    """
    获取所有关注的UP主列表（支持分页）
    """
    followings = []
    my_uid = cookie_dict.get("DedeUserID", "")

    if not my_uid:
        print("错误: 无法从 cookie 中获取用户 ID (DedeUserID)")
        return []

    print(f"当前用户 UID: {my_uid}")
    print("开始获取关注列表...")

    # 先访问主页建立会话
    print("正在建立会话...")
    await page.goto("https://bilibili.com", wait_until="networkidle")
    await random_delay(1000, 2000)

    page_num = 1
    page_size = 50  # API实际每页返回50个，虽然可以请求100但最多只返回50

    while True:
        # 构建 API 请求参数
        params = {
            "vmid": my_uid,
            "pn": page_num,
            "ps": page_size,
            "order": "desc",
        }

        api_url = f"https://api.bilibili.com/x/relation/followings?{urlencode(params)}"
        print(f"正在获取第 {page_num} 页...")

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
        items = data.get("list", [])
        total = data.get("total", 0)

        if not items:
            print(f"第 {page_num} 页没有数据，获取完成")
            break

        print(f"第 {page_num} 页获取到 {len(items)} 个UP主 (总共 {total} 个)")

        for item in items:
            try:
                user = FollowingUser(
                    uid=item.get("mid", 0),
                    nickname=item.get("uname", ""),
                    face=item.get("face", ""),
                    sign=item.get("sign", ""),
                    official_verify=item.get("official_verify", {}).get("desc", "")
                )
                followings.append(user)
            except Exception as e:
                print(f"解析用户数据时出错: {e}")
                continue

        # 根据 total 计算总页数，确保获取全部
        total_pages = (total + page_size - 1) // page_size  # 向上取整
        print(f"进度: {len(followings)}/{total} (第 {page_num}/{total_pages} 页)")

        # 检查是否还有更多数据
        if page_num >= total_pages or len(followings) >= total:
            print(f"已获取全部 {len(followings)} 个关注")
            break

        page_num += 1
        await random_delay(800, 1500)  # 分页之间添加延迟

    return followings


def format_followings(followings: List[FollowingUser], output_format: str = "text", show_similarity: bool = False) -> str:
    """格式化关注列表为字符串"""
    if output_format == "json":
        data = [
            {
                "uid": user.uid,
                "nickname": user.nickname,
                "face": user.face,
                "sign": user.sign,
                "official_verify": user.official_verify,
                "similarity": round(user.similarity, 4) if show_similarity else None
            }
            for user in followings
        ]
        return json.dumps(data, ensure_ascii=False, indent=2)
    else:
        # 文本格式
        lines = []
        lines.append(f"共关注 {len(followings)} 个UP主\n")
        lines.append("-" * 50)

        for i, user in enumerate(followings, 1):
            # 如果有相似度信息，显示相似度
            similarity_str = ""
            if show_similarity and user.similarity > 0:
                # 用星星表示相似度等级
                stars = "★" * int(user.similarity * 5) + "☆" * (5 - int(user.similarity * 5))
                similarity_str = f" [{stars} {user.similarity:.1%}]"

            lines.append(f"{i}. {user.nickname}{similarity_str}")
            lines.append(f"   UID: {user.uid}")
            if user.sign:
                lines.append(f"   签名: {user.sign}")
            if user.official_verify:
                lines.append(f"   认证: {user.official_verify}")
            lines.append("")

        return "\n".join(lines)


async def main():
    # 获取脚本所在目录
    script_dir = Path(__file__).parent.absolute()
    default_cookie_file = script_dir / ".bilibili.cookie"

    # 解析命令行参数
    parser = argparse.ArgumentParser(
        description="获取 Bilibili 关注列表",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python bilibili_following_list.py                                    # 使用默认的 .bilibili.cookie 文件
  python bilibili_following_list.py --cookie-file ~/cookies/bili.txt   # 指定 cookie 文件路径
  python bilibili_following_list.py --output followings.json           # 输出为 JSON 格式
  python bilibili_following_list.py --format json                      # 指定输出格式为 JSON
  python bilibili_following_list.py --name "老番茄"                     # 按昵称模糊搜索，默认显示最相似的10个
  python bilibili_following_list.py --name "老番茄" --top 5             # 只显示最相似的5个
  python bilibili_following_list.py --name "老番茄" --top 0             # 显示所有搜索结果（不限制数量）
  python bilibili_following_list.py --name "老番茄" --format json       # 搜索结果输出为JSON

提示:
  当输出内容超过3000字符时，终端会自动截断显示，并提示使用 --output 参数保存完整结果到文件
        """
    )
    parser.add_argument(
        "--cookie-file",
        type=str,
        default=str(default_cookie_file),
        help=f"Cookie 文件路径 (默认: {default_cookie_file})"
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
    parser.add_argument(
        "--name",
        "-n",
        type=str,
        help="按昵称模糊搜索UP主（支持部分匹配）"
    )
    parser.add_argument(
        "--top",
        "-t",
        type=int,
        default=10,
        help="只显示最相似的N个结果，默认10个（配合 --name 使用，设为0表示显示全部）"
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
            followings = await fetch_followings(page, cookie_dict)

            if followings:
                # 如果指定了搜索关键词，进行模糊搜索并排序
                show_similarity = False
                if args.name:
                    print(f"\n正在搜索昵称包含 '{args.name}' 的UP主...")
                    followings = filter_and_sort_by_name(followings, args.name, top_n=args.top)
                    show_similarity = True

                    # 显示搜索结果统计
                    high_match = sum(1 for u in followings if u.similarity >= 0.5)
                    print(f"找到 {len(followings)} 个结果（高相似度: {high_match} 个）\n")

                formatted = format_followings(followings, output_format=args.format, show_similarity=show_similarity)

                if args.output:
                    # 写入文件
                    output_path = Path(args.output)
                    output_path.write_text(formatted, encoding='utf-8')
                    print(f"\n结果已保存到: {args.output}")
                    print(f"共 {len(followings)} 个关注")
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
                        print(f"   例如: python {Path(__file__).name} --name \"{args.name or ''}\" --output result.json")
                    else:
                        print("\n" + "="*50)
                        print(formatted)
                        print("="*50)
            else:
                print("未获取到任何关注数据")

        except Exception as e:
            print(f"执行出错: {e}")
            import traceback
            traceback.print_exc()

        finally:
            await browser.close()
            print("\n浏览器已关闭")


if __name__ == "__main__":
    asyncio.run(main())
