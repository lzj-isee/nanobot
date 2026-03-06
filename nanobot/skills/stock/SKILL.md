---
name: stock
description: Search stock market information including stocks, indices, and ETFs. Supports searching by stock name (贵州茅台, 平安银行, Apple), code (600519, 000001, AAPL), or sector keywords (红利低波, 半导体ETF). Uses East Money as data source. Use when user asks about stock prices, market data, or stock-related queries.
always: true
metadata: {"nanobot":{"emoji":"📈","requires":{"bins":["python"],"pip":["playwright"]}}}
---

# Stock Search

Search stock market information including stocks, indices, and ETFs.

## Usage

```bash
python {baseDir}/scripts/search_stock.py --query <keyword>
```

**Note:** Do not include spaces in keywords. Use `沪深300` instead of `沪深 300`, as the search engine may not find results with spaces.

**Example:**

```bash
python {baseDir}/scripts/search_stock.py --query "贵州茅台"
```

## Common Queries

| Type | Examples |
|------|----------|
| Stock name | 贵州茅台, 平安银行, Apple |
| Stock code | 600519, H30269, AAPL |
| Index | 沪深300, 上证指数, 中证银行, 中证红利 |
| ETF | 红利低波, 半导体ETF, 东证红利低波, CS消费50 |
| Overseas | 纳斯达克100, 标普500 |
| Commodity | 黄金/美元, 伦敦金, 比特币 |

## Output

The script returns:
- **Stock name and code**
- **Current price**

If no useful information is found, inform the user directly. Do not fabricate data.

## Data Source

East Money (eastmoney.com), real-time updates.