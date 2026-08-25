#!/usr/bin/env python3
"""
LexiVoice 使用统计查询脚本

用法:
    python3 stats.py              # 显示全部按天统计
    python3 stats.py -d 7         # 最近 7 天
    python3 stats.py -d 30        # 最近 30 天
    python3 stats.py --total      # 只显示总计
"""
import sqlite3
import argparse
import os
from datetime import datetime, timedelta

DB = 'usage.db'


def query(days=None):
    if not os.path.exists(DB):
        print("暂无使用记录（usage.db 不存在）")
        return []
    conn = sqlite3.connect(DB)
    if days:
        since = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        rows = conn.execute(
            "SELECT day, COUNT(*) AS times, SUM(word_count) AS words "
            "FROM usage_log WHERE day >= ? GROUP BY day ORDER BY day",
            (since,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT day, COUNT(*) AS times, SUM(word_count) AS words "
            "FROM usage_log GROUP BY day ORDER BY day"
        ).fetchall()
    conn.close()
    return rows


def main():
    parser = argparse.ArgumentParser(description="LexiVoice 使用统计")
    parser.add_argument('-d', '--days', type=int, help='最近 N 天')
    parser.add_argument('--total', action='store_true', help='只显示总计')
    args = parser.parse_args()

    rows = query(args.days)

    if not rows:
        return

    if args.total:
        total_times = sum(r[1] for r in rows)
        total_words = sum(r[2] for r in rows)
        print(f"总生成次数: {total_times}")
        print(f"总单词量:   {total_words}")
        return

    print(f"{'日期':<12} {'生成次数':>8} {'单词量':>10}")
    print("-" * 32)
    for day, times, words in rows:
        print(f"{day:<12} {times:>8} {words:>10}")
    print("-" * 32)
    print(f"{'合计':<12} {sum(r[1] for r in rows):>8} {sum(r[2] for r in rows):>10}")


if __name__ == '__main__':
    main()
