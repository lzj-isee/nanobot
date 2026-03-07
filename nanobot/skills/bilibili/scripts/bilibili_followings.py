"""
Bilibili 关注动态提取脚本
提取 https://t.bilibili.com/ 页面中关注UP主的更新信息

使用方法:
    python temp.py                          # 使用默认的 .bilibili.cookie 文件
    python temp.py --cookie-file /path/to/cookie.txt  # 指定 cookie 文件路径
"""

import argparse
import asyncio
import os
import re
import sys
from pathlib import Path
from playwright.async_api import async_playwright
from dataclasses import dataclass
from typing import List, Optional, Dict


# 必需的 Cookie 名称
REQUIRED_COOKIES = ["SESSDATA", "DedeUserID", "DedeUserID__ckMd5", "bili_jct"]


@dataclass
class DynamicItem:
    """动态项数据结构"""
    up_name: str
    time_text: str
    content: str
    video_title: Optional[str] = None
    video_desc: Optional[str] = None


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


async def extract_dynamics(page) -> List[DynamicItem]:
    """从页面提取动态信息"""
    dynamics = []

    # 等待动态列表加载
    await page.wait_for_selector(".bili-dyn-list__item", timeout=30000)

    # 获取所有动态项
    items = await page.query_selector_all(".bili-dyn-list__item")
    print(f"找到 {len(items)} 条动态\n")

    for i, item in enumerate(items, 1):
        try:
            # 提取UP主名字
            up_name_elem = await item.query_selector(".bili-dyn-title__text")
            up_name = await up_name_elem.text_content() if up_name_elem else "未知UP主"
            up_name = up_name.strip()

            # 提取时间
            time_elem = await item.query_selector(".bili-dyn-time")
            time_text = await time_elem.text_content() if time_elem else ""
            time_text = time_text.strip()

            # 提取动态内容（文本类型）
            content = ""
            content_elem = await item.query_selector(".dyn-card-opus__summary")
            if content_elem:
                content = await content_elem.text_content()
                content = content.strip()

            # 提取视频信息（视频类型）
            video_title = None
            video_desc = None
            video_title_elem = await item.query_selector(".bili-dyn-card-video__title")
            if video_title_elem:
                video_title = await video_title_elem.text_content()
                video_title = video_title.strip()

            video_desc_elem = await item.query_selector(".bili-dyn-card-video__desc")
            if video_desc_elem:
                video_desc = await video_desc_elem.text_content()
                video_desc = video_desc.strip()

            # 如果有视频标题但没有内容，使用视频标题作为内容
            if not content and video_title:
                content = video_title

            dynamic = DynamicItem(
                up_name=up_name,
                time_text=time_text,
                content=content,
                video_title=video_title,
                video_desc=video_desc
            )
            dynamics.append(dynamic)

        except Exception as e:
            print(f"提取第 {i} 条动态时出错: {e}")
            continue

    return dynamics


def format_dynamics(dynamics: List[DynamicItem], max_items: int = 20, max_chars: int = 3000) -> str:
    """格式化动态信息为字符串，限制数量和字符数"""
    result_parts = []
    total_chars = 0

    # 限制最多20个item
    dynamics_to_show = dynamics[:max_items]

    for i, dyn in enumerate(dynamics_to_show, 1):
        # 构建单个动态的内容
        parts = []
        parts.append(f"up_name: {dyn.up_name}")
        parts.append(f"time_text: {dyn.time_text}")

        if dyn.video_title:
            parts.append(f"video_title: {dyn.video_title}")
            if dyn.video_desc and dyn.video_desc != dyn.video_title:
                parts.append(f"video_desc: {dyn.video_desc}")
        elif dyn.content:
            parts.append(f"content: {dyn.content}")

        item_text = "\n".join(parts)

        # 检查是否超过字符限制
        if total_chars + len(item_text) > max_chars:
            # 如果超过限制，截断内容
            remaining = max_chars - total_chars
            if remaining > 50:  # 至少保留一些内容
                truncated = item_text[:remaining - 3] + "..."
                result_parts.append(truncated)
            result_parts.append(f"\n... (还有 {len(dynamics) - i + 1} 条动态未显示，达到字符限制)")
            break

        result_parts.append(item_text)
        total_chars += len(item_text) + 2  # +2 是为了两个换行符

    return "\n\n---\n\n".join(result_parts)


async def main():
    # 获取脚本所在目录
    script_dir = Path(__file__).parent.absolute()
    default_cookie_file = script_dir / ".bilibili.cookie"

    # 解析命令行参数
    parser = argparse.ArgumentParser(
        description="提取 Bilibili 关注动态",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python temp.py                                    # 使用默认的 .bilibili.cookie 文件
  python temp.py --cookie-file ~/cookies/bili.txt   # 指定 cookie 文件路径

Cookie 文件格式:
  从浏览器开发者工具复制的 cookie 字符串即可，如:
  SESSDATA=xxx; DedeUserID=xxx; DedeUserID__ckMd5=xxx; bili_jct=xxx
        """
    )
    parser.add_argument(
        "--cookie-file",
        type=str,
        default=str(default_cookie_file),
        help=f"Cookie 文件路径 (默认: {default_cookie_file})"
    )
    args = parser.parse_args()

    # 解析 cookie 文件
    try:
        cookie_dict = parse_cookie_file(args.cookie_file)
        print(f"成功从 {args.cookie_file} 加载 {len(cookie_dict)} 个必需 Cookie")
    except (FileNotFoundError, ValueError) as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)

    async with async_playwright() as p:
        # 启动浏览器（无头模式，添加反爬参数）
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-web-security",
                "--disable-features=IsolateOrigins,site-per-process",
            ]
        )

        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
            extra_http_headers={
                "Referer": "https://t.bilibili.com/",
                "Origin": "https://t.bilibili.com",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Accept-Encoding": "gzip, deflate, br",
                "Cache-Control": "max-age=0",
            }
        )

        # 添加 cookies
        cookies = build_cookie_list(cookie_dict)
        await context.add_cookies(cookies)
        print(f"已加载 {len(cookies)} 个 Cookie")

        page = await context.new_page()

        # 注入脚本隐藏自动化特征
        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
            Object.defineProperty(navigator, 'languages', {
                get: () => ['zh-CN', 'zh', 'en']
            });
            window.chrome = { runtime: {} };
        """)

        print("正在访问 https://t.bilibili.com/ ...")
        response = await page.goto("https://t.bilibili.com/", wait_until="domcontentloaded")
        print(f"页面加载状态: {response.status if response else 'No response'}")

        # 等待动态内容加载
        await page.wait_for_selector(".bili-dyn-list__item", timeout=30000)

        # 获取页面标题
        title = await page.title()
        print(f"页面标题: {title}\n")

        # 检查是否需要登录
        login_selectors = [
            ".login-box",
            ".login-panel",
            ".bili-login",
        ]

        needs_login = False
        for selector in login_selectors:
            try:
                element = await page.wait_for_selector(selector, timeout=30000)
                if element:
                    needs_login = True
                    break
            except:
                continue

        if needs_login:
            print("⚠️  登录已过期，请更新 Cookie 文件中的值")
            await browser.close()
            return

        # 提取动态信息
        dynamics = await extract_dynamics(page)

        # 打印结果
        if dynamics:
            formatted = format_dynamics(dynamics, max_items=20, max_chars=3000)
            print(formatted)
        else:
            print("未找到任何动态内容")

        await browser.close()
        print("\n浏览器已关闭")


if __name__ == "__main__":
    asyncio.run(main())
