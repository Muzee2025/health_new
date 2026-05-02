#!/usr/bin/env python3
"""
数据分析报告生成脚本 - 执行全面的数据分析并生成报告

使用方法（在 backend 目录下执行）：
    cd backend
    python scripts/run_analytics_report.py

功能：
1. 对所有用户进行趋势分析
2. 检测异常数据
3. 提取行为模式
4. 生成平台整体统计
5. 输出详细分析报告
"""
from __future__ import annotations

import os
import sys
from datetime import date, datetime
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))
os.chdir(BACKEND_ROOT)

from dotenv import load_dotenv

load_dotenv(BACKEND_ROOT / ".env")

if not os.getenv("DATABASE_URL"):
    print("错误: 请在 backend/.env 中设置 DATABASE_URL")
    sys.exit(1)

from app.database import SessionLocal
from app.services import analytics_service


def print_separator(title: str = "") -> None:
    """打印分隔线"""
    if title:
        print(f"\n{'=' * 20} {title} {'=' * 20}")
    else:
        print("=" * 60)


def run_analytics_report(days: int = 30) -> None:
    """执行数据分析并生成报告"""
    db = SessionLocal()

    try:
        print_separator("健康数据分析报告")
        print(f"分析周期: 近 {days} 天")
        print(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        print_separator("平台整体统计")
        stats = analytics_service.get_platform_statistics(db)

        print(f"\n用户统计:")
        print(f"  - 总用户数: {stats['users']['total']}")

        print(f"\n数据记录统计:")
        print(f"  - 传感器记录: {stats['data_records']['sensor_records']} 条")
        print(f"  - 小程序健康指标: {stats['data_records']['mini_metrics']} 条")
        print(f"  - 健康同步记录: {stats['data_records']['health_sync']} 条")

        print(f"\n社区活动统计:")
        print(f"  - 帖子总数: {stats['community']['posts']} 篇")
        print(f"  - 评论总数: {stats['community']['comments']} 条")
        print(f"  - 对话记录: {stats['community']['conversations']} 条")

        print(f"\n平台平均指标:")
        print(f"  - 平均步数: {stats['averages']['steps']:.0f} 步/天")
        print(f"  - 平均屏幕时间: {stats['averages']['screen_time_hours']:.1f} 小时/天")
        print(f"  - 平均情绪评分: {stats['averages']['mood_score']:.1f}/10")

        print_separator("用户健康分布")
        distribution = analytics_service.get_user_distribution(db)

        print(f"\n活动水平分布:")
        total = sum(distribution['activity_levels'].values())
        for level, count in distribution['activity_levels'].items():
            pct = count / total * 100 if total > 0 else 0
            level_name = {"low": "低", "medium": "中", "high": "高"}.get(level, level)
            print(f"  - {level_name}: {count} 人 ({pct:.1f}%)")

        print(f"\n健康风险分布:")
        for level, count in distribution['risk_levels'].items():
            pct = count / total * 100 if total > 0 else 0
            level_name = {"low": "低风险", "medium": "中风险", "high": "高风险"}.get(level, level)
            print(f"  - {level_name}: {count} 人 ({pct:.1f}%)")

        print_separator("用户详细分析")

        from app import models

        users = db.query(models.User).all()

        for user in users:
            print(f"\n--- 用户: {user.username} ---")

            report = analytics_service.generate_analytics_report(db, user.id, days)

            print(f"\n健康画像:")
            print(f"  - 用户类型: {report.health_profile.user_type}")
            print(f"  - 活动水平: {report.health_profile.activity_level}")
            print(f"  - 健康评分: {report.health_profile.overall_score}/100")

            if report.health_profile.strengths:
                print(f"  - 优势: {', '.join(report.health_profile.strengths)}")
            if report.health_profile.risk_factors:
                print(f"  - 风险因素: {', '.join(report.health_profile.risk_factors)}")
            if report.health_profile.recommendations:
                print(f"  - 建议: {', '.join(report.health_profile.recommendations)}")

            if report.trends:
                print(f"\n趋势分析:")
                for trend in report.trends:
                    direction_emoji = {
                        "increasing": "📈",
                        "decreasing": "📉",
                        "stable": "➡️",
                        "volatile": "📊",
                    }.get(trend.direction.value, "📊")
                    print(f"  {direction_emoji} {trend.metric_name}: {trend.description}")
                    print(f"      变化: {trend.change_percent:+.1f}%, 置信度: {trend.confidence:.0%}")

            if report.anomalies:
                print(f"\n异常检测 (共 {len(report.anomalies)} 个):")
                critical = [a for a in report.anomalies if a.severity.value in ["high", "critical"]]
                for anomaly in critical[:5]:
                    severity_emoji = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(
                        anomaly.severity.value, "⚪"
                    )
                    print(f"  {severity_emoji} {anomaly.date}: {anomaly.description}")

            if report.patterns:
                print(f"\n行为模式:")
                for pattern in report.patterns:
                    print(f"  🔍 {pattern.pattern_name}: {pattern.description}")
                    print(f"      置信度: {pattern.confidence:.0%}")

            print(f"\n洞察总结:")
            for insight in report.insights[:5]:
                print(f"  • {insight}")

        print_separator("分析报告完成")
        print(f"\n报告生成完毕，共分析 {len(users)} 个用户")

    finally:
        db.close()


def main() -> None:
    print("\n" + "=" * 60)
    print("健康数据分析系统")
    print("=" * 60 + "\n")

    run_analytics_report(days=30)

    print("\n提示: 可通过 API 端点获取更多分析数据:")
    print("  - GET /analytics/report - 综合分析报告")
    print("  - GET /analytics/trends - 趋势分析")
    print("  - GET /analytics/anomalies - 异常检测")
    print("  - GET /analytics/patterns - 模式提取")
    print("  - GET /analytics/profile - 健康画像")
    print("  - GET /analytics/platform/stats - 平台统计")
    print("  - GET /analytics/platform/distribution - 用户分布")


if __name__ == "__main__":
    main()
