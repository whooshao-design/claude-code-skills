---
name: dev-cr
description: 证据驱动的代码评审系统。自动采集 git diff、构建、测试、覆盖率证据，4 角色多维度审查，输出 Top 10 去重问题 + 可执行修复方案。目标技术栈：Java + DB + Redis + MQ，Maven 构建。使用条件：用户要求代码评审、CR、review 时触发。
version: 1.3.0
---
> **Skill**: dev-cr | **Version**: 1.3.0


# 证据驱动代码评审系统

## 快速开始

**触发方式**：当前分支与 master 对比，自动采集证据并执行评审。

**输出**：单一 Markdown 评审报告，包含 Top 10 去重问题 + 可执行修复方案。

## 目录约定

> **重要**：`.claude/specs/` 是**用户级目录**，位于 `~/.claude/specs/`（即 `/home/{user}/.claude/specs/`），**不是**当前项目目录下的 `.claude/specs/`。

---

## 绝对原则

> **不要要求用户粘贴 diff 或测试输出。**
> 首先通过执行命令自动采集证据。
> 仅当命令执行不可能时，才要求用户手动提供。

---

## 评审工作流概览

```
PHASE 2: Evidence Collection（自动执行）
    ↓ git diff / build / test / coverage
    ↓ 自动探测 req-spec.md + tech-spec.md（有则用，无则跳过）
PHASE 1: Scope & Risk（基于证据总结）
    ↓ 变更范围 / 影响面 / 风险等级
PHASE 3: Multi-Role Review（4 角色并行）
    ↓ Correctness / Architecture / Security / SRE
PHASE 4: Problem Verification（问题验证，防误报）
    ↓ 上下游分析，排除误报
PHASE 5: Consolidation（去重 Top 10）
    ↓ 跨角色去重 + 排序
PHASE 6: Patch & Execution Plan
    ↓ Blocker/Major 可执行修复方案
PHASE 7: Final Report（单一 Markdown 输出）
```

**注意**：执行顺序是 PHASE 2 → 1 → 3 → 4 → 5 → 6 → 7（先采集证据，再总结 Scope，验证后去重输出）。

---

## 审查核心原则：避免过度工程

**审查代码时，同样要警惕「过度设计」，这与「设计不足」同样重要。**

### 只做必要的事

| ❌ 过度工程 | ✅ 恰当实现 |
|-------------|-------------|
| Bug 修复时顺便重构周围代码 | 只修复 Bug 本身 |
| 简单功能添加复杂配置项 | 硬编码或最简配置 |
| 为假设的未来需求预留扩展 | 只实现当前需求 |
| 一次性逻辑抽象成工具类 | 内联实现，需要时再抽象 |

### 信任内部代码

| 场景 | 处理方式 |
|------|----------|
| 内部方法调用 | 信任调用方已校验，不重复校验 |
| 框架保证的行为 | 信任框架，不额外防御 |
| 系统边界（用户输入、外部 API） | **必须**校验和防御 |

### 审查时的判断标准

遇到以下情况，标记为 **Nit（过度工程）**：
- 为不可能发生的场景添加错误处理
- 创建只用一次的 Helper/Util 类
- 添加未请求的「优化」或「改进」
- 过早抽象（仅一处使用就抽成接口/抽象类）
- 添加冗余的 null 检查（框架/上游已保证非空）

---

## PHASE 1: Scope & Risk

**在证据采集完成后输出**（依赖 PHASE 2 的数据）：

```markdown
## Scope & Risk Summary
- **变更概述**: [基于 diff 的一句话描述]
- **影响模块/API**: [受影响的模块列表]
- **DB 影响**: [表结构变更 / 新 SQL / 索引变更 / 无]
- **Redis 影响**: [新增 Key / TTL 变更 / 无]
- **MQ 影响**: [新增 Topic / Consumer 变更 / 无]
- **Config 影响**: [新增配置项 / 配置变更 / 无]
- **风险等级**: Low / Medium / High
- **风险理由**: [具体说明]
- **发布策略**: [canary / feature flag / 直接发布 + rollback 步骤]
```

### 系统模块识别

不同模块类型有不同审查标准：

| 模块类型 | 识别特征 | 审查重点 |
|----------|----------|----------|
| **线上主流程** | 决策引擎、规则执行、核心服务 | 性能(ms级)、幂等、熔断、埋点 |
| **作业系统/批跑** | Scheduler、Job、Batch | 限流、断点续跑、幂等、大数据量 |
| **管理后台** | Admin、Console、配置管理 | 权限校验、操作审计 |
| **对外接口** | API、Gateway、Facade | 参数校验、限流、版本兼容 |

---

## PHASE 2: Evidence Collection（必须，自动执行）

**假设仓库在本地，命令可以执行。**

### Step 0: 确定对比基准

```bash
# 获取当前分支
git rev-parse --abbrev-ref HEAD

# 尝试 fetch（如果网络允许；失败则继续）
git fetch --all --prune 2>/dev/null || echo "SKIP: fetch failed, using local refs"

# 确定 BASE ref
if git rev-parse --verify refs/remotes/origin/master >/dev/null 2>&1; then
  BASE="origin/master"
else
  BASE="master"
fi
echo "BASE=$BASE"
```

### Step 0.5: 获取上下文文档

**文档来源**（按优先级，高优先级覆盖低优先级）：

1. **用户对话指定**（最高优先级）：用户通过 `@path/to/req-spec.md` 或对话中提供文件路径
2. **自动探测**：搜索 `~/.claude/specs/` 下的文档
3. **无文档**：跳过，仅基于代码审查

**自动探测逻辑**（仅在用户未指定时执行）：

```bash
# 搜索 specs 目录
SPECS_DIR="$HOME/.claude/specs"
if [ -d "$SPECS_DIR" ]; then
  ls -d $SPECS_DIR/*/
  find $SPECS_DIR -name "req-spec.md" -type f 2>/dev/null
  find $SPECS_DIR -name "tech-spec.md" -type f 2>/dev/null
else
  echo "SKIP: ~/.claude/specs/ not found"
fi
```

**自动探测匹配策略**（按优先级）：
1. 如果用户在对话中指定了需求名称 → 精确匹配 `~/.claude/specs/{需求名称}/`
2. 如果当前分支名包含需求标识 → 模糊匹配目录名
3. 如果仅找到一个 specs 目录 → 直接使用
4. 如果找到多个或零个 → 跳过，仅基于代码审查

**找到文档后**（无论来源是用户指定还是自动探测）：
- `req-spec.md` → 用于 PHASE 3 后的功能完整性检查
- `tech-spec.md` → 用于 Role 2 架构审查时作为设计基准

记录探测结果：

```markdown
| 文档 | 状态 | 来源 | 路径 |
|------|------|------|------|
| req-spec.md | FOUND / NOT_FOUND | 用户指定 / 自动探测 / - | path |
| tech-spec.md | FOUND / NOT_FOUND | 用户指定 / 自动探测 / - | path |
```

### Step 1: Git 证据

按顺序执行，捕获输出：

```bash
# 1. 变更文件列表
git diff --name-only $BASE...HEAD

# 2. 变更统计
git diff --stat $BASE...HEAD

# 3. 详细 diff（带 5 行上下文）
git diff -U5 $BASE...HEAD

# 4. 提交历史
git log --oneline $BASE...HEAD

# 5. 最近提交统计
git show --stat
```

### Step 1.5: 读取变更文件全文

**仅看 diff 不够，必须读取变更文件的完整内容获取上下文**：

- 对 `git diff --name-only` 输出的每个文件，使用 Read 工具读取全文
- 重点关注：变更方法的调用方（上游）和被调用方（下游）
- 这一步是问题验证（防误报）的基础——不读全文就无法做上下游分析

### Step 2: Build & Test 证据

```bash
# 编译 + 运行测试
mvn -q test 2>&1

# 如果失败，记录错误并继续（不阻塞评审）
```

### Step 3: Coverage 证据

```bash
# 运行 JaCoCo 报告
mvn -q test jacoco:report 2>&1

# 查找报告文件（优先 CSV 便于解析）
find . -path "*/site/jacoco/jacoco.csv" -type f 2>/dev/null
find . -path "*/site/jacoco/index.html" -type f 2>/dev/null

# 如果 CSV 存在，解析覆盖率：
# - 读取 CSV，按 PACKAGE + CLASS 汇总 INSTRUCTION_MISSED / INSTRUCTION_COVERED
# - 计算总覆盖率 = COVERED / (COVERED + MISSED) * 100
# - 重点关注变更文件对应类的覆盖率
# 如果报告不存在或命令失败：标记 coverage 为 SKIP
# 将缺失覆盖率证据作为风险记录到 PHASE 5
```

### 证据汇总格式

每条命令输出：

```markdown
| # | Command | Status | Summary |
|---|---------|--------|---------|
| 1 | git diff --name-only | PASS | 12 files changed |
| 2 | git diff -U5 | PASS | +342/-89 lines |
| 3 | mvn test | PASS | 156 tests, 0 failures |
| 4 | jacoco:report | SKIP | JaCoCo plugin not configured |
```

### 命令失败处理

如果任何命令无法执行：
1. 记录失败原因（权限、缺少工具、无仓库等）
2. 用已有证据继续评审
3. **仅在此时**才要求用户提供最小必要信息（diff 或测试输出）

---

## PHASE 3: Multi-Role Review（4 角色）

### 严重程度定义

| 级别 | 标记 | 说明 | 处理要求 |
|------|------|------|----------|
| **Blocker** | 🔴 | 必须修复才能合并 | 阻塞合并 |
| **Major** | 🟠 | 强烈建议修复 | 合并前修复 |
| **Minor** | 🟡 | 建议改进 | 可后续修复 |
| **Nit** | ⚪ | 风格/偏好 | 可选 |

### 通用规则

- 每条发现**必须**引用 diff 或命令输出中的证据（文件/类/方法/行号）
- 每条 Major/Blocker **必须**包含可执行修复步骤和验证步骤
- 发现问题后需进行上下游验证，减少误报

### 问题验证（防误报）

**每个问题在纳入报告前，必须验证**：

| 验证维度 | 检查内容 |
|----------|----------|
| **上游分析** | 调用方是否已处理该场景？ |
| **下游分析** | 被调用方是否有保障？ |
| **业务场景** | 该场景在业务上是否可达？ |
| **代码上下文** | 是否有注释/配置说明是有意设计？ |

误报问题标记为「已排除」并说明原因，记录到报告附录。

---

### Role 1: Correctness Reviewer（正确性审查）

**关注点**：

- **事务正确性**：`@Transactional` 正确性、rollback 规则、propagation
- **MQ 消费幂等**：messageId/bizKey 去重、ack/commit 时序
- **缓存一致性**：DB write + cache invalidate 模式、TTL 设置
- **并发与锁**：乐观锁/version、分布式锁正确性
  - 先查后改是否有竞态条件
  - CAS 操作是否有 ABA 问题
  - 锁超时/锁续期/锁释放
- **查询正确性**：N+1 问题、分页稳定性
- **异常处理与重试安全**：幂等感知的重试
- **状态机完整性**（如涉及）：
  - 状态流转是否完整覆盖所有业务场景
  - 是否存在孤立状态无法流转到终态
  - 异常中断后能否恢复继续处理
  - 最终一致性保障（TCC/Saga/消息事务）

**典型问题示例**：

```java
// ❌ 错误：先查后改，存在并发问题
int balance = getBalance(userId);
if (balance >= amount) {
    updateBalance(userId, balance - amount);  // 并发时可能超扣
}

// ✅ 正确：原子操作
int affected = updateBalanceWithCheck(userId, amount);
// UPDATE balance SET amount = amount - ? WHERE user_id = ? AND amount >= ?
if (affected == 0) {
    throw new InsufficientBalanceException();
}
```

---

### Role 2: Architecture Reviewer（架构审查）

**关注点**：

- 分层违规、耦合、边界问题
- Config/timeouts/retries 是否外部化
- 依赖倒置与可测性
- 兼容性：DTO/schema/序列化演进
- 是否符合现有架构分层
- 是否有循环依赖
- 新增接口是否有统一封装

**数据模型简洁性检查**（新增 VO / DTO / 缓存结构时必检）：

| 检查项 | 说明 | 反例 |
|--------|------|------|
| 冗余字段 | 能从其他字段推导出的字段不应独立存储 | 同时存储 `groupToEditionMapping` 和按 editionId 索引的 `grayRoutes`，实际可以直接用 groupId 作 key |
| Map key 选择 | 能一步查表的不应引入中间映射 | `mapping.get(groupId)` → `editionId` → `routes.get(editionId)` 可简化为 `routes.get(groupId)` |
| 字段间隐含依赖 | 多个字段的 key/value 存在关联时考虑合并 | A 的 key 是 B 的 value，说明可以合并为一个 Map |
| 注释与代码一致性 | 注释中的类型描述必须与实际代码匹配 | 注释写 "key:灰度分组id" 但实际 key 是 editionId |

**tech-spec.md 基准对比**（如 Step 0.5 探测到技术方案）：
- 实现是否与技术方案设计一致
- 是否偏离了方案中的架构分层/模块边界
- 方案中的关键设计决策是否被正确落地

**DB 表结构兼容性**（如涉及 DDL）：

| 操作 | 兼容性 | 注意事项 |
|------|--------|----------|
| 新增字段 | ✅ | 必须有默认值或允许 NULL |
| 删除字段 | ⚠️ | 先停止使用，再删除 |
| 修改字段类型 | ❌ | 新增字段 + 数据迁移 |
| 新增索引 | ✅ | 注意锁表时间 |

**兼容性发布顺序**：

```
推荐发布顺序：
1. 新增字段/索引：先 DDL，后代码
2. 删除字段/索引：先代码（停止使用），后 DDL
3. 字段类型变更：评估兼容性，必要时分步发布
```

**SQL 变更清单输出**：

```markdown
| SQL 类型 | 表名 | 条件字段 | 建议索引 |
|----------|------|----------|----------|
| SELECT | t_credit_record | user_id, status | idx_user_status |
| UPDATE | t_order | order_no | uk_order_no |
```

---

### Role 3: Security Reviewer（安全审查）

**关注点**：

- SQL 注入、不安全字符串拼接
- 敏感信息日志（PII/tokens）、密钥泄露
- 反序列化风险
- Redis key 隔离性/可猜测性
- 输入校验和鉴权（如涉及接口变更）
- 越权访问风险

**SQL 注入扫描**：

```bash
# 检查 MyBatis XML 中的 ${} 拼接（高风险）
git diff $BASE...HEAD -- "*.xml" | grep -n '\${' || echo "无 \${} 拼接"

# 检查 Java 代码中的字符串拼接 SQL
git diff $BASE...HEAD -- "*.java" | grep -n 'concat\|StringBuilder.*sql\|"SELECT.*+\|"UPDATE.*+\|"DELETE.*+' -i || echo "无字符串拼接 SQL"
```

**敏感信息日志扫描**：

```bash
# 检查日志中的敏感信息
git diff $BASE...HEAD -- "*.java" | grep -n 'log\..*password\|log\..*token\|log\..*secret\|log\..*idCard\|log\..*phone\|log\..*bankCard' -i || echo "无敏感信息日志"
```

---

### Role 4: SRE/Reliability Reviewer（可靠性审查）

**关注点**：

- DB/Redis/MQ/HTTP 的超时设置
- 重试/退避策略、DLQ 策略、毒消息处理
- 资源池、背压机制
- 可观测性：traceId/bizKey/messageId、metrics
- 埋点完整性（入口/决策/异常三类埋点）
- 放量设计（灰度开关、配置默认值）

**批跑/作业系统专项检查**（如涉及 Scheduler/Job/Batch）：
- [ ] 调用下游是否有限流（RateLimiter、信号量）
- [ ] 批量处理是否分页/分批（每批 ≤500）
- [ ] 是否有进度记录（支持断点续跑）
- [ ] 是否考虑数据倾斜
- [ ] 是否有处理耗时监控

**埋点检查**：

```bash
# 在变更文件中搜索埋点方法
git diff $BASE...HEAD --name-only | xargs grep -l "sumReport\|counterReport\|averageReport\|errorReport" 2>/dev/null || echo "无埋点"
```

- [ ] 核心业务入口是否有 sumReport/counterReport
- [ ] 关键分支决策点是否有 counterReport
- [ ] 异常处理是否有 errorReport
- [ ] 埋点命名规范：`{系统}.{模块}.{操作}.{结果}`

**放量设计检查**：

```bash
# 搜索配置中心/灰度相关代码
git diff $BASE...HEAD | grep -E "hippo|config|switch|gray|灰度|放量" -i
```

- [ ] 新增配置项是否有默认值
- [ ] 默认值走哪条流程（新流程/旧流程）
- [ ] 是否支持灰度放量（百分比/白名单）

输出配置清单：

```markdown
| 配置 Key | 默认值 | 说明 | 放量策略 |
|----------|--------|------|----------|
| credit.new.flow.enable | false | 新流程开关 | 按比例放量 |
```

**热加载配置初始化检查**：

当变更代码中使用了热加载配置（如 Hippo/Apollo/Nacos 动态配置）时，检查是否在以下**静态初始化上下文**中使用：
- Bean 字段初始化（`private Cache<K,V> cache = buildCache(config.getValue())`）
- 静态初始化块（`static { ... }`）
- `@PostConstruct` 中构建的不可变对象（如 Caffeine Cache 的 `expireAfterWrite`）
- 构造函数中固化配置值到不可变数据结构

**检查规则**：
- [ ] 热加载配置值是否在不可变对象构建时被固化？
- [ ] 如果是，配置变更后能否实时生效？
- [ ] 是否违反项目 CLAUDE.md 中关于配置初始化的明确禁令？

发现此类问题时的严重程度判定：
- 如果项目 CLAUDE.md **明确禁止**该模式 → **Blocker**，修复建议不得包含「接受为已知限制」
- 如果无明确禁令但配置需要动态生效 → **Major**
- 如果配置变更极少且默认值正确 → **Minor**

---

### 每角色输出格式

**Blocker/Major**（必须包含 Fix + Verification）：

```markdown
#### [Severity] Finding Title
- **Evidence**: `ClassName.java:123` — [引用 diff 中的相关代码片段]
- **Problem**: [问题描述]
- **Fix (Executable steps)**:
  1. [具体步骤 1]
  2. [具体步骤 2]
- **Verification**:
  - [运行什么命令]
  - [检查什么结果]
```

**Minor/Nit**（仅需 Evidence + Problem）：

```markdown
#### [Severity] Finding Title
- **Evidence**: `ClassName.java:123` — [引用 diff 中的相关代码片段]
- **Problem**: [问题描述]
- **Suggestion**: [改进建议，一句话]
```

---

## PHASE 4: Problem Verification（问题验证，防误报）

**对 PHASE 3 产出的每个问题进行上下游分析，确认问题真实存在后才纳入最终报告。**

### 验证检查清单

每个问题需验证：

| 验证维度 | 检查内容 |
|----------|----------|
| **上游分析** | 调用方是否已处理该场景？（如：上游已校验参数，下游无需重复校验） |
| **下游分析** | 被调用方是否有保障？（如：框架已保证非空，无需 null 检查） |
| **业务场景** | 该场景在业务上是否真实可达？ |
| **代码上下文** | 是否有注释、配置说明该设计是有意为之？ |

### 验证流程

1. 收集 PHASE 3 所有问题（草稿状态）
2. 对每个问题读取相关文件的上下游调用链
3. 验证通过 → 纳入最终报告
4. 验证不通过（误报）→ 标记为「已排除」并说明原因
5. 已排除问题附在报告末尾的「Excluded Issues」章节

---

## PHASE 5: Consolidation（去重 + Top 10）

1. 跨角色去重（同一问题可能被多个角色发现）
2. 仅保留 **Top 10** 问题，按严重程度排序
3. 输出汇总表：

```markdown
| # | Severity | Area | File | Summary | Executable Fix |
|---|----------|------|------|---------|----------------|
| 1 | 🔴 Blocker | Concurrency | OrderService.java:89 | Race condition in balance deduction | Use atomic UPDATE with WHERE check |
| 2 | 🟠 Major | MQ | ConsumerHandler.java:45 | Missing idempotency on message consume | Add messageId dedup via Redis SETNX |
| ... | | | | | |
```

**Area 分类**：DB / Redis / MQ / Test / Config / Concurrency / Security / Architecture / Reliability / Other

**分类**：
- **MUST FIX before merge**: Blocker + Major
- **CAN DEFER**: Minor + Nit

---

## PHASE 6: Patch & Execution Plan

### 对每个 Blocker/Major 提供

1. **精确位置**：文件/类/方法
2. **分步修复计划**：step-by-step
3. **代码片段**：patch-style diff 或代码示例
4. **验证方式**：具体命令 + 检查内容

**示例**（每个 Fix 按此格式输出）：

    ### Fix #1: [Finding Title]

    **File**: `src/main/java/com/example/OrderService.java`
    **Method**: `deductBalance()`

    **Steps**:
    1. Replace read-then-write pattern with atomic UPDATE
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

    **Verify**: `mvn test -Dtest=OrderServiceTest -pl order-module`

### Coverage Policy（80% 阈值）

**JaCoCo 覆盖率可用时**：
- 覆盖率 < 80%：标记为 Major（关键路径则 Blocker）
- 具体指出变更类/方法中缺少测试的部分
- 提供具体测试用例建议

**JaCoCo 不可用时**：
- 新增/修改的生产逻辑缺少测试：标记为 Major
- 提供具体测试用例建议
- 提供 JaCoCo Maven 插件配置片段：

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

## PHASE 6.5: Fix Quality Review（修复质量自检）

**当 CR 流程包含修复步骤时（即 CR 发现问题后直接修复），对修复代码执行二次审查。**

### 触发条件

仅当 PHASE 6 的修复方案被实际应用到代码中时执行。如果 CR 只输出报告不修复，则跳过此步骤。

### 检查清单

对每个 Blocker/Major 的修复代码，逐项检查：

| 检查维度 | 检查内容 | 反例 |
|----------|----------|------|
| **注释精确性** | 注释是否用确定性语言描述因果关系？ | ❌ "可能是..."、"也许会..."、"应该是..." |
| **注释完整性** | 注释是否说明了 WHY（为什么这样做）而非仅 WHAT（做了什么）？ | ❌ "保存原始值" → ✅ "路由后 nodeId 会被重置，但缓存 Key 使用原始值，两者必须一致" |
| **修复一致性** | 修复是否在所有相关位置都应用了？（如 3 个服务类的相同模式） | ❌ 只改了 1 处，遗漏其他 2 处 |
| **变量命名** | 新增变量名是否准确反映用途？ | ❌ `temp` → ✅ `originalNodeId` |
| **测试适配** | 修复是否需要同步更新测试？测试是否已更新？ | ❌ 新增 Mock 字段但测试未适配 |
| **副作用检查** | 修复是否引入了新的问题？（如变量作用域、线程安全） | ❌ 在错误的作用域定义变量 |

### 输出格式



### 常见修复质量问题

1. **模糊注释**：使用"可能"、"应该"等不确定词汇，实际是确定性的因果关系
2. **作用域错误**：在外层方法定义变量，但实际需要在内层方法使用
3. **遗漏测试更新**：修改了生产代码但忘记适配对应的 Mock/测试
4. **不完整修复**：只修了报告中提到的位置，忽略了相同模式的其他位置

---

## PHASE 7: Final Report

**输出单一 Markdown 文档。**

**文件名格式**：

```
Review-<current-branch>-<YYYYMMDD>-java-db-redis-mq.md
```

**输出路径**（根据上下文选择）：
- 如果在 `~/.claude/specs/{需求名称}/` 工作流中：`~/.claude/specs/{需求名称}/代码开发/review/Review-xxx.md`
- 否则：当前项目根目录下 `Review-xxx.md`

**报告结构**（参考 report-template.md）：

```markdown
# Executive Summary
[一段话总结：变更范围、风险等级、关键发现数量]

# Evidence Summary
[PHASE 2 的证据汇总表]

# Scope & Risk
[PHASE 1 的 Scope & Risk Summary]

# Top Findings (Deduped, Top 10)
[PHASE 4 的去重汇总表，分为 MUST FIX / CAN DEFER]

# Detailed Notes by Role
## Correctness Reviewer
[Role 1 的详细发现]
## Architecture Reviewer
[Role 2 的详细发现]
## Security Reviewer
[Role 3 的详细发现]
## SRE / Reliability Reviewer
[Role 4 的详细��现]

# Patch & Action Plan
[PHASE 5 的修复方案，每个 Blocker/Major 一个子章节]

# Test & Coverage Review
[覆盖率数据 + 缺失测试建议 + JaCoCo 配置（如需）]

# Release Checklist
- [ ] All Blocker issues resolved
- [ ] All Major issues resolved or explicitly accepted
- [ ] Tests pass (mvn test)
- [ ] Coverage >= 80% (or risk accepted)
- [ ] DB DDL executed in correct order
- [ ] Config defaults verified (feature flags OFF)
- [ ] Rollback plan documented
- [ ] Monitoring/alerting configured

# Appendix
## Excluded Issues (False Positives)
[已排除的误报问题及原因]
## SQL Change List
[SQL 变更清单]
## Config Change List
[配置变更清单]
```

---

## 全局规则

1. **优先自动采集证据**，不要求用户粘贴
2. **Major/Blocker 必须提供可执行修复方案**，不给模糊建议
3. **最终汇总最多 10 条**，去重排序
4. **输出干净的可复制粘贴 Markdown**
5. **问题必须引用证据**（文件/行号/diff 片段）
6. **问题验证防误报**：上下游分析后才纳入报告
7. **只审查变更代码**：不审查未变更的代码，但需读取上下文理解影响
8. **CLAUDE.md 约束优先**：当发现的问题违反项目 CLAUDE.md 中的明确禁令时，修复建议**不得**包含「接受为已知限制」或「记录后跳过」。CLAUDE.md 中的明确禁令等同于 Blocker 级别约束，必须要求代码修复。

---

## 自动：功能完整性检查

**如果 Step 0.5 探测到 req-spec.md**，自动执行功能覆盖度对比（无需用户手动提供）：

```markdown
| 需求功能点 | 实现状态 | 相关文件 |
|------------|----------|----------|
| 用户授信额度计算 | ✅ 已实现 | CreditService.java |
| 授信结果通知 | ⚠️ 部分实现 | NotifyService.java（缺失失败通知）|
| 额度冻结功能 | ❌ 未实现 | - |
```

如果 Step 0.5 未探测到 req-spec.md，跳过此步骤。用户也可在对话中主动提供需求文档路径或 TAPD 链接来触发。

---

## 与其他 Skill 的关系

| Skill | 关系 |
|-------|------|
| **requirement-clarifier** | req-spec.md 自动探测，用于功能完整性检查 |
| **spec-generator** | tech-spec.md 自动探测，用于架构审查基准对比 |
| **tech-review** | 方案评审在前，代码评审在后 |
| **test-verify** | 测试验证在前，代码评审在后；test-report 可作为评审参考 |
| **code-dev** | 开发完成后经测试验证再调用代码评审 |

---

## 用户指令

| 指令 | 说明 |
|------|------|
| `/cr-stop` | 终止评审 |
| `/cr-status` | 查看当前评审进度 |
| `/cr-rerun <phase>` | 重新执行指定阶段 |
