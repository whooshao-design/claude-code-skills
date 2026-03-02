# dev-cr Changelog

## [1.3.0] - 2026-02-28

### Added
- 数据模型简洁性检查（新增 VO/DTO/缓存结构时必检）：冗余字段、Map key 选择、字段间隐含依赖、注释与代码一致性

## [1.2.0] - 2026-02-28

### Added
- 热加载配置初始化检查：检测在静态初始化上下文中使用动态配置的问题（如 Hippo/Apollo/Nacos）
- PHASE 6.5: Fix Quality Review（修复质量自检）：对 CR 修复代码执行二次审查
  - 注释精确性、完整性检查
  - 修复一致性、变量命名、测试适配、副作用检查
- 新增原则：CLAUDE.md 约束优先（明确禁令等同 Blocker 级别）

## [1.1.0] - 2026-02-27

### Fixed
- 修复 skill 引用名称（中文名改为英文 skill ID）

### Added
- 工作流关系表（上游: test-verify，完整链路）
- 更新目录树约定，增加测试验证目录

## [1.0.0] - 2026-02-27

### Added
- 初始版本
- 4 角色多维度代码审查（架构师、安全专家、性能专家、可维护性专家）
- 16 维度评审体系
- 自动采集 git diff、构建、测试、覆盖率证据
- Top 10 去重问题 + 可执行修复方案
- references/report-template.md 报告模板
- references/role-checklists.md 角色检查清单
