# 测试验证报告

## 概要

**日期**: {YYYY-MM-DD}
**分支**: {branch-name}
**测试框架**: {framework}
**验证结论**: {PASS / PASS_WITH_WARNINGS / FAIL}

| 指标 | 结果 |
|------|------|
| 单元测试 | XX passed, X failed, X skipped |
| 集成测试 | XX passed, X failed, X skipped / SKIPPED |
| 自动修复 | X 次修复，X 次成功 |
| 新增测试 | X 个测试类，X 个测试方法 |
| 覆盖率 | XX% / N/A (JaCoCo 未配置) |

---

## 环境探测

| 探测项 | 状态 | 详情 |
|--------|------|------|
| 测试框架 | {framework} | {source} |
| TestNG Suite | {FOUND/NOT_FOUND} | {suite list} |
| JaCoCo | {FOUND/NOT_FOUND} | {config status} |
| dev-plan.md | {FOUND/NOT_FOUND} | {path} |
| 变更文件 | {N} files | 生产代码 X 个，测试代码 Y 个 |

---

## 单元测试结果

### 执行摘要

| 模块 | Suite | 通过 | 失败 | 跳过 | 耗时 |
|------|-------|------|------|------|------|
| {module} | {suite} | XX | X | X | Xs |

### 失败用例详情

#### [FAIL] {TestClass}.{testMethod}
- **错误类型**: {AssertionError / MockitoException / ...}
- **错误信息**: {message}
- **修复状态**: {FIXED (第 N 次) / UNRESOLVED}
- **修复内容**: {description}

---

## 失败修复记录

| 迭代 | 修复用例 | 失败类型 | 修复内容 | 结果 |
|------|----------|----------|----------|------|
| {N} | {TestClass.method} | {type} | {fix} | {FIXED/UNRESOLVED} |

---

## 测试用例生成

### 新增测试

| 测试类 | 被测类 | 新增方法数 | 覆盖场景 |
|--------|--------|-----------|----------|
| {TestClass} | {Class} | {N} | {scenarios} |

### 未生成原因

| 类名 | 原因 |
|------|------|
| {Class} | {reason} |

---

## 集成测试结果

| 模块 | Suite | 通过 | 失败 | 跳过 | 状态 |
|------|-------|------|------|------|------|
| {module} | {suite} | XX | X | X | {PASS/FAIL/SKIPPED} |

---

## 覆盖率分析

### 覆盖率数据

{JaCoCo 数据表 或 静态分析对照表}

### 未覆盖建议

| 类 | 方法 | 未覆盖分支 | 建议测试场景 |
|----|------|-----------|-------------|
| {Class} | {method} | {branch} | {scenario} |

---

## 后续建议

- [ ] {具体建议}
- 建议执行 `dev-cr` 进行代码评审
