"""A股候选股票池筛选器（研究用途）。"""
from __future__ import annotations

import argparse
import time
from pathlib import Path

import akshare as ak
import numpy as np
import pandas as pd


def _number(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def fetch_spot() -> pd.DataFrame:
    df = ak.stock_zh_a_spot_em()
    rename = {
        "代码": "code", "名称": "name", "最新价": "price", "涨跌幅": "change_pct",
        "成交额": "amount", "总市值": "market_cap", "换手率": "turnover",
    }
    df = df.rename(columns=rename)
    required = ["code", "name", "price", "change_pct", "amount"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise RuntimeError(f"行情接口缺少字段: {missing}，请检查 AKShare 版本或接口变更")
    for col in ["price", "change_pct", "amount", "market_cap", "turnover"]:
        if col in df:
            df[col] = _number(df[col])
    df["code"] = df["code"].astype(str).str.zfill(6)
    return df


def fetch_history(code: str, days: int = 140) -> pd.DataFrame:
    end = pd.Timestamp.today().strftime("%Y%m%d")
    start = (pd.Timestamp.today() - pd.Timedelta(days=days * 2)).strftime("%Y%m%d")
    df = ak.stock_zh_a_hist(symbol=code, period="daily", start_date=start,
                            end_date=end, adjust="qfq")
    if df.empty:
        return df
    df = df.rename(columns={"日期": "date", "收盘": "close", "成交量": "volume"})
    df["close"] = _number(df["close"])
    df["volume"] = _number(df["volume"])
    return df.dropna(subset=["close", "volume"]).sort_values("date")


def rsi(close: pd.Series, period: int = 14) -> float:
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    if loss.iloc[-1] == 0:
        return 100.0
    return float(100 - 100 / (1 + gain.iloc[-1] / loss.iloc[-1]))


def score(row: dict) -> tuple[float, list[str]]:
    points, reasons = 0.0, []
    if row["price"] > row["ma20"]:
        points += 20; reasons.append("收盘价在MA20上方")
    if row["price"] > row["ma60"]:
        points += 20; reasons.append("收盘价在MA60上方")
    if row["ma20"] > row["ma60"]:
        points += 20; reasons.append("MA20高于MA60")
    if 0 < row["return20"] <= 25:
        points += 15; reasons.append("20日涨幅适中")
    if 40 <= row["rsi14"] <= 70:
        points += 10; reasons.append("RSI处于相对健康区间")
    if row["volume_ratio"] >= 1.1:
        points += 10; reasons.append("成交量温和放大")
    if row["change_pct"] > 9:
        points -= 15; reasons.append("今日涨幅过大，追高风险较高")
    return round(points, 2), reasons


def screen(limit: int, min_price: float, min_amount: float, sleep: float) -> pd.DataFrame:
    spot = fetch_spot()
    mask = (
        ~spot["name"].str.contains("ST|退", na=False) &
        (spot["price"] >= min_price) & (spot["amount"] >= min_amount)
    )
    candidates = spot.loc[mask].sort_values("amount", ascending=False).head(max(limit * 8, 160))
    rows = []
    for _, item in candidates.iterrows():
        try:
            hist = fetch_history(item.code)
            if len(hist) < 70:
                continue
            close, volume = hist["close"], hist["volume"]
            row = {
                "code": item.code, "name": item.name, "price": float(item.price),
                "change_pct": float(item.change_pct), "amount": float(item.amount),
                "ma20": float(close.rolling(20).mean().iloc[-1]),
                "ma60": float(close.rolling(60).mean().iloc[-1]),
                "return20": float((close.iloc[-1] / close.iloc[-21] - 1) * 100),
                "volume_ratio": float(volume.iloc[-5:].mean() / volume.iloc[-25:-5].mean()),
                "rsi14": rsi(close),
            }
            row["score"], row["reasons"] = score(row)
            rows.append(row)
        except Exception as exc:
            print(f"跳过 {item.code} {item.name}: {exc}")
        time.sleep(sleep)
    result = pd.DataFrame(rows)
    if result.empty:
        return result
    result = result.sort_values(["score", "amount"], ascending=[False, False]).head(limit)
    result["reasons"] = result["reasons"].apply("；".join)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="生成A股候选股票池")
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--min-price", type=float, default=3.0)
    parser.add_argument("--min-amount", type=float, default=20_000_000)
    parser.add_argument("--sleep", type=float, default=0.15)
    parser.add_argument("--output", default="output/stock_pool.csv")
    args = parser.parse_args()
    result = screen(args.limit, args.min_price, args.min_amount, args.sleep)
    if result.empty:
        print("没有生成候选结果，请检查网络、交易日或筛选参数")
        return
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(output, index=False, encoding="utf-8-sig")
    print(result[["code", "name", "score", "price", "return20", "rsi14", "reasons"]].to_string(index=False))
    print(f"\n已写入: {output}")


if __name__ == "__main__":
    main()
