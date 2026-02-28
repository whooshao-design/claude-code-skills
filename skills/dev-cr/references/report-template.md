# Code Review Report Template

```markdown
# Code Review Report

## Executive Summary

**Branch**: `feature/xxx` vs `master`
**Date**: YYYY-MM-DD
**Risk Level**: Low / Medium / High
**Verdict**: X Blockers, Y Majors, Z Minors — [MUST FIX / READY TO MERGE / NEEDS DISCUSSION]

[一段话总结：变更范围、核心风险、关键发现]

---

## Evidence Summary

| # | Command | Status | Summary |
|---|---------|--------|---------|
| 1 | `git rev-parse --abbrev-ref HEAD` | PASS | feature/xxx |
| 2 | `git diff --name-only BASE...HEAD` | PASS | 12 files changed |
| 3 | `git diff -U5 BASE...HEAD` | PASS | +342/-89 lines |
| 4 | `git show --stat` | PASS | 3 commits |
| 5 | `mvn test` | PASS | 156 tests, 0 failures |
| 6 | `mvn test jacoco:report` | SKIP | JaCoCo not configured |

---

## Scope & Risk

- **变更概述**: [一句话描述]
- **影响模块/API**: [模块列表]
- **DB 影响**: [表结构变更 / 新 SQL / 索引变更 / 无]
- **Redis 影响**: [新增 Key / TTL 变更 / 无]
- **MQ 影响**: [新增 Topic / Consumer 变更 / 无]
- **Config 影响**: [新增配置项 / 配置变更 / 无]
- **风险等级**: Low / Medium / High
- **风险理由**: [具体说明]
- **发布策略**: [canary / feature flag / 直接发布 + rollback 步骤]

---

## Top Findings (Deduped, Top 10)

### MUST FIX before merge

| # | Severity | Area | File | Summary | Executable Fix |
|---|----------|------|------|---------|----------------|
| 1 | 🔴 Blocker | Concurrency | OrderService.java:89 | Race condition | Atomic UPDATE |
| 2 | 🟠 Major | MQ | ConsumerHandler.java:45 | No idempotency | Redis SETNX dedup |

### CAN DEFER

| # | Severity | Area | File | Summary | Executable Fix |
|---|----------|------|------|---------|----------------|
| 3 | 🟡 Minor | Architecture | ConfigService.java:23 | Hardcoded timeout | Externalize to config |
| 4 | ⚪ Nit | Style | UserService.java:30 | Naming convention | Rename to queryXxx |

---

## Detailed Notes by Role

### Correctness Reviewer

#### 🔴 Blocker: Race condition in balance deduction
- **Evidence**: `OrderService.java:89` — read-then-write pattern without locking
  ```java
  int balance = getBalance(userId);
  if (balance >= amount) {
      updateBalance(userId, balance - amount);
  }
  ```
- **Problem**: 并发请求可能导致余额超扣
- **Fix (Executable steps)**:
  1. 替换为原子 UPDATE 语句
  2. 添加 WHERE amount >= ? 条件
- **Verification**:
  - `mvn test -Dtest=OrderServiceTest`
  - 检查并发测试用例通过

---

### Architecture Reviewer

[按上述格式列出发现]

---

### Security Reviewer

[按上述格式列出发现]

---

### SRE / Reliability Reviewer

[按上述格式列出发现]

---

## Patch & Action Plan

### Fix #1: Race condition in balance deduction

**File**: `src/main/java/com/example/OrderService.java`
**Method**: `deductBalance()`

**Steps**:
1. Replace read-then-write with atomic UPDATE
2. Add optimistic lock version check

**Patch**:
```diff
- int balance = getBalance(userId);
- if (balance >= amount) {
-     updateBalance(userId, balance - amount);
- }
+ int affected = orderDao.deductWithCheck(userId, amount);
+ if (affected == 0) {
+     throw new InsufficientBalanceException();
+ }
```

**Verify**:
```bash
mvn test -Dtest=OrderServiceTest -pl order-module
```

---

## Test & Coverage Review

### Coverage Data
- **Overall**: XX% (target: 80%)
- **Changed files**: XX%

### Missing Tests
| Class | Method | Reason |
|-------|--------|--------|
| OrderService | deductBalance | No concurrent test case |

### JaCoCo Configuration (if needed)
```xml
<plugin>
  <groupId>org.jacoco</groupId>
  <artifactId>jacoco-maven-plugin</artifactId>
  <version>0.8.11</version>
  <executions>
    <execution>
      <goals><goal>prepare-agent</goal></goals>
    </execution>
    <execution>
      <id>report</id>
      <phase>test</phase>
      <goals><goal>report</goal></goals>
    </execution>
  </executions>
</plugin>
```

---

## Release Checklist

- [ ] All Blocker issues resolved
- [ ] All Major issues resolved or explicitly accepted
- [ ] Tests pass (`mvn test`)
- [ ] Coverage >= 80% (or risk accepted)
- [ ] DB DDL executed in correct order
- [ ] Config defaults verified (feature flags OFF)
- [ ] Rollback plan documented
- [ ] Monitoring/alerting configured

---

## Appendix

### Excluded Issues (False Positives)

| ID | Original Finding | Exclusion Reason |
|----|-----------------|------------------|
| - | 幂等设计缺失 | 上游 Controller 已通过 @Idempotent 注解处理 |

### SQL Change List

| SQL Type | Table | Condition Fields | Suggested Index |
|----------|-------|-----------------|-----------------|

### Config Change List

| Config Key | Default | Description | Rollout Strategy |
|-----------|---------|-------------|-----------------|
```
