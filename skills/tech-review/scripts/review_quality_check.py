#!/usr/bin/env python3
"""
技术方案评审报告质量检查工具

用于验证 Review-vX.md 文档是否符合规范：
1. 文件名规范
2. 必需章节完整性
3. 问题编号唯一性
4. 状态转移合法性
"""

import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field


@dataclass
class Issue:
    """问题记录"""
    id: str
    level: str  # B, M, C, R, Q
    title: str
    first_round: str
    current_round: str
    status: str  # Open, Resolved, Accepted Risk, Pending Confirmation
    line_number: int


@dataclass
class ReviewReport:
    """评审报告结构"""
    version: str
    depth: str
    round: str
    issues: List[Issue] = field(default_factory=list)
    has_checkpoint: bool = False
    chapters: Dict[str, int] = field(default_factory=dict)


class ReviewQualityChecker:
    """评审报告质量检查器"""

    # 必需章节
    REQUIRED_CHAPTERS = [
        "评审元信息",
        "本轮评审结论",
        "问题总览",
        "问题详细记录",
        "评审收敛性自检"
    ]

    # 问题级别正则
    LEVEL_PATTERN = {
        "Blocker": r"^##{1,3}\s*\[(B-\d+)\]",
        "Major": r"^##{1,3}\s*\[(M-\d+)\]",
        "Completeness": r"^##{1,3}\s*\[(C-\d+)\]",
        "Risk": r"^##{1,3}\s*\[(R-\d+)\]",
        "Question": r"^##{1,3}\s*\[(Q-\d+)\]"
    }

    # 合法状态
    VALID_STATES = {"Open", "Resolved", "Accepted Risk", "Pending Confirmation"}

    def __init__(self, file_path: str):
        self.file_path = Path(file_path)
        self.content = ""
        self.report = ReviewReport(version="", depth="", round="")
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def check(self) -> Tuple[bool, List[str], List[str]]:
        """执行完整检查"""
        if not self.file_path.exists():
            return False, [f"文件不存在: {self.file_path}"], []

        self.content = self.file_path.read_text(encoding="utf-8")
        self._extract_metadata()
        self._check_filename()
        self._check_chapters()
        self._extract_issues()
        self._check_issue_uniqueness()
        self._check_issue_lifecycle()
        self._check_checkpoint()

        all_messages = self.errors + self.warnings
        return len(self.errors) == 0, all_messages, self.errors

    def _extract_metadata(self):
        """提取元信息"""
        # 提取版本
        version_match = re.search(r"# 技术方案评审报告\s*v(\d+)", self.content)
        if version_match:
            self.report.version = version_match.group(1)

        # 提取评审粒度
        depth_match = re.search(r"\*\*评审粒度\*\*:\s*(quick|standard|deep)", self.content, re.I)
        if depth_match:
            self.report.depth = depth_match.group(1).lower()

        # 提取评审轮次
        round_match = re.search(r"\*\*评审轮次\*\*:\s*v(\d+)", self.content)
        if round_match:
            self.report.round = round_match.group(1)

    def _check_filename(self):
        """检查文件名规范"""
        pattern = r"^Review-v\d+\.md$"
        if not re.match(pattern, self.file_path.name):
            self.errors.append(f"文件名不符合规范: {self.file_path.name}")
            self.errors.append("  期望格式: Review-v1.md, Review-v2.md 等")

    def _check_chapters(self):
        """检查必需章节"""
        for chapter in self.REQUIRED_CHAPTERS:
            if chapter not in self.content:
                self.errors.append(f"缺少必需章节: {chapter}")

    def _extract_issues(self):
        """提取所有问题"""
        lines = self.content.split('\n')

        for i, line in enumerate(lines, 1):
            for level, pattern in self.LEVEL_PATTERN.items():
                match = re.search(pattern, line)
                if match:
                    issue_id = match.group(1)
                    issue = Issue(
                        id=issue_id,
                        level=level,
                        title="",
                        first_round=self.report.round,
                        current_round=self.report.round,
                        status="Open",
                        line_number=i
                    )
                    self.report.issues.append(issue)

        # 提取问题状态（从问题总览表格）
        self._extract_status_from_table()

    def _extract_status_from_table(self):
        """从问题总览表格提取状态"""
        # 查找表格行
        table_pattern = r"\| (B-\d+|M-\d+|C-\d+|R-\d+|Q-\d+) \| ([^|]+) \| ([^|]+) \| (\w+) \|"
        matches = re.findall(table_pattern, self.content)

        status_map = {}
        for issue_id, _, _, status in matches:
            status_map[issue_id] = status

        # 更新问题状态
        for issue in self.report.issues:
            if issue.id in status_map:
                issue.status = status_map[issue.id]

    def _check_issue_uniqueness(self):
        """检查问题编号唯一性"""
        ids = [issue.id for issue in self.report.issues]
        duplicates = set([x for x in ids if ids.count(x) > 1])
        if duplicates:
            self.errors.append(f"问题编号重复: {', '.join(duplicates)}")

    def _check_issue_lifecycle(self):
        """检查问题生命周期合法性"""
        for issue in self.report.issues:
            # 检查状态合法性
            if issue.status not in self.VALID_STATES:
                self.warnings.append(
                    f"[{issue.id}] 状态'{issue.status}'不在标准状态列表中"
                )

            # 检查 Resolved 问题是否还有后续提及
            if issue.status == "Resolved":
                # 简单检查：Resolved 后是否还有相关内容
                # 实际需要更复杂的上下文分析
                pass

    def _check_checkpoint(self):
        """检查 Checkpoint 标记"""
        if "已触发人工 Checkpoint" in self.content:
            self.report.has_checkpoint = True
            # 检查是否提供了继续指令
            if "待人工输入" in self.content or "等待" in self.content:
                pass  # 符合预期

    def generate_summary(self) -> str:
        """生成检查摘要"""
        summary_lines = [
            f"=== 评审报告检查摘要 ===",
            f"文件: {self.file_path.name}",
            f"版本: v{self.report.version}",
            f"评审轮次: v{self.report.round}",
            f"粒度: {self.report.depth or '未指定'}",
            f"发现问题数: {len(self.report.issues)}",
            f"  - Blocker: {len([i for i in self.report.issues if i.level == 'Blocker'])}",
            f"  - Major: {len([i for i in self.report.issues if i.level == 'Major'])}",
            f"  - Completeness: {len([i for i in self.report.issues if i.level == 'Completeness'])}",
            f"  - Risk: {len([i for i in self.report.issues if i.level == 'Risk'])}",
            f"  - Question: {len([i for i in self.report.issues if i.level == 'Question'])}",
            f"Checkpoint: {'是' if self.report.has_checkpoint else '否'}",
            f"错误: {len(self.errors)}",
            f"警告: {len(self.warnings)}",
        ]
        return "\n".join(summary_lines)


def check_review_report(file_path: str) -> bool:
    """检查单个评审报告"""
    checker = ReviewQualityChecker(file_path)
    success, messages, errors = checker.check()

    print(checker.generate_summary())
    print()

    if messages:
        print("=== 详细信息 ===")
        for msg in messages:
            print(f"  {'[ERROR]' if msg in errors else '[WARN]'} {msg}")

    return success


def check_review_directory(dir_path: str) -> bool:
    """检查目录下的所有评审报告"""
    dir_path = Path(dir_path)
    if not dir_path.exists():
        print(f"目录不存在: {dir_path}")
        return False

    md_files = sorted(dir_path.glob("Review-v*.md"))
    if not md_files:
        print(f"目录下没有评审报告文件: {dir_path}")
        return False

    print(f"发现 {len(md_files)} 个评审报告文件")
    print()

    all_success = True
    for md_file in md_files:
        print("-" * 50)
        if not check_review_report(str(md_file)):
            all_success = False
        print()

    return all_success


def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("用法:")
        print("  python review_quality_check.py <file.md>      # 检查单个文件")
        print("  python review_quality_check.py <directory>/    # 检查目录下所有文件")
        sys.exit(1)

    target = sys.argv[1]
    target_path = Path(target)

    if target_path.is_file():
        success = check_review_report(target)
    elif target_path.is_dir():
        success = check_review_directory(target)
    else:
        print(f"路径不存在: {target}")
        success = False

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
