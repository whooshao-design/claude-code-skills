# test-verify Changelog

## [1.3.0] - 2026-02-28

### Added
- Step 3 拆分为单元测试生成 (3.4) 和集成测试生成 (3.5)
- Step 3.3 测试类型判断逻辑（根据类特征决定生成单元测试或集成测试）
- Step 3.5 全量回归验证（修复/生成后重跑 checkin suite，检测回归）
- 集成测试环境不可用时自动跳过所有集成测试生成（熔断）

## [1.2.0] - 2026-02-28

### Added
- 熔断机制防止无限修复循环
  - Step 2: 同一测试连续失败 2 次标记 UNRESOLVED
  - 回归检测、停滞检测
  - 最多 3 轮迭代
- Step 3.4 生成验证熔断

## [1.1.0] - 2026-02-28

### Added
- 三维验证标准
  - 变更代码测试覆盖门控（100% 类，≥80% 方法）
  - 覆盖率阈值（JaCoCo line ≥80%，branch ≥70%）
  - 区分单元测试 / 集成测试分类规则
- 判定结果: PASS / PASS_WITH_WARNINGS / FAIL

## [1.0.0] - 2026-02-27

### Added
- 初始版本
- 自动探测测试框架（TestNG/JUnit + Mockito）
- 执行单元测试并分析失败
- 尝试修复失败测试
- 生成缺失测试用例
- 输出覆盖率分析报告
- 独立输出到测试验证目录
- references/report-template.md 报告模板
- references/test-checklist.md 测试清单
