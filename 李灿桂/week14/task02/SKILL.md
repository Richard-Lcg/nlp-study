---
name: 股票可视化分析与买卖建议
description: 基于K线数据可视化股票波动，并提供买入卖出时机建议
---

# 股票可视化分析技能

## 功能概述

- 获取股票的日K线和周K线数据
- 计算并可视化日波动率和周波动率
- 基于波动率分析提供买入/卖出最佳时机建议

## 使用方法

```python
import requests
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime, timedelta
from autostock import get_stock_day_kline, get_stock_week_kline, get_stock_info

TOKEN = "zgaLG8unUPr"

def calculate_volatility(df, window=5):
    """计算波动率"""
    if df is None or len(df) < window:
        return None
    df['return'] = df['close'].pct_change()
    df['volatility'] = df['return'].rolling(window=window).std()
    return df

def get_volatility_signal(daily_vol, weekly_vol):
    """
    基于波动率给出买卖信号
    返回: (signal, reason)
    signal: 'buy', 'sell', 'hold'
    """
    if daily_vol is None or weekly_vol is None:
        return 'hold', '数据不足'

    # 计算波动率比率
    vol_ratio = daily_vol / weekly_vol if weekly_vol > 0 else 1

    if daily_vol < weekly_vol * 0.5:
        return 'buy', f'日波动率({daily_vol:.4f})远低于周波动率({weekly_vol:.4f})，市场稳定，可考虑买入'
    elif daily_vol > weekly_vol * 1.5:
        return 'sell', f'日波动率({daily_vol:.4f})高于周波动率({weekly_vol:.4f})，市场波动剧烈，注意风险'
    elif vol_ratio < 0.8:
        return 'buy', f'日波动率/周波动率 = {vol_ratio:.2f} < 0.8，价格稳定，是买入机会'
    elif vol_ratio > 1.2:
        return 'sell', f'日波动率/周波动率 = {vol_ratio:.2f} > 1.2，波动加剧，建议减仓'
    else:
        return 'hold', f'日波动率/周波动率 = {vol_ratio:.2f}，波动正常，观望'

def visualize_stock_volatility(code, name="股票"):
    """可视化股票波动率"""
    # 获取日K线数据（最近60个交易日）
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=120)).strftime("%Y-%m-%d")

    day_data = get_stock_day_kline(code, start_date, end_date, type=1)
    week_data = get_stock_week_kline(code, start_date, end_date, type=1)

    # 转换日K数据
    if day_data and day_data.get('data'):
        df_day = pd.DataFrame(day_data['data'])
        df_day['date'] = pd.to_datetime(df_day['date'])
        df_day['close'] = df_day['close'].astype(float)
        df_day = calculate_volatility(df_day, window=5)
    else:
        df_day = None

    # 转换周K数据
    if week_data and week_data.get('data'):
        df_week = pd.DataFrame(week_data['data'])
        df_week['date'] = pd.to_datetime(df_week['date'])
        df_week['close'] = df_week['close'].astype(float)
        df_week = calculate_volatility(df_week, window=4)
    else:
        df_week = None

    # 创建图表
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(14, 10), sharex=True)
    fig.suptitle(f'{name} ({code}) 波动率分析', fontsize=16, fontweight='bold')

    # 图1: 价格走势
    if df_day is not None:
        ax1.plot(df_day['date'], df_day['close'], label='日K线(前复权)', color='#2196F3', linewidth=1.5)
        ax1.fill_between(df_day['date'], df_day['close'], alpha=0.3, color='#2196F3')
    ax1.set_ylabel('价格 (元)', fontsize=11)
    ax1.set_title('价格走势', fontsize=12)
    ax1.legend(loc='upper left')
    ax1.grid(True, alpha=0.3)

    # 图2: 日波动率
    if df_day is not None:
        ax2.plot(df_day['date'], df_day['volatility'], label='日波动率', color='#FF5722', linewidth=1.5)
        ax2.fill_between(df_day['date'], df_day['volatility'], alpha=0.3, color='#FF5722')
    ax2.set_ylabel('波动率', fontsize=11)
    ax2.set_title('日波动率 (5日滚动标准差)', fontsize=12)
    ax2.legend(loc='upper left')
    ax2.grid(True, alpha=0.3)

    # 图3: 周波动率
    if df_week is not None:
        ax3.plot(df_week['date'], df_week['volatility'], label='周波动率', color='#4CAF50', linewidth=2)
        ax3.fill_between(df_week['date'], df_week['volatility'], alpha=0.3, color='#4CAF50')
    ax3.set_ylabel('波动率', fontsize=11)
    ax3.set_title('周波动率 (4周滚动标准差)', fontsize=12)
    ax3.legend(loc='upper left')
    ax3.grid(True, alpha=0.3)
    ax3.set_xlabel('日期', fontsize=11)

    plt.tight_layout()
    plt.savefig(f'volatility_{code}.png', dpi=150, bbox_inches='tight')
    plt.show()

    # 计算当前信号
    current_day_vol = df_day['volatility'].iloc[-1] if df_day is not None and len(df_day) > 0 else None
    current_week_vol = df_week['volatility'].iloc[-1] if df_week is not None and len(df_week) > 0 else None

    return get_volatility_signal(current_day_vol, current_week_vol)

def get_buy_sell_advice(code):
    """获取完整的买卖建议"""
    # 获取股票信息
    stock_info = get_stock_info(code)
    name = stock_info.get('data', {}).get('name', code) if stock_info else code

    # 获取分析信号
    signal, reason = visualize_stock_volatility(code, name)

    # 构建建议
    advice = {
        'code': code,
        'name': name,
        'signal': signal,
        'reason': reason,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }

    if signal == 'buy':
        advice['action'] = '建议买入'
        advice['tips'] = [
            '波动率处于低位，市场稳定',
            '可考虑分批建仓',
            '止损位：近期低点下方5%'
        ]
    elif signal == 'sell':
        advice['action'] = '建议卖出/减仓'
        advice['tips'] = [
            '波动率放大，注意风险',
            '考虑分批减仓锁定利润',
            '避免追高'
        ]
    else:
        advice['action'] = '观望'
        advice['tips'] = [
            '波动率处于正常区间',
            '等待更明确信号',
            '可小仓位试探'

    return advice
```

## 波动率分析方法

### 波动率计算

- **日波动率**: 5日滚动标准差，反映短期波动程度
- **周波动率**: 4周滚动标准差，反映中期波动程度

### 买卖信号判断

| 日波动率/周波动率 | 信号     | 含义          |
| --------- | ------ | ----------- |
| < 0.5     | **买入** | 极度稳定，可能蓄势待发 |
| 0.5-0.8   | **买入** | 波动较低，买入机会   |
| 0.8-1.2   | **观望** | 波动正常，等待时机   |
| 1.2-1.5   | **卖出** | 波动加剧，注意风险   |
| > 1.5     | **卖出** | 极度波动，风险较大   |

### 辅助判断指标

- **缩量整理**: 波动率下降 + 成交量萎缩 = 可能变盘信号
- **放量突破**: 波动率上升 + 成交量放大 = 趋势确认信号
- **价量背离**: 价格创新高但波动率下降 = 顶背离风险

## 示例输出

```python
# 获取股票600519(茅台)的买卖建议
advice = get_buy_sell_advice('600519')
print(f"""
股票: {advice['name']} ({advice['code']})
信号: {advice['signal']}
建议: {advice['action']}
原因: {advice['reason']}
时间: {advice['timestamp']}
操作建议:
""")
for tip in advice['tips']:
    print(f"  - {tip}")
```

# 