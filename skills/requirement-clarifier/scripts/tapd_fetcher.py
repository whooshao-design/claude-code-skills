#!/usr/bin/env python3
"""
TAPD 需求抓取工具

用于从 TAPD 故事链接中提取需求信息，自动填充需求规格说明书。

依赖：
- Playwright MCP 服务
- 或直接调用 TAPD Open API

使用方式：
    python tapd_fetcher.py <TAPD_URL>
    python tapd_fetcher.py <TAPD_URL> --format json
    python tapd_fetcher.py <TAPD_URL> --output extracted.json
"""

import re
import sys
import json
import argparse
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, List
from datetime import datetime


@dataclass
class TAPDStory:
    """TAPD 故事信息"""
    title: str = ""
    description: str = ""
    status: str = ""
    priority: str = ""
    story_type: str = ""
    owner: str = ""
    created_at: str = ""
    modified_at: str = ""
    acceptance_criteria: str = ""
    attachments: List[Dict] = field(default_factory=list)
    tasks: List[Dict] = field(default_factory=list)
    comments: List[Dict] = field(default_factory=list)
    labels: List[str] = field(default_factory=list)
    source_url: str = ""


@dataclass
class ExtractedRequirement:
    """提取后的需求结构"""
    feature_name: str = ""
    summary: str = ""
    background: str = ""
    scope_included: List[str] = field(default_factory=list)
    scope_excluded: List[str] = field(default_factory=list)
    business_rules: List[str] = field(default_factory=list)
    acceptance_criteria: List[str] = field(default_factory=list)
    input_fields: List[Dict] = field(default_factory=list)
    output_fields: List[Dict] = field(default_factory=list)
    performance_requirements: Dict = field(default_factory=dict)
    error_codes: List[Dict] = field(default_factory=list)
    open_questions: List[str] = field(default_factory=list)
    raw_content: str = ""


class TAPDFetcher:
    """TAPD 故事抓取器"""

    def __init__(self):
        self.story = TAPDStory()

    def fetch(self, url: str) -> TAPDStory:
        """
        从 TAPD URL 提取故事信息

        支持两种方式：
        1. Playwright MCP（需要 MCP 服务运行）
        2. TAPD Open API（需要 API Token）
        """
        # 解析故事 ID
        story_id = self._extract_story_id(url)
        if not story_id:
            raise ValueError(f"无法从 URL 提取故事 ID: {url}")

        self.story.source_url = url

        # 尝试 Playwright MCP
        if self._try_playwright_mcp(url, story_id):
            return self.story

        # 尝试 TAPD API
        if self._try_tapd_api(story_id):
            return self.story

        raise ConnectionError("无法连接 TAPD，请检查 URL 或配置 API Token")

    def _extract_story_id(self, url: str) -> Optional[str]:
        """从 URL 提取故事 ID"""
        # 匹配模式：/story/12345 或 story_id=12345
        patterns = [
            r'/story/(\d+)',
            r'story_id=(\d+)',
            r'/s/(\d+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    def _try_playwright_mcp(self, url: str, story_id: str) -> bool:
        """尝试使用 Playwright MCP 抓取"""
        try:
            # 检查是否有 Playwright MCP
            # 这里需要 MCP 服务的支持，暂不实现
            return False
        except Exception:
            return False

    def _try_tapd_api(self, story_id: str) -> bool:
        """尝试使用 TAPD Open API 抓取"""
        # 从环境变量获取 API Token
        api_token = self._get_api_token()
        if not api_token:
            return False

        try:
            # TAPD Open API: GET /stories/{story_id}
            import requests

            base_url = "https://api.tapd.cn"
            endpoint = f"{base_url}/stories/{story_id}"

            params = {"fields": "id,title,description,status,priority,owner,created,modified,acceptance_criteria"}
            headers = {"Authorization": f"Bearer {api_token}"}

            response = requests.get(endpoint, params=params, headers=headers, timeout=30)
            response.raise_for_status()

            data = response.json()
            if data.get("data"):
                self._parse_api_response(data["data"])
                return True

        except Exception as e:
            print(f"[WARN] TAPD API 调用失败: {e}")

        return False

    def _get_api_token(self) -> Optional[str]:
        """获取 TAPD API Token"""
        import os
        return os.environ.get("TAPD_API_TOKEN")

    def _parse_api_response(self, data: dict):
        """解析 API 响应"""
        self.story.title = data.get("title", "")
        self.story.description = data.get("description", "")
        self.story.status = data.get("status", "")
        self.story.priority = data.get("priority", "")
        self.story.owner = data.get("owner", "")
        self.story.created_at = data.get("created", "")
        self.story.modified_at = data.get("modified", "")
        self.story.acceptance_criteria = data.get("acceptance_criteria", "")

    def extract_requirement(self) -> ExtractedRequirement:
        """从故事信息提取需求规格"""
        requirement = ExtractedRequirement()

        # 功能名称（从标题提取）
        requirement.feature_name = self._extract_feature_name()
        requirement.summary = self.story.title
        requirement.background = self._extract_background()

        # 范围
        requirement.scope_included = self._extract_scope_included()
        requirement.scope_excluded = self._extract_scope_excluded()

        # 业务规则
        requirement.business_rules = self._extract_business_rules()

        # 验收标准
        requirement.acceptance_criteria = self._extract_acceptance_criteria()

        # 原始内容（用于人工审核）
        requirement.raw_content = f"""
# {self.story.title}

## 描述
{self.story.description}

## 验收标准
{self.story.acceptance_criteria}

## 元信息
- 状态: {self.story.status}
- 优先级: {self.story.priority}
- 负责人: {self.story.owner}
- 标签: {', '.join(self.story.labels)}
"""

        return requirement

    def _extract_feature_name(self) -> str:
        """从标题提取功能名称"""
        # 移除常见前缀
        title = re.sub(r"^(【.*?】|\[.*?\]|\d+\.)", "", self.story.title)
        return title.strip()

    def _extract_background(self) -> str:
        """提取业务背景"""
        desc = self.story.description
        # 尝试从描述中提取背景
        if "为了" in desc or "因为" in desc or "解决" in desc:
            return desc
        return ""

    def _extract_scope_included(self) -> List[str]:
        """提取包含范围"""
        return []

    def _extract_scope_excluded(self) -> List[str]:
        """提取不包含范围"""
        return []

    def _extract_business_rules(self) -> List[str]:
        """提取业务规则"""
        return []

    def _extract_acceptance_criteria(self) -> List[str]:
        """提取验收标准"""
        criteria = []
        text = self.story.acceptance_criteria or ""

        # 按行分割，提取列表项
        for line in text.split('\n'):
            line = line.strip()
            if line.startswith('-') or line.startswith('*') or line.startswith('1.'):
                criteria.append(line.lstrip('-*1. ').strip())

        return criteria


class TAPDRequirementExtractor:
    """TAPD 需求提取器（支持更多字段）"""

    def __init__(self, fetcher: TAPDFetcher):
        self.fetcher = fetcher

    def extract_all(self) -> ExtractedRequirement:
        """提取完整需求信息"""
        requirement = self.fetcher.extract_requirement()

        # 尝试从描述中提取更多信息
        if self.fetcher.story.description:
            self._extract_fields_from_description(
                requirement,
                self.fetcher.story.description
            )

        return requirement

    def _extract_fields_from_description(self, requirement: ExtractedRequirement, desc: str):
        """从描述文本中提取字段信息"""
        # 提取输入字段
        input_pattern = r"输入[：:]\s*\n(.*?)(?=\n\n|\n[A-Z]|$)"
        if match := re.search(input_pattern, desc, re.DOTALL | re.IGNORECASE):
            requirement.input_fields = self._parse_field_table(match.group(1))

        # 提取输出字段
        output_pattern = r"输出[：:]\s*\n(.*?)(?=\n\n|\n[A-Z]|$)"
        if match := re.search(output_pattern, desc, re.DOTALL | re.IGNORECASE):
            requirement.output_fields = self._parse_field_table(match.group(1))

        # 提取错误码
        error_pattern = r"(错误码|异常码)[：:]\s*\n(.*?)(?=\n\n|\n[A-Z]|$)"
        if match := re.search(error_pattern, desc, re.DOTALL | re.IGNORECASE):
            requirement.error_codes = self._parse_error_table(match.group(1))

    def _parse_field_table(self, text: str) -> List[Dict]:
        """解析字段表格"""
        fields = []
        for line in text.split('\n'):
            line = line.strip()
            if not line or line.startswith('|') is False:
                continue

            # 解析 | 分割的表格
            parts = [p.strip() for p in line.strip('|').split('|')]
            if len(parts) >= 2:
                fields.append({
                    "field": parts[0],
                    "type": parts[1] if len(parts) > 1 else "",
                    "description": parts[2] if len(parts) > 2 else ""
                })
        return fields

    def _parse_error_table(self, text: str) -> List[Dict]:
        """解析错误码表格"""
        errors = []
        for line in text.split('\n'):
            line = line.strip()
            if not line or line.startswith('|') is False:
                continue

            parts = [p.strip() for p in line.strip('|').split('|')]
            if len(parts) >= 2:
                errors.append({
                    "code": parts[0],
                    "message": parts[1],
                    "handling": parts[2] if len(parts) > 2 else ""
                })
        return errors


def format_for_claude(requirement: ExtractedRequirement) -> str:
    """格式化输出，供 Claude 读取"""
    output = {
        "feature_name": requirement.feature_name,
        "summary": requirement.summary,
        "background": requirement.background,
        "scope_included": requirement.scope_included,
        "scope_excluded": requirement.scope_excluded,
        "business_rules": requirement.business_rules,
        "acceptance_criteria": requirement.acceptance_criteria,
        "input_fields": requirement.input_fields,
        "output_fields": requirement.output_fields,
        "error_codes": requirement.error_codes,
        "raw_content": requirement.raw_content
    }
    return json.dumps(output, ensure_ascii=False, indent=2)


def main():
    parser = argparse.ArgumentParser(description="TAPD 需求抓取工具")
    parser.add_argument("url", help="TAPD 故事链接")
    parser.add_argument("--format", choices=["json", "text"], default="json",
                        help="输出格式")
    parser.add_argument("--output", "-o", help="输出文件路径")
    parser.add_argument("--api-token", help="TAPD API Token（也可通过环境变量 TAPD_API_TOKEN 设置）")

    args = parser.parse_args()

    # 设置 API Token
    if args.api_token:
        import os
        os.environ["TAPD_API_TOKEN"] = args.api_token

    # 抓取数据
    fetcher = TAPDFetcher()
    try:
        fetcher.fetch(args.url)
    except ConnectionError as e:
        print(f"[ERROR] {e}")
        sys.exit(1)

    # 提取需求
    extractor = TAPDRequirementExtractor(fetcher)
    requirement = extractor.extract_all()

    # 输出
    if args.format == "json":
        output = format_for_claude(requirement)
    else:
        output = requirement.raw_content

    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
        print(f"[INFO] 已输出到: {args.output}")
    else:
        print(output)


if __name__ == "__main__":
    main()
