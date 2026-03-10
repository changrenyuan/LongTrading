import os
import json
import pandas as pd
import akshare as ak
from datetime import datetime, time, timedelta, timezone

# 强制使用北京时间 (CST, UTC+8)
TZ_BJ = timezone(timedelta(hours=8))

# 缓存变量
_trading_days_cache = {"year": 0, "days": set()}


def get_trading_days(year: int):
    """获取指定年份的交易日，带缓存逻辑"""
    global _trading_days_cache
    if _trading_days_cache["year"] == year:
        return _trading_days_cache["days"]

    try:
        df = ak.tool_trade_date_hist_sina()
        df['trade_date'] = pd.to_datetime(df['trade_date']).dt.date
        trading_days = set(d for d in df['trade_date'] if d.year == year)

        if not trading_days:
            raise ValueError("No data from akshare")

        _trading_days_cache = {"year": year, "days": trading_days}
        return trading_days
    except Exception as e:
        print(f"Akshare 获取失败，启用周六日降级: {e}")
        trading_days = set()
        curr = datetime(year, 1, 1).date()
        while curr.year == year:
            if curr.weekday() < 5: trading_days.add(curr)
            curr += timedelta(days=1)
        return trading_days


def update_market_status_json(output_path = os.path.join(os.path.dirname(__file__), "../data/market_status.json")):
    """
    计算当前市场状态并保存为 JSON 文件
    """
    # 1. 统一使用北京时间
    now = datetime.now(TZ_BJ).replace(tzinfo=None)
    today_date = now.date()
    current_time = now.time()

    # 2. 判断交易日
    trading_days = get_trading_days(now.year)
    is_trading_day = today_date in trading_days

    # 3. A股时间常量
    T_930, T_1130, T_1300, T_1500 = time(9, 30), time(11, 30), time(13, 0), time(15, 0)

    # 4. 状态判定
    status_code = 0
    market_status = "休市日"
    next_event, next_event_time = None, None

    if is_trading_day:
        if current_time < T_930:
            market_status, status_code = "开盘前", 1
            next_event, next_event_time = "开盘", datetime.combine(today_date, T_930)
        elif T_930 <= current_time < T_1130:
            market_status, status_code = "早盘交易中", 2
            next_event, next_event_time = "午间休市", datetime.combine(today_date, T_1130)
        elif T_1130 <= current_time < T_1300:
            market_status, status_code = "午间休市", 3
            next_event, next_event_time = "下午开盘", datetime.combine(today_date, T_1300)
        elif T_1300 <= current_time < T_1500:
            market_status, status_code = "午盘交易中", 4
            next_event, next_event_time = "收盘", datetime.combine(today_date, T_1500)
        else:
            market_status, status_code = "已收盘", 5

    # 计算倒计时
    countdown = None
    if next_event_time:
        diff = next_event_time - now
        if diff.total_seconds() > 0:
            m, s = divmod(int(diff.total_seconds()), 60)
            h, m = divmod(m, 60)
            countdown = f"{h:02d}:{m:02d}:{s:02d}"

    # 5. 构建结果字典
    result = {
        "is_trading_day": is_trading_day,
        "market_status": market_status,
        "status_code": status_code,
        "current_time": now.strftime("%Y-%m-%d %H:%M:%S"),
        "date": now.strftime("%Y-%m-%d"),
        "weekday": ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][now.weekday()],
        "next_event": next_event,
        "countdown": countdown,
        "trading_periods": {  # 👈 必须添加这个字段
            "morning": {"open": "09:30", "close": "11:30"},
            "afternoon": {"open": "13:00", "close": "15:00"}
        },
        "last_update": datetime.now().strftime("%H:%M:%S")  # 记录物理生成时间
    }

    # 写入文件
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=4, ensure_ascii=False)

    return result


if __name__ == "__main__":
    # 手动测试脚本
    print(update_market_status_json())