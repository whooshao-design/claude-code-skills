#!/usr/bin/env python3
"""
技术方案评审收敛性分析工具

分析多轮评审报告，判断是否满足终止条件，
并给出收敛趋势预测。
"""

import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field
from collections import defaultdict


@dataclass
class RoundStats:
    """单轮统计"""
    round: str
    blocker: int = 0
    major: int = 0
    completeness: int = 0
    risk: int = 0
    question: int = 0
    total: int = 0


@dataclass
class IssueTracker:
    """问题追踪"""
    id: str
    level: str
    title: str
    first_round: str
    status: str
    changes: List[Dict] = field(default_factory=list)


class ConvergenceAnalyzer:
    """收敛性分析器"""

    def __init__(self, review_dir: str):
        self.review_dir = Path(review_dir)
        self.rounds: List[RoundStats] = []
        self.all_issues: Dict[str, IssueTracker] = {}

    def analyze(self) -> Dict:
        """执行收敛性分析"""
        self._load_all_reports()
        stats = self._calculate_stats()
        trend = self._analyze_trend()
        recommendations = self._generate_recommendations()

        return {
            "rounds": stats,
            "trend": trend,
            "recommendations": recommendations,
            "termination_check": self._check_termination()
        }

    def _load_all_reports(self):
        """加载所有评审报告"""
        md_files = sorted(self.review_dir.glob("Review-v*.md"))

        for md_file in md_files:
            content = md_file.read_text(encoding="utf-8")
            round_num = md_file.stem.replace("Review-v", "")

            # 提取问题统计
            stats = self._extract_round_stats(content, round_num)
            self.rounds.append(stats)

            # 追踪问题变化
            self._track_issues(content, round_num)

    def _extract_round_stats(self, content: str, round_num: str) -> RoundStats:
        """提取单轮统计"""
        stats = RoundStats(round=round_num)

        # 从问题总览表格提取
        table_pattern = r"\| (B-\d+) \|.*?\| (Open|Resolved|Accepted Risk) \|"
        for match in re.finditer(table_pattern, content):
            issue_id = match.group(1)
            status = match.group(2)

            level = issue_id.split("-")[0]
            if level == "B":
                stats.blocker += 1
            elif level == "M":
                stats.major += 1
            elif level == "C":
                stats.completeness += 1
            elif level == "R":
                stats.risk += 1
            elif level == "Q":
                stats.question += 1

        stats.total = (stats.blocker + stats.major + stats.completeness +
                       stats.risk + stats.question)

        return stats

    def _track_issues(self, content: str, round_num: str):
        """追踪问题变化"""
        # 从状态表格提取
        table_pattern = r"\| (B-\d+|M-\d+|C-\d+|R-\d+|Q-\d+) \| ([^|]+) \| v\d+ \| (\w+) \|"
        for match in re.finditer(table_pattern, content):
            issue_id = match.group(1)
            title = match.group(2).strip()
            status = match.group(3)

            level = issue_id.split("-")[0]

            if issue_id not in self.all_issues:
                self.all_issues[issue_id] = IssueTracker(
                    id=issue_id,
                    level=level,
                    title=title,
                    first_round=round_num,
                    status=status
                )

            # 记录状态变化
            self.all_issues[issue_id].changes.append({
                "round": round_num,
                "status": status
            })
            self.all_issues[issue_id].status = status

    def _calculate_stats(self) -> List[Dict]:
        """计算统计数据"""
        return [
            {
                "round": r.round,
                "blocker": r.blocker,
                "major": r.major,
                "completeness": r.completeness,
                "risk": r.risk,
                "question": r.question,
                "total": r.total
            }
            for r in self.rounds
        ]

    def _analyze_trend(self) -> Dict:
        """分析收敛趋势"""
        if len(self.rounds) < 2:
            return {
                "direction": "unknown",
                "description": "数据不足，无法判断趋势",
                "prediction": None
            }

        # 计算最近两轮的变化
        latest = self.rounds[-1]
        previous = self.rounds[-2]

        blocker_change = latest.blocker - previous.blocker
        major_change = latest.major - previous.major
        total_change = latest.total - previous.total

        # 判断趋势
        if blocker_change < 0 and major_change < 0:
            direction = "converging"
            description = "收敛中"
        elif blocker_change > 0 or major_change > 0:
            direction = "diverging"
            description = "发散中"
        else:
            direction = "stable"
            description = "趋于稳定"

        # 预测
        if direction == "converging":
            remaining = latest.total - latest.blocker - latest.major
            if remaining > 0 and total_change < 0:
                predicted_rounds = remaining // max(1, -total_change) + 1
                prediction = f"预计 {predicted_rounds} 轮后可收敛"
            else:
                prediction = "即将收敛"
        else:
            prediction = None

        return {
            "direction": direction,
            "description": description,
            "prediction": prediction,
            "changes": {
                "blocker": blocker_change,
                "major": major_change,
                "total": total_change
            }
        }

    def _check_termination(self) -> Dict:
        """检查终止条件"""
        latest = self.rounds[-1] if self.rounds else None

        if not latest:
            return {"can_terminate": False, "reason": "无评审数据"}

        conditions = []

        # 条件1：连续2轮无新增 Blocker/Major
        if len(self.rounds) >= 2:
            latest_change = self._get_change(-1)
            prev_change = self._get_change(-2)
            if latest_change["blocker"] <= 0 and latest_change["major"] <= 0:
                if prev_change["blocker"] <= 0 and prev_change["major"] <= 0:
                    conditions.append({
                        "condition": "连续2轮无新增 Blocker/Major",
                        "met": True
                    })

        # 条件2：所有问题均为 Resolved 或 Accepted Risk
        unresolved = latest.blocker + latest.major
        if unresolved == 0:
            conditions.append({
                "condition": "所有 Blocker/Major 已解决",
                "met": True
            })
        else:
            conditions.append({
                "condition": f"仍有 {unresolved} 个 Blocker/Major 未解决",
                "met": False
            })

        # 条件3：达到最大轮次
        if len(self.rounds) >= 16:
            conditions.append({
                "condition": "达到最大轮次 (16)",
                "met": True
            })

        # 综合判断
        can_terminate = any(c["met"] for c in conditions if c["condition"] != "仍有 N 个 Blocker/Major 未解决")

        return {
            "can_terminate": can_terminate,
            "conditions": conditions,
            "remaining_blocker": latest.blocker if latest else 0,
            "remaining_major": latest.major if latest else 0
        }

    def _get_change(self, index: int) -> Dict:
        """获取某轮的变化量（相对于前一伦）"""
        if index == -1:
            return {
                "blocker": self.rounds[index].blocker,
                "major": self.rounds[index].major,
                "total": self.rounds[index].total
            }

        current = self.rounds[index]
        previous = self.rounds[index - 1] if index > 0 else current

        return {
            "blocker": current.blocker - previous.blocker,
            "major": current.major - previous.major,
            "total": current.total - previous.total
        }

    def _generate_recommendations(self) -> List[str]:
        """生成建议"""
        recommendations = []

        if not self.rounds:
            return ["等待评审数据"]

        latest = self.rounds[-1]
        trend = self._analyze_trend()

        # 基于 Blocker 数量
        if latest.blocker > 0:
            recommendations.append(f"仍有 {latest.blocker} 个 Blocker，方案修订前不应上线")
        else:
            recommendations.append("所有 Blocker 已解决")

        # 基于收敛趋势
        if trend["direction"] == "converging":
            recommendations.append(f"趋势良好 - {trend['description']}")
            if trend["prediction"]:
                recommendations.append(trend["prediction"])
        elif trend["direction"] == "diverging":
            recommendations.append("警告：问题数量增加，需检查方案是否有重大遗漏")
        else:
            recommendations.append("问题数量趋于稳定")

        return recommendations

    def print_report(self):
        """打印分析报告"""
        result = self.analyze()

        print("=" * 60)
        print("技术方案评审收敛性分析报告")
        print("=" * 60)
        print()

        # 评审历史
        print("【评审历史】")
        print(f"{'轮次':<8} {'B':>4} {'M':>4} {'C':>4} {'R':>4} {'Q':>4} {'合计':>6}")
        print("-" * 40)
        for stats in result["rounds"]:
            print(f"v{stats['round']:<6} {stats['blocker']:>4} {stats['major']:>4} "
                  f"{stats['completeness']:>4} {stats['risk']:>4} {stats['question']:>4} "
                  f"{stats['total']:>6}")
        print()

        # 收敛趋势
        trend = result["trend"]
        print("【收敛趋势】")
        print(f"  方向: {trend['description']}")
        if trend.get("changes"):
            changes = trend["changes"]
            print(f"  变化: B:{changes['blocker']:+d}, M:{changes['major']:+d}, 合计:{changes['total']:+d}")
        if trend.get("prediction"):
            print(f"  预测: {trend['prediction']}")
        print()

        # 终止条件
        term = result["termination_check"]
        print("【终止条件检查】")
        for c in term["conditions"]:
            status = "✓" if c["met"] else "✗"
            print(f"  [{status}] {c['condition']}")
        print()

        # 建议
        print("【建议】")
        for rec in result["recommendations"]:
            print(f"  • {rec}")
        print()

        # 最终结论
        if term["can_terminate"]:
            print("【结论】✅ 可终止评审")
        else:
            print("【结论】⏳ 继续评审")
        print("=" * 60)


def main():
    if len(sys.argv) < 2:
        print("用法: python convergence_analyzer.py <review_directory>")
        sys.exit(1)

    analyzer = ConvergenceAnalyzer(sys.argv[1])
    analyzer.print_report()


if __name__ == "__main__":
    main()
