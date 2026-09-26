# A股股票筛选器

基于 AKShare 的 A 股量化筛选示例：结合趋势、动量、成交量和可选的基本面指标生成候选股票池。

> 免责声明：本项目仅用于学习和研究，不构成投资建议，也不能保证股票上涨。使用前请自行核验数据、交易规则和风险。

## 快速开始

```bash
python -m venv .venv
# macOS/Linux
source .venv/bin/activate
# Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
python screener.py --limit 30 --output output/stock_pool.csv
```

程序会优先读取行情数据，计算 MA20/MA60、RSI、近期涨幅、量比等指标并打分。网络、数据源或接口字段变化可能导致运行失败；请以实际返回数据为准。

## 筛选逻辑

- 排除 ST、退市整理、停牌及价格/成交额过低的股票
- 收盘价位于 MA20 和 MA60 上方
- MA20 高于 MA60，优先选择中期趋势向上
- 近期涨幅不过度、成交量温和放大
- 以评分排序，而非输出“必涨”结论

## 参数

```bash
python screener.py --limit 50 --min-price 3 --min-amount 20000000 --output output/stock_pool.csv
```

数据来自公开接口，可能有延迟、缺失或复权口径差异。建议先回测，再用模拟盘验证，并加入止损、仓位和流动性约束。
