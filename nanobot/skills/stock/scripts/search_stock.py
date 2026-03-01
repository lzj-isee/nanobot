#!/usr/bin/env python3
"""
Stock Search Tool - Search Chinese stock market information via East Money

Usage:
    python search_stock.py --query <search_keyword>

Examples:
    python search_stock.py --query 贵州茅台
    python search_stock.py --query 600519
    python search_stock.py --query 红利低波
    python search_stock.py --query 半导体ETF
"""

import asyncio
import argparse
from playwright.async_api import async_playwright


async def search_stock(query: str):
    """
    Search stock information

    Args:
        query: Search keyword, e.g., "红利低波", "贵州茅台", "600519"
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        url = f"https://so.eastmoney.com/web/s?keyword={query}"
        print(f"Accessing: {url}\n")

        has_result = False

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(5000)

            # 1. Try to get stock quote information
            print("【股票/指数行情】")
            stock_elements = await page.query_selector_all(".exstock")

            if stock_elements:
                has_result = True
                for stock in stock_elements:
                    try:
                        name_el = await stock.query_selector(".exstock_t_l")
                        name = await name_el.inner_text() if name_el else ""

                        time_el = await stock.query_selector(".exstock_time")
                        time_text = await time_el.inner_text() if time_el else ""

                        price_el = await stock.query_selector(".price span span, .price")
                        price = await price_el.inner_text() if price_el else ""

                        zde_el = await stock.query_selector(".zde span")
                        zde = await zde_el.inner_text() if zde_el else ""

                        zdf_el = await stock.query_selector(".zdf span")
                        zdf = await zdf_el.inner_text() if zdf_el else ""

                        state_el = await stock.query_selector(".state")
                        state = await state_el.inner_text() if state_el else ""

                        print(f"名称: {name}")
                        print(f"时间: {time_text}")
                        print(f"价格: {price}")
                        print(f"涨跌额: {zde}")
                        print(f"涨跌幅: {zdf}")
                        print(f"状态: {state}")

                        info_rows = await stock.query_selector_all("tbody tr")
                        for row in info_rows:
                            row_text = await row.inner_text()
                            print(f"  {row_text}")
                    except Exception as e:
                        print(f"Error parsing stock info: {e}")
            else:
                print("No direct quotes found")

            # 2. Get related stock table (only when step 1 has no results)
            if not has_result:
                print("\n【相关个股行情】")
                table = await page.query_selector(".index_stocks table, .c_table")
                if table:
                    rows = await table.query_selector_all("tbody tr")
                    if rows:
                        has_result = True
                        print(f"{'代码':<12} {'名称':<12} {'市场':<6} {'最新价':<10} {'涨跌额':<10} {'涨跌幅':<10}")
                        print("-" * 60)
                        for row in rows:
                            cells = await row.query_selector_all("td")
                            if len(cells) >= 6:
                                code_el = await cells[0].query_selector("a")
                                code = await code_el.inner_text() if code_el else ""
                                name_el = await cells[1].query_selector("span[title]")
                                name = await name_el.get_attribute("title") if name_el else ""
                                if not name:
                                    name = await cells[1].inner_text()
                                market = await cells[2].inner_text()
                                price = await cells[3].inner_text()
                                change = await cells[4].inner_text()
                                percent = await cells[5].inner_text()

                                print(f"{code:<12} {name:<12} {market:<6} {price:<10} {change:<10} {percent:<10}")
                    else:
                        print("  No related stock data")
                else:
                    print("  No related stock table found")

            # 3. If no valid info extracted, output page text content
            if not has_result:
                print("\n【页面文本内容】")
                print("-" * 50)
                text = await page.inner_text("body")
                print(text[:3000])

        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            await browser.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Search Chinese stock market information")
    parser.add_argument("--query", "-q", type=str, required=True, help="Search keyword (stock name or code)")
    args = parser.parse_args()

    asyncio.run(search_stock(args.query))