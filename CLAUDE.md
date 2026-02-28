# CLAUDE.md

## 项目概述

个人 Claude Code 技能套件仓库，管理多个工作流的 skills。

## 技能安装机制 — 重要经验教训

### ✅ 可靠方式: User Skills (`~/.claude/skills/`)

直接复制 skill 目录到 `~/.claude/skills/`，和 `codeagent` 相同的加载机制。
重启 Claude Code 后自动生效，无需任何注册。

### ❌ 不可靠方式: Plugin System (`~/.claude/plugins/local/`)

手动修改 `installed_plugins.json` / `settings.json` 注册本地插件——**经过 5 次尝试确认不可行**。
可能原因: 本地插件可能仅支持通过 Claude Code CLI 官方安装，不支持手动注册。

### SKILL.md frontmatter 必须包含三个字段

```yaml
---
name: skill-name
description: 何时触发此 skill 的描述
version: 1.0.0
---
```

缺少任一字段都可能导致 skill 不被发现。

### 符号链接不可靠

在 `~/.claude/skills/` 下使用符号链接指向仓库文件——Claude Code 可能不跟随符号链接扫描。
始终使用实体文件复制。

## 仓库结构

```
claude-code-skills/
├── dev-workflow/                    # 工作流组
│   ├── .claude-plugin/plugin.json  # 工作流元数据 (用于发现)
│   └── skills/                     # 技能目录
├── install.py                       # 安装脚本
├── install.sh                       # Bash 安装脚本
└── CLAUDE.md                        # 本文件
```

## 安装原理

安装脚本将选中的 skill 目录复制到 `~/.claude/skills/`，重启 Claude Code 即生效。
不修改 `installed_plugins.json` 或 `settings.json`。
