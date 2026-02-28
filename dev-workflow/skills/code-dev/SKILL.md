---
name: code-dev
description: 基于开发计划的代码开发工作流。读取 dev-plan.md 按任务逐步开发，内置核心代码规范检查，支持 Claude 主 Agent / Codex / Claude 子代理三种后端。使用条件：用户要求开发代码、实现功能、或有 dev-plan.md 需要执行时触发。
---

# 代码开发系统

## 快速开始

**输入方式**：
- 引用开发计划：`@~/.claude/specs/{需求名称}/代码开发/dev-plan.md`
- 直接提供需求描述（自动生成开发计划后再开发）

**输出**：代码 + 单元测试 + 编译验证

## 目录约定

> **重要**：`.claude/specs/` 是**用户级目录**，位于 `~/.claude/specs/`（即 `/home/{user}/.claude/specs/`），**不是**当前项目目录下的 `.claude/specs/`。
>
> 所有 skill 产出的文档统一存放在此目录下，按需求名称组织。

---

## 核心原则：代码质量优先

### 写代码前必须确认

1. **有开发计划**：没有 dev-plan.md 不写代码
2. **理解现有代码**：读懂再改，不猜测
3. **遵循现有模式**：复用项目中已有的模式和工具类
4. **最小改动**：只改必要的，不顺手重构

### 代码质量标准

| 标准 | 要求 |
|------|------|
| **编译** | 必须通过 `mvn compile` |
| **测试** | 覆盖率 ≥90%，TestNG + Mockito |
| **规范** | 内置核心规范检查（见下文） |
| **简洁** | 不过度工程，不冗余抽象 |

---

## 工作流概览

```
dev-plan.md → 对齐确认 → 逐任务开发 → 编译验证 → 完成总结
                                ↓
                          每个任务：
                          1. 读懂现有代码
                          2. 写代码（遵循规范）
                          3. 自检（内置规范）
                          4. 可选：写单元测试
```

---

## Step 0: 开发计划对齐

**必须有开发计划**。如果没有：
- 引导用户使用 spec-generator Skill 生成
- 或基于用户描述自动生成简易开发计划

**对齐确认**：

使用 `AskUserQuestion` 确认：

```
Question: "开发计划确认：

已读取 dev-plan.md，包含以下任务：
1. [task-1]: [描述]
2. [task-2]: [描述]
3. [task-3]: [描述]

是否按此计划开发？"

Options:
1. label: "确认，开始开发"
2. label: "需要调整计划"
```

---

## Step 1: 开发配置选择

### 1.1 代码编写方式

使用 `AskUserQuestion` 询问：

```
Question: "选择代码编写方式：

| 方式 | 说明 | 适用场景 |
|------|------|----------|
| Claude 主 Agent | 直接在当前会话中编写 | 简单任务、需要交互 |
| Codex 子代理 | 调用 codeagent --backend codex | 独立任务、批量开发 |
| Claude 子代理 | 调用 codeagent --backend claude | 复杂任务、需要推理 |"

Options:
1. label: "Claude 主 Agent（推荐）"
2. label: "Codex 子代理"
3. label: "Claude 子代理"
```

### 1.2 单元测试时机

使用 `AskUserQuestion` 询问：

```
Question: "选择单元测试编写时机："

Options:
1. label: "每个任务完成后立即写（推荐）"
2. label: "所有任务完成后统一写"
```

---

## Step 2: 逐任务开发

### 开发前：读懂现有代码

**每个任务开始前必须**：
1. 读取 File Scope 中列出的所有文件
2. 识别现有模式（命名、分层、异常处理）
3. 确认修改点和影响范围

### 开发中：写代码

**代码编写原则**：

```
1. 最小改动原则
   - 只改 dev-plan 中要求的内容
   - 不顺手重构、不添加额外功能
   - 不修改不相关的代码

2. 复用优先原则
   - 优先使用项目中已有的工具类
   - 优先复用已有的设计模式
   - 三次法则：相同逻辑出现三次才抽象

3. 简洁明了原则
   - 方法长度 ≤50 行
   - 圈复杂度 ≤10
   - 命名清晰，不需要注释解释
   - 避免深层嵌套（≤3 层）

4. 防御性编程原则
   - 系统边界做参数校验
   - 内部方法信任调用方，不重复校验
   - 异常处理：捕获具体异常，不吞异常
```

### 开发后：自检

**每个任务完成后，执行内置规范自检**（参考 coding-standards.md）：

```
自检清单：
[ ] 编译通过
[ ] 命名规范（类名 UpperCamelCase，方法名 lowerCamelCase）
[ ] 无通配符 import
[ ] 异常处理完整（不吞异常、不空 catch）
[ ] 幂等设计（写操作是否幂等）
[ ] 埋点完整（入口/决策/异常）
[ ] 日志规范（关键节点有日志，不打印敏感信息）
```

---

## Step 3: 并发执行规则

**无依赖任务必须并行执行**：

```
规则：
1. 分析 dev-plan.md 中的任务依赖关系
2. 无依赖的任务必须在同一消息中发送多个工具调用
3. 最大并发数：3 个任务
4. 有依赖的任务必须等前置任务完成

示例：
task-1（无依赖）  ──┐
task-2（无依赖）  ──┼──▶ 并行执行
task-3（依赖 task-1）──▶ 等 task-1 完成后执行
```

### 子代理调用方式

**Codex 子代理**：
```bash
codeagent-wrapper --backend codex \
  --timeout 7200000 \
  --prompt "基于以下任务描述开发代码：[任务描述]" \
  @file1.java @file2.java
```

**Claude 子代理**：
```bash
codeagent-wrapper --backend claude \
  --timeout 7200000 \
  --prompt "基于以下任务描述开发代码：[任务描述]" \
  @file1.java @file2.java
```

---

## Step 4: 单元测试

### TestNG + Mockito 规范

```java
// 测试类命名：{被测类名}Test
public class XxxServiceTest {

    @Mock
    private YyyDao yyyDao;

    @InjectMocks
    private XxxService xxxService;

    @BeforeMethod
    public void setUp() {
        MockitoAnnotations.initMocks(this);
    }

    // 测试方法命名：test_{场景}_{预期结果}
    @Test
    public void test_normalCase_success() {
        // Given
        when(yyyDao.query(anyLong())).thenReturn(mockData);

        // When
        Result result = xxxService.process(input);

        // Then
        Assert.assertEquals(result.getCode(), "0000");
        verify(yyyDao, times(1)).query(anyLong());
    }
}
```

### 测试覆盖要求

| 场景 | 必须覆盖 |
|------|----------|
| 正常流程 | ✅ |
| 边界条件 | ✅ |
| 异常处理 | ✅ |
| 空值/null | ✅ |
| 并发场景 | 视情况 |

### 测试命令

```bash
# 运行指定测试类
mvn test -Dtest=XxxServiceTest -pl module-name

# 运行测试套件
mvn -pl module-name test -DsuiteXmlFile=src/test/resources/testng_ut_checkin.xml
```

---

## Step 5: 编译验证与总结

### 编译验证

```bash
# 编译所有模块
mvn compile -DskipTests

# 如果编译失败，自动修复后重试（最多 3 次）
```

### 完成总结

```markdown
## 开发完成总结

### 已完成任务
| Task | 状态 | 新增/修改文件 | 测试覆盖 |
|------|------|---------------|----------|
| task-1 | ✅ | 3 个文件 | 95% |
| task-2 | ✅ | 2 个文件 | 92% |

### 编译状态
- mvn compile: ✅ 通过

### 后续建议
- 建议执行 dev-cr 进行代码审查
```

---

## 内置核心规范（从 dev-cr 提取）

开发过程中自动遵循以下核心规范，减少后续 CR 问题：

### P0 级规范（必须遵守）

| 规范 | 说明 | 检查方式 |
|------|------|----------|
| **幂等设计** | 写操作必须幂等 | 检查是否有幂等 Key |
| **异常处理** | 不吞异常、不空 catch | 代码扫描 |
| **并发安全** | 共享状态必须加锁 | 检查共享变量 |
| **数据校验** | 系统边界做参数校验 | 检查入口方法 |

### P1 级规范（强烈建议）

| 规范 | 说明 | 检查方式 |
|------|------|----------|
| **埋点** | 入口/决策/异常三类埋点 | 检查关键方法 |
| **日志** | 关键节点有日志 | 检查核心流程 |
| **状态机** | 状态流转完整 | 检查状态枚举 |
| **事务边界** | 事务范围最小化 | 检查 @Transactional |

### 过度工程检测

**开发时自动检测以下情况**：

| ❌ 过度工程 | ✅ 恰当实现 |
|-------------|-------------|
| 为假设需求预留扩展 | 只实现当前需求 |
| 一次性逻辑抽象成工具类 | 内联实现 |
| 添加未请求的"优化" | 按需实现 |
| 过早抽象（仅一处使用） | 必要时再抽象 |
| 内部方法重复校验参数 | 信任调用方 |

---

## 错误处理

### 编译失败

```
1. 分析错误信息
2. 定位问题文件和行号
3. 修复后重新编译
4. 最多重试 3 次
5. 仍然失败则报告用户
```

### 测试失败

```
1. 分析失败原因（断言错误 / Mock 配置 / 环境问题）
2. 修复测试代码或业务代码
3. 重新运行测试
4. 仍然失败则报告用户
```

### 子代理执行失败

```
1. 检查 codeagent-wrapper 输出
2. 如果是超时：增加 timeout 重试
3. 如果是代码错误：切换到 Claude 主 Agent 手动修复
4. 如果是依赖冲突：序列化执行
```

---

## 用户指令

| 指令 | 说明 |
|------|------|
| `/dev-stop` | 终止开发 |
| `/dev-status` | 查看当前进度 |
| `/dev-skip <task-id>` | 跳过某个任务 |
| `/dev-retry <task-id>` | 重试某个任务 |

---

## 与其他 Skill 的关系

| Skill | 关系 | 触发方式 |
|-------|------|----------|
| **requirement-clarifier** | req-spec.md 是最上游输入 | 间接关联 |
| **spec-generator** | dev-plan.md 是直接输入 | 用户提供路径 |
| **tech-review** | 评审通过后才开始开发 | 前置条件 |
| **test-verify** | 开发完成后调用测试验证 | 建议用户调用 |
| **dev-cr** | 测试验证通过后调用代码评审 | 间接关联（经 test-verify） |

---

## 输出文件位置

```
~/.claude/specs/{需求名称}/
├── 需求文档/
│   └── req-spec.md
├── 技术方案/
│   ├── tech-spec.md
│   └── review/
│       └── Review-vX.md
├── 代码开发/
│   ├── dev-plan.md          ← 输入
│   └── review/
│       └── Review-xxx.md    ← dev-cr 产出
└── 测试验证/
    └── test-report-YYYYMMDD.md  ← test-verify 产出

项目代码目录/
├── src/main/java/...        ← 代码输出
└── src/test/java/...        ← 测试输出
```
