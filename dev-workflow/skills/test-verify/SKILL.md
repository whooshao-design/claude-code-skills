---
name: test-verify
description: 代码开发后的测试验证系统。自动探测测试框架，执行单元测试/集成测试，分析失败并尝试修复，生成缺失测试用例，输出覆盖率分析报告。目标技术栈：Java + Maven + TestNG/JUnit + Mockito。使用条件：代码开发完成后需要系统性测试验证时触发。
---

# 测试验证工作流（test-verify）

## 工作流概览

```
Step 0: 环境探测
    ↓
Step 1: 单元测试执行
    ↓
Step 2: 失败修复循环（≤3 次）
    ↓
Step 3: 测试缺口分析 + 用例生成（单测 + 集成测试）
    ↓
Step 3.5: 全量回归验证
    ↓
Step 4: 集成测试验证
    ↓
Step 5: 覆盖率分析
    ↓
Step 6: 输出测试报告
```

---

## Step 0: 环境探测（自动）

**无需用户交互**，自动完成以下探测：

### 0.1 测试框架探测

扫描项目 pom.xml，识别测试依赖：

```bash
# 探测测试框架
grep -r 'testng\|junit\|mockito\|spring-test' pom.xml */pom.xml 2>/dev/null
```

支持的框架组合：
- TestNG + Mockito（主要支持）
- JUnit 4/5 + Mockito
- Spring Test

### 0.2 测试 Suite 探测

```bash
# 查找 TestNG XML 配置
find . -name "testng*.xml" -path "*/test/resources/*" -type f 2>/dev/null

# 查找 JUnit Suite
find . -name "*Suite*.java" -path "*/test/*" -type f 2>/dev/null
```

Suite 执行优先级：
1. `testng_ut_checkin.xml` — 特性分支级别（Step 1 使用）
2. `testng_ut_pre_integration.xml` — 集成前验证（Step 4 使用）
3. `testng_ut_post_integration.xml` — 集成后验证（Step 4 使用）

### 0.3 覆盖率工具探测

```bash
# 检查 JaCoCo 配置
grep -r 'jacoco-maven-plugin' pom.xml */pom.xml 2>/dev/null
```

### 0.4 变更范围探测

```bash
# 获取变更文件
git diff --name-only HEAD~1...HEAD -- '*.java' 2>/dev/null

# 区分生产代码和测试代码
git diff --name-only HEAD~1...HEAD -- '*.java' | grep -v 'Test.java' | grep 'src/main'
git diff --name-only HEAD~1...HEAD -- '*.java' | grep 'Test.java'
```

### 0.5 上下文文档探测

与 dev-cr 的 Step 0.5 一致，探测 `~/.claude/specs/` 下的 dev-plan.md。

### 探测结果输出

```markdown
| 探测项 | 状态 | 详情 |
|--------|------|------|
| 测试框架 | TestNG 7.4.0 + Mockito 4.3.1 | pom.xml |
| TestNG Suite | FOUND | checkin / pre_integration / post_integration |
| JaCoCo | NOT_FOUND / FOUND | 配置状态 |
| dev-plan.md | FOUND / NOT_FOUND | 路径 |
| 变更文件 | N files | 生产代码 X 个，测试代码 Y 个 |
| 模块 | core / impl | 涉及的模块列表 |
```

### 0.6 测试分类（单测 vs 集成测试）

对探测到的测试类自动分类：

| 分类 | 判定规则 | 典型特征 |
|------|----------|----------|
| **单元测试** | 使用 `@Mock` / `@InjectMocks`，不启动 Spring 容器 | Mockito 驱动，毫秒级执行 |
| **集成测试** | 继承 `AbstractTestNGSpringContextTests` 或使用 `@SpringBootTest`、`@ContextConfiguration` | `@Autowired` 真实 Bean，需要外部依赖 |

分类方法：

```bash
# 识别集成测试：查找继承 Spring 测试基类的测试
grep -rl 'AbstractTestNGSpringContextTests\|@SpringBootTest\|@ContextConfiguration' \
  --include='*Test.java' src/test/ 2>/dev/null

# 识别单元测试：使用 Mockito 且不继承 Spring 基类的测试
grep -rl '@Mock\|@InjectMocks\|MockitoAnnotations' \
  --include='*Test.java' src/test/ 2>/dev/null
```

分类结果记录：

```markdown
| 测试类 | 分类 | 判定依据 |
|--------|------|----------|
| XxxServiceTest | 单元测试 | @Mock + @InjectMocks |
| YyyServiceTest | 集成测试 | extends BaseTest (AbstractTestNGSpringContextTests) |
```

**重要**：后续统计和验证结论中，单测和集成测试分开计数。

---

## Step 1: 单元测试执行

### 1.1 运行 checkin 级别测试

按探测到的模块逐一运行：

```bash
# 示例：运行 core 模块 checkin suite
mvn -pl {module-name} test \
  -DsuiteXmlFile=src/test/resources/testng_ut_checkin.xml 2>&1
```

**绝对原则**：自动执行命令采集结果，不要求用户粘贴输出。

### 1.2 解析测试结果

解析 `target/surefire-reports/` 下的 XML 报告：

```bash
# 查找 surefire 报告
find . -path "*/surefire-reports/*.xml" -type f 2>/dev/null
```

提取：
- 总测试数、通过数、失败数、跳过数
- 失败用例的类名、方法名、错误信息、堆栈

### 1.3 结果记录

```markdown
| 模块 | Suite | 通过 | 失败 | 跳过 | 耗时 |
|------|-------|------|------|------|------|
| core | checkin | XX | X | X | Xs |
| impl | checkin | XX | X | X | Xs |
```

---

## Step 2: 失败修复循环

**前提**：Step 1 存在失败用例时才执行。全部通过则跳过。

### 熔断机制

为避免"修了 A 坏了 B → 修了 B 坏了 A"的死循环，设置多层熔断：

| 熔断规则 | 阈值 | 触发后行为 |
|----------|------|-----------|
| 单用例修复上限 | 同一用例修复 2 次仍失败 | 标记 UNRESOLVED，不再尝试 |
| 全局迭代上限 | 总迭代 3 次 | 停止修复，所有剩余失败标记 UNRESOLVED |
| 回归检测 | 修复后新增失败数 ≥ 修复成功数 | 回滚本次修复，标记 UNRESOLVED |
| 重复错误检测 | 连续 2 次迭代失败数未减少 | 停止修复，判定为非测试问题 |

### 修复策略（按优先级）

| 优先级 | 失败类型 | 修复方式 | 自动修复？ |
|--------|----------|----------|-----------|
| 1 | Mock 配置错误（when/thenReturn 不匹配） | 更新 Mock 返回值 | 是 |
| 2 | 断言值不匹配（预期值过时） | 更新断言预期值 | 是 |
| 3 | 编译错误（接口变更导致测试不兼容） | 更新方法签名/参数 | 是 |
| 4 | 业务逻辑 bug | 标记 UNRESOLVED | 否 |
| 5 | 环境/依赖问题（连接超时、配置缺失） | 标记 ENV_ISSUE | 否 |

### 修复流程

```
Step 1 失败用例列表
    ↓
记录初始失败快照：{用例名: 错误信息}
    ↓
┌─ 迭代开始（≤3 次）─────────────────────┐
│                                         │
│  逐个分析失败原因                        │
│      ↓                                  │
│  优先级 1-3 → 修复测试代码               │
│  优先级 4-5 → 标记 UNRESOLVED/ENV_ISSUE  │
│      ↓                                  │
│  重新运行全部失败用例                     │
│      ↓                                  │
│  ── 熔断检查 ──                          │
│  ✓ 同一用例第 2 次失败？→ 标记 UNRESOLVED │
│  ✓ 新增失败 ≥ 修复成功？→ 回滚，停止      │
│  ✓ 失败数未减少？→ 连续 2 次则停止        │
│      ↓                                  │
│  仍有可修复的失败 → 下一次迭代            │
│  全部通过或全部 UNRESOLVED → 退出循环     │
│                                         │
└─────────────────────────────────────────┘
    ↓
输出修复摘要，进入 Step 3
```

### 修复记录

```markdown
| 迭代 | 修复用例 | 失败类型 | 修复内容 | 结果 |
|------|----------|----------|----------|------|
| 1 | XxxTest.test_a | Mock 配置 | 更新 when().thenReturn() | FIXED |
| 1 | YyyTest.test_b | 业务 bug | - | UNRESOLVED |
| 2 | ZzzTest.test_c | 断言值 | 更新 assertEquals | FIXED |
```

---

## Step 3: 测试缺口分析 + 用例生成

### 3.1 缺口分析

对 Step 0 探测到的变更生产类，检查是否有对应测试：

```bash
# 对每个变更的生产类，查找对应测试类
# 例如 XxxService.java → XxxServiceTest.java
find . -name "{ClassName}Test.java" -path "*/test/*" -type f 2>/dev/null
```

分析维度：
- 变更类是否有对应 Test 类
- 变更方法是否有对应测试方法
- 现有测试是否覆盖了新增/修改的分支
- 现有测试是单元测试还是集成测试（基于 Step 0.6 分类结果）

### 3.2 生成确认

使用 `AskUserQuestion` 确认：

```
Question: "以下变更类缺少测试覆盖，是否自动生成？"

| 类名 | 变更方法 | 现有测试 | 建议生成类型 | 建议新增 |
|------|----------|----------|-------------|----------|
| XxxService | methodA, methodB | 无 | 单元测试 | 正常/异常/边界/null |
| YyyLogic | methodC | 部分(单测) | 单元测试 | 异常分支 |
| ZzzHandler | handleRequest | 无 | 集成测试 | 端到端流程 |

Options:
1. "全部生成（推荐）"
2. "只生成单元测试"
3. "选择性生成"
4. "跳过，不生成"
```

### 3.3 生成类型判定

根据被测类的特征决定生成单元测试还是集成测试：

| 被测类特征 | 生成类型 | 原因 |
|-----------|----------|------|
| 纯逻辑类（无外部依赖或依赖可 Mock） | 单元测试 | Mockito 可完全隔离 |
| Service 层（依赖注入其他 Service） | 单元测试 | Mock 依赖即可 |
| 涉及 DB/Redis/MQ 的复杂交互 | 集成测试 | 需要真实容器验证交互 |
| 入口类（Dubbo 接口实现） | 集成测试 | 需要验证完整调用链 |

### 3.4 单元测试生成规范

**遵循项目 Mockito 模式**：

```java
@Slf4j
public class {ClassName}Test {

    @InjectMocks
    private {ClassName} target;

    @Mock
    private {DependencyType} dependency;

    @BeforeMethod
    public void setUp() {
        MockitoAnnotations.initMocks(this);
    }

    @Test
    public void test_{场景描述}_{预期结果}() {
        // Given
        {准备测试数据和 Mock}

        // When
        {调用被测方法}

        // Then
        {断言验证}
    }
}
```

覆盖场景：
- 正常流程（happy path）
- 边界条件（空集合、最大值、最小值）
- 异常处理（抛出异常、返回 null）
- null 值输入

### 3.5 集成测试生成规范

**遵循项目 BaseTest 模式**（继承 `AbstractTestNGSpringContextTests`）：

```java
@Slf4j
public class {ClassName}Test extends BaseTest {

    @Autowired
    private {ClassName} target;

    @Test
    public void test_{场景描述}_{预期结果}() {
        // Given
        {准备请求对象}

        // When
        {result} = target.{method}({request});

        // Then
        assertNotNull(result);
        {断言验证业务结果}
    }
}
```

集成测试注意事项：
- 必须有断言（不能只调用不验证，避免出现无断言的冒烟测试）
- 测试数据使用可控的固定值，不依赖特定环境数据
- 如果运行失败且错误为连接超时/配置缺失，标记 ENV_ISSUE 而非 UNRESOLVED

### 3.6 生成后验证

生成的测试必须运行通过：

```bash
# 单元测试：直接运行
mvn -pl {module} test -Dtest={NewTestClass} 2>&1

# 集成测试：通过 suite 运行（需要 Spring 容器）
mvn -pl {module} test -DsuiteXmlFile=src/test/resources/testng_ut_checkin.xml \
  -Dtest={NewTestClass} 2>&1
```

生成验证的熔断规则：

| 规则 | 阈值 | 触发后行为 |
|------|------|-----------|
| 单个测试类修复上限 | 2 次 | 放弃该测试类，从项目中删除，标记 GEN_FAILED |
| 同一错误重复出现 | 连续 2 次相同错误信息 | 判定为理解偏差，放弃并删除 |
| 生成总失败上限 | 累计 3 个测试类生成失败 | 停止后续生成，仅保留已成功的 |
| 集成测试环境不可用 | 首个集成测试因环境问题失败 | 跳过所有集成测试生成，仅保留单元测试 |

**关键原则**：生成失败的测试代码必须从项目中删除，不能留下不可编译或不可运行的测试文件。

---

## Step 3.5: 全量回归验证

**前提**：Step 2 或 Step 3 修改/新增了测试代码时才执行。无变更则跳过。

### 目的

确保 Step 2 的修复和 Step 3 的新增没有引入回归问题。

### 执行

重新运行 Step 1 的 checkin suite（全量）：

```bash
mvn -pl {module} test \
  -DsuiteXmlFile=src/test/resources/testng_ut_checkin.xml 2>&1
```

### 结果处理

| 情况 | 处理 |
|------|------|
| 全部通过 | 进入 Step 4 |
| 出现新的失败（Step 1 没有的） | 回归问题，回滚最近的修改，标记 REGRESSION |
| Step 1 已有的失败仍在 | 正常，已在 Step 2 标记为 UNRESOLVED |

**不再进入修复循环**。回归验证只做检测，不做修复。发现回归就回滚，避免无限循环。

---

## Step 4: 集成测试验证

### 4.1 运行 pre_integration suite

```bash
mvn -pl {module} test \
  -DsuiteXmlFile=src/test/resources/testng_ut_pre_integration.xml 2>&1
```

### 4.2 运行 post_integration suite

仅在 pre_integration 通过后执行：

```bash
mvn -pl {module} test \
  -DsuiteXmlFile=src/test/resources/testng_ut_post_integration.xml 2>&1
```

### 4.3 无集成测试 suite 时

如果项目没有 pre/post_integration suite，跳过此步骤，在报告中标记 `SKIPPED`。

### 结果记录

```markdown
| 模块 | Suite | 通过 | 失败 | 跳过 | 状态 |
|------|-------|------|------|------|------|
| core | pre_integration | XX | X | X | PASS/FAIL |
| impl | post_integration | XX | X | X | PASS/FAIL/SKIPPED |
```

---

## Step 5: 覆盖率分析

### 5.1 JaCoCo 已配置

```bash
mvn test jacoco:report 2>&1
find . -path "*/site/jacoco/jacoco.csv" -type f 2>/dev/null
```

解析 CSV，输出覆盖率数据：

```markdown
| 模块 | 类覆盖率 | 方法覆盖率 | 行覆盖率 | 分支覆盖率 |
|------|----------|-----------|----------|-----------|
| core | XX% | XX% | XX% | XX% |
```

### 5.2 JaCoCo 未配置（静态分析替代）

基于 git diff 做变更方法 vs 已有测试的对照分析：

```markdown
| 模块 | 变更类 | 变更方法 | 测试覆盖 | 备注 |
|------|--------|----------|----------|------|
| core | XxxService | methodA | COVERED | XxxServiceTest.test_xxx |
| core | YyyLogic | methodB | MISSING | 建议补充 |
| impl | ZzzHandler | methodC | PARTIAL | 缺少异常分支 |
```

### 5.3 JaCoCo 配置建议

未配置时，在报告中提供配置片段：

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

## Step 6: 输出测试报告

### 输出路径

- 工作流模式：`~/.claude/specs/{需求名称}/测试验证/test-report-{YYYYMMDD}.md`
- 独立模式：项目根目录 `test-report-{YYYYMMDD}.md`

### 报告结构

参考 `references/report-template.md` 模板。

### 验证标准体系

验证结论基于 3 个维度综合判定：

#### 维度 1：测试执行结果

| 检查项 | PASS 条件 | FAIL 条件 |
|--------|-----------|-----------|
| 单元测试 | 全部通过（允许修复后通过） | 存在 UNRESOLVED 失败 |
| 集成测试 | 全部通过或主动 SKIP | 存在 UNRESOLVED 失败 |

#### 维度 2：变更代码测试覆盖

对 git diff 中每个变更的生产��，检查：

| 检查项 | 说明 |
|--------|------|
| 测试类存在性 | 变更类 `XxxService.java` 必须有对应 `XxxServiceTest.java` |
| 变更方法覆盖 | 变更/新增的 public 方法必须有对应测试方法 |

���盖检查结果：

```markdown
| 变更类 | 测试类 | 变更方法 | 已覆盖 | 未覆盖 | 覆盖率 |
|--------|--------|----------|--------|--------|--------|
| XxxService | XxxServiceTest | 3 | 2 | 1 | 67% |
| YyyLogic | (无) | 2 | 0 | 2 | 0% |
```

#### 维度 3：覆盖率阈值门控

| 指标 | 阈值 | 说明 |
|------|------|------|
| 变更方法覆盖率 | ≥ 80% | 变更的 public 方法中，有对应测试方法的比例 |
| 变更类覆盖率 | 100% | 每个变更的生产类必须有对应测试类 |
| JaCoCo 行覆盖率 | ≥ 80%（如已配置） | 变更代码的行覆盖率 |
| JaCoCo 分支覆盖率 | ≥ 70%（如已配置） | 变更代码的分支覆盖率 |

> JaCoCo 未配置时，仅使用变更方法覆盖率和变更类覆盖率作为门控指标。

### 验证结论

综合 3 个维度，得出最终结论：

| 结论 | 条件 |
|------|------|
| **PASS** | 测试全部通过 + 变更类覆盖率 100% + 变更方法覆盖率 ≥ 80% |
| **PASS_WITH_WARNINGS** | 测试全部通过，但变更方法覆盖率 < 80%（或 JaCoCo 指标低于阈值） |
| **FAIL** | 存在 UNRESOLVED 失败用例，或有变更类完全无测试覆盖（0%） |

验证结论摘要格式：

```markdown
## 验证结论：{PASS / PASS_WITH_WARNINGS / FAIL}

### 各维度评分

| 维度 | 结果 | 详情 |
|------|------|------|
| 测试执行 | PASS / FAIL | 单测 XX/XX 通过，集成 XX/XX 通过 |
| 变更覆盖 | PASS / WARN / FAIL | X/Y 变更类有测试，方法覆盖率 XX% |
| 覆盖率阈值 | PASS / WARN / N/A | 行 XX%，分支 XX% / JaCoCo 未配置 |

### 未通过项（如有）

| 变更类 | 问题 | 建议 |
|--------|------|------|
| YyyLogic | 无对应测试类 | 需新建 YyyLogicTest |
| XxxService.methodC | 无对应测试方法 | 需补充测试 |
```

### 后续建议

报告末尾自动建议：
- FAIL → 列出具体需要补充的测试类/方法，建议修复后重新运行 test-verify
- PASS_WITH_WARNINGS → 列出覆盖率不足的方法，建议补充但不阻塞
- PASS → 建议执行 `dev-cr` 进行代码评审

---

## 用户指令

| 指令 | 说明 |
|------|------|
| `/test-stop` | 终止测试验证 |
| `/test-status` | 查看当前测试进度 |
| `/test-skip <step>` | 跳过某个步骤（如 coverage、integration） |
| `/test-rerun` | 重新执行全部测试 |

---

## 输出位置

```
~/.claude/specs/{需求名称}/
├── 需求文档/
│   └── req-spec.md          ← 需求澄清产出
├── 技术方案/
│   ├── tech-spec.md         ← 方案设计产出
│   └── review/
│       └── Review-vX.md     ← 方案评审产出
├── 代码开发/
│   ├── dev-plan.md          ← 开发计划产出
│   └── review/
│       └── Review-xxx.md    ← 代码评审产出
└── 测试验证/                  ← 测试验证产出
    └── test-report-YYYYMMDD.md
```

---

## 与其他 Skill 的关系

| Skill | 关系 | 触发方式 |
|-------|------|----------|
| **requirement-clarifier** | req-spec.md 中的验收标准作为测试依据 | 间接关联 |
| **spec-generator** | tech-spec.md 中的测试策略作为参考 | 间接关联 |
| **tech-review** | 评审通过的方案指导测试范围 | 间接关联 |
| **code-dev** | 开发完成后调用测试验证，dev-plan.md 是直接输入 | 上游，code-dev 完成后建议调用 |
| **dev-cr** | 测试验证通过后调用代码评审 | 下游，test-verify 完成后建议调用 |
