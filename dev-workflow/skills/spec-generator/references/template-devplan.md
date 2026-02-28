# {功能名称} - 开发计划

## Overview
[一句话描述核心功能]

## Technical Specification
> 详细技术方案请参阅：[tech-spec.md](../技术方案/tech-spec.md)

---

## Task Breakdown

### Task 1: [任务名称]

- **ID**: task-1
- **Description**: [What needs to be done]
- **File Scope**: [Directories or files involved]
  - `src/main/java/com/example/Xxx.java`
  - `src/test/java/com/example/XxxTest.java`
- **Dependencies**: [None / task-x]
- **Test Command**:
  ```bash
  mvn test -Dtest=XxxTest -pl module-name
  ```
- **Test Focus**: [Scenarios to cover - 只描述测试场景，不写代码]
  - 正常流程测试
  - 边界条件测试
  - 异常处理测试

---

### Task 2: [任务名称]

- **ID**: task-2
- **Description**: [What needs to be done]
- **File Scope**: [Directories or files involved]
- **Dependencies**: task-1
- **Test Command**: [e.g., mvn test ...]
- **Test Focus**: [Scenarios to cover]

---

### Task 3: [任务名称]

- **ID**: task-3
- **Description**: [What needs to be done]
- **File Scope**: [Directories or files involved]
- **Dependencies**: task-1
- **Test Command**: [e.g., mvn test ...]
- **Test Focus**: [Scenarios to cover]

---

### Task N: [任务名称]
[重复上述格式]

---

## 任务依赖关系

```
任务依赖图：

task-1 ──┬──▶ task-2
         │
         └──▶ task-3
              │
              └──▶ task-4
```

**并行建议**：
- task-1 和 task-2 可以并行开发
- task-3 依赖 task-1完成后开始
- task-4 依赖 task-3 完成后开始

---

## Acceptance Criteria

### 功能验收
- [ ] 验收点 1
- [ ] 验收点 2
- [ ] 验收点 3

### 非功能验收
- [ ] 单元测试覆盖率 ≥90%
- [ ] 集成测试通过
- [ ] 代码编译通过
- [ ] SonarQube 无 blocker/critical 问题

### 上线验收
- [ ] 预发布环境验证通过
- [ ] 监控告警配置完成
- [ ] 回滚方案验证通过

---

## Technical Notes

### 关键技术决策
- [决策1]：[说明]
- [决策2]：[说明]

### 需要注意的约束
- [约束1]：[说明]
- [约束2]：[说明]

### 参考资料
- [参考1]：[链接或位置]
- [参考2]：[链接或位置]

---

## 开发检查清单

### 开发前
- [ ] 理解 tech-spec.md 全部内容
- [ ] 确认任务依赖关系
- [ ] 准备好开发环境

### 开发中
- [ ] 遵循项目代码规范
- [ ] 同步更新相关文档
- [ ] 编写单元测试

### 提测前
- [ ] 本地测试通过
- [ ] 代码评审完成
- [ ] SonarQube 检查通过

---

## 里程碑

| 里程碑 | 计划日期 | 实际日期 | 状态 |
|--------|----------|----------|------|
| Task-1 开发完成 | YYYY-MM-DD | | 待开始 |
| Task-2 开发完成 | YYYY-MM-DD | | 待开始 |
| ... | | | |
| 提测 | YYYY-MM-DD | | 待开始 |
| 产品验收 | YYYY-MM-DD | | 待开始 |
| 上线 | YYYY-MM-DD | | 待开始 |

---

## 变更记录

| 版本 | 日期 | 作者 | 变更说明 |
|------|------|------|----------|
| v1.0 | YYYY-MM-DD | xxx | 初始版本 |
