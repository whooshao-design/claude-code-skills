# claude-code-skills

个人 Claude Code 技能套件，支持多插件管理与选择性部署。

## 插件列表

### dev-workflow

开发生命周期工作流技能套件。

| Skill | 说明 |
|---|---|
| `requirement-clarifier` | 需求澄清 - 结构化梳理需求，输出需求规格文档 |
| `spec-generator` | 方案设计 - 生成技术方案和开发计划 |
| `tech-review` | 方案评审 - 多维度评审技术方案 |
| `code-dev` | 代码开发 - 基于开发计划逐步实现代码 |
| `test-verify` | 测试验证 - 单元测试/集成测试执行、生成与覆盖率分析 |
| `dev-cr` | 代码评审 - 16 维度代码审查 |

**工作流**: requirement-clarifier → spec-generator → tech-review → code-dev → test-verify → dev-cr

## 安装

```bash
git clone https://github.com/whooshao-design/claude-code-skills.git
cd claude-code-skills
```

### 安装所有插件

```bash
python3 install.py
# 或
bash install.sh
```

### 安装指定插件

```bash
python3 install.py --plugins dev-workflow
```

### 插件内选择性安装

```bash
python3 install.py --plugins dev-workflow --skills code-dev,test-verify,dev-cr
```

### 查看可用插件和 skills

```bash
python3 install.py --list
```

### 强制覆盖

```bash
python3 install.py --force
```

### 卸载

```bash
# 卸载所有插件
python3 install.py --uninstall

# 卸载指定插件
python3 install.py --uninstall --plugins dev-workflow
```

## 安装原理

安装脚本会：

1. 自动发现仓库中的插件（含 `.claude-plugin/plugin.json` 的子目录）
2. 在 `~/.claude/plugins/local/{plugin-name}/` 创建插件目录
3. 将选中的 skill 目录以**符号链接**方式挂载（修改仓库文件立即生效）
4. 在 `installed_plugins.json` 中注册插件
5. 在 `settings.json` 中启用插件

## 目录结构

```
claude-code-skills/
├── dev-workflow/                    # 插件: 开发工作流
│   ├── .claude-plugin/plugin.json
│   └── skills/
│       ├── requirement-clarifier/
│       ├── spec-generator/
│       ├── tech-review/
│       ├── code-dev/
│       ├── test-verify/
│       └── dev-cr/
├── future-workflow/                 # 未来可扩展...
│   ├── .claude-plugin/plugin.json
│   └── skills/
├── install.py
├── install.sh
├── README.md
└── .gitignore
```

## 更新 Skills

由于使用符号链接，只需 `git pull` 即可获取最新版本：

```bash
cd ~/projects/ai/claude-code-skills
git pull
```

如需增减已安装的 skills，重新运行安装脚本：

```bash
python3 install.py --force --plugins dev-workflow --skills code-dev,test-verify
```

## 添加新插件

在仓库根目录创建新的子目录，包含 `.claude-plugin/plugin.json` 和 `skills/` 目录即可自动被安装脚本发现。
