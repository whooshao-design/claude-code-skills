---
name: test-verify
description: 代码开发后的单元测试验证系统。覆盖率驱动的闭环验证：执行单元测试→修复失败→采集JaCoCo覆盖率→门控检查→补充用例，循环直到变更代码行覆盖率≥80%。目标技术栈：Java + Maven + TestNG/JUnit + Mockito。使用条件：代码开发完成后需要系统性测试验证时触发。
version: 2.5.0
---
> **Skill**: test-verify | **Version**: 2.5.0


# 测试验证工作流（test-verify）

## 工作流概览

```
Step 0: 环境探测 + JaCoCo 准备
    ↓
┌─ 覆盖率驱动循环（≤3 轮）──────────────────────────────┐
│                                                        │
│  Step 1: 执行单元测试                                   │
│      ↓ 有失败                                          │
│  Step 2: 修复失败 → 回到 Step 1（内循环 ≤3 次）         │
│      ↓ 全部通过                                        │
│  Step 3: 采集 JaCoCo 覆盖率（变更代码）                  │
│  Step 4: 覆盖率门控（行覆盖率 ≥80%？）                   │
│      ├─ YES → 退出循环                                  │
│      └─ NO  → Step 5                                   │
│  Step 5: 针对未覆盖行生成测试用例 → 回到 Step 1          │
│                                                        │
└────────────────────────────────────────────────────────┘
    ↓
Step 6: 输出测试报告
```

### 双层循环说明

| 循环 | 范围 | 目的 | 上限 |
|------|------|------|------|
| **内循环** | Step 1 ↔ Step 2 | 修复测试失败，确保全部通过 | 3 次 |
| **外循环** | Step 1 → 2 → 3 → 4 → 5 → Step 1 | 提升覆盖率至 ≥80% | 3 轮 |

---

## Step 0: 环境探测 + JaCoCo 准备（自动）

**无需用户交互**，自动完成以下探测和准备：

### 0.1 测试框架探测

扫描项目 pom.xml，识别测试依赖：

```bash
# 探测测试框架
grep -r "testng\|junit\|mockito" pom.xml */pom.xml 2>/dev/null
```

支持的框架组合：
- TestNG + Mockito（主要支持）
- JUnit 4/5 + Mockito

### 0.2 测试 Suite 探测

```bash
# 查找 TestNG XML 配置
find . -name "testng*.xml" -path "*/test/resources/*" -type f 2>/dev/null

# 查找 JUnit Suite
find . -name "*Suite*.java" -path "*/test/*" -type f 2>/dev/null
```

Suite 执行优先级：
1. `testng_ut_checkin.xml` — 特性分支级别（Step 1 使用）

### 0.3 覆盖率工具探测 + JaCoCo 准备

```bash
# 检查 JaCoCo 配置
grep -r "jacoco-maven-plugin" pom.xml */pom.xml 2>/dev/null
```

**JaCoCo 状态判定**：

| 状态 | 条件 | 后续处理 |
|------|------|----------|
| CONFIGURED | pom.xml 中已有 jacoco-maven-plugin | 直接使用，无需注入 |
| NOT_CONFIGURED | 未找到 JaCoCo 配置 | 执行临时注入（0.3.1） |

#### 0.3.1 跨模块结构探测（关键）

**问题背景**：标准 JaCoCo 只分析当前模块 `target/classes/` 下的类。如果测试代码在 `impl` 模块，生产代码在 `core/kernel` 模块，运行 `mvn -pl impl test jacoco:report` 只会报告 impl 模块自身的类，变更的生产类不会出现在报告中。

**探测跨模块结构**：

```bash
# 1. 获取变更的生产代码所在模块
git diff --name-only HEAD~1...HEAD -- "*.java" | grep "src/main" | sed 's|/src/main.*||' | sort -u

# 2. 获取测试代码所在模块
git diff --name-only HEAD~1...HEAD -- "*.java" | grep "src/test" | sed 's|/src/test.*||' | sort -u
find . -path "*/src/test/java/*Test.java" -type f | sed 's|/src/test.*||' | sort -u

# 3. 检查是否分离
# 如果生产模块 ≠ 测试模块，则为跨模块结构
```

**跨模块结构判定**：

| 结构类型 | 条件 | 覆盖率采集方式 |
|----------|------|----------------|
| 单模块 | 生产代码和测试代码在同一模块 | `mvn -pl {module} test jacoco:report` |
| 跨模块 | 生产代码在 core，测试代码在 impl | 在 **根目录** 运行 `mvn test jacoco:report-aggregate` |

**跨模块时的处理原则**：
- **不在子模块单独运行 JaCoCo**，因为报告会缺失依赖模块的覆盖率
- 必须在根目录运行，使用 `report-aggregate` 聚合所有模块的覆盖率
- 如果项目无 JaCoCo 配置，需在 **父 pom** 注入 `report-aggregate` execution

#### 0.3.2 JaCoCo 临时注入

**注入位置决策**：

| 场景 | 注入位置 | 注入内容 |
|------|----------|----------|
| 单模块结构 | 变更模块的 pom.xml | `prepare-agent` + `report` |
| 跨模块结构 | **父 pom.xml** | `prepare-agent` + `report-aggregate` |

**备份 pom.xml**：

```bash
# 单模块：备份变更模块
for module in {affected_modules}; do
  cp "${module}/pom.xml" "${module}/pom.xml.bak"
done

# 跨模块：备份父 pom
cp pom.xml pom.xml.bak
```

**注入 JaCoCo 插件**：

单模块结构注入（在变更模块的 `<build><plugins>` 节点添加）：

```xml
<!-- [TEMP] JaCoCo - 临时注入，勿提交 -->
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

跨模块结构注入（在 **父 pom.xml** 的 `<build><plugins>` 节点添加）：

```xml
<!-- [TEMP] JaCoCo - 临时注入，勿提交 -->
<plugin>
  <groupId>org.jacoco</groupId>
  <artifactId>jacoco-maven-plugin</artifactId>
  <version>0.8.11</version>
  <executions>
    <execution>
      <id>prepare-agent</id>
      <goals><goal>prepare-agent</goal></goals>
    </execution>
    <execution>
      <id>report-aggregate</id>
      <phase>verify</phase>
      <goals><goal>report-aggregate</goal></goals>
    </execution>
  </executions>
</plugin>
```

注入规则：
- 跨模块结构时，**必须注入父 pom**，使用 `report-aggregate` 聚合所有模块覆盖率
- 使用 XML 注释 `<!-- [TEMP] -->` 标记，便于回滚时确认
- 记录 `jacoco_injected = true` 和 `cross_module = true/false` 标志

### 0.4 变更范围探测

```bash
# 获取变更文件
git diff --name-only HEAD~1...HEAD -- "*.java" 2>/dev/null

# 区分生产代码和测试代码
git diff --name-only HEAD~1...HEAD -- "*.java" | grep -v "Test.java" | grep "src/main"
git diff --name-only HEAD~1...HEAD -- "*.java" | grep "Test.java"
```

### 0.5 上下文文档探测

与 dev-cr 的 Step 0.5 一致，探测 `~/.claude/specs/` 下的 dev-plan.md。

### 探测结果输出

```markdown
| 探测项 | 状态 | 详情 |
|--------|------|------|
| ��试框架 | TestNG 7.4.0 + Mockito 4.3.1 | pom.xml |
| TestNG Suite | FOUND | checkin |
| 项目结构 | 单模块 / 跨模块 | 生产代码模块: {list}，测试代码模块: {list} |
| JaCoCo | CONFIGURED / INJECTED | 原有配置 / 临时注入（跨模块用 report-aggregate） |
| dev-plan.md | FOUND / NOT_FOUND | 路径 |
| 变更文件 | N files | 生产代码 X 个，测试代码 Y 个 |
| 模块 | core / impl | 涉及的模块列表 |
```

---

## 覆盖率驱动循环（Step 1 ~ Step 5）

> 以下 5 个步骤构成闭环，循环执行直到行覆盖率 ≥80% 或达到 3 轮上限。

### 循环状态追踪

每轮循环记录：

```markdown
| 轮次 | 测试通过 | 修复次数 | 行覆盖率 | 新增用例 | 结果 |
|------|----------|----------|----------|----------|------|
| 1 | 45/48 → 48/48 | 2 | 62% | 0 | 覆盖率不足，继续 |
| 2 | 55/55 | 0 | 78% | 7 | 覆盖率不足，继续 |
| 3 | 60/60 | 0 | 85% | 5 | 达标，退出循环 |
```

---

## Step 1: 执行单元测试

### 1.1 运行 checkin 级别测试

使用 `-am`（also-make）让 Maven reactor 自动构建依赖模块，避免分步 install 被 FindBugs/PMD 等插件阻断：

```bash
# 示例：运行 impl 模块 checkin suite，-am 自动构建依赖的 core 模块
mvn clean test -pl {test-module} -am \
  -DsuiteXmlFile=src/test/resources/testng_ut_checkin.xml \
  -Dfindbugs.skip=true -Dpmd.skip=true -Dcheckstyle.skip=true 2>&1
```

**为什么用 `-am` 而非分步 install + test**：
- 分步 `install` 可能被 FindBugs 等插件阻断，导致 core 模块未安装到本地仓库
- impl 测试会加载本地仓库中的旧版本 core jar，引发诡异的测试失败
- `-am` 让 Maven reactor 在同一构建中编译所有依赖模块，确保使用最新代码

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

### 1.3 结果判定

| 情况 | 处理 |
|------|------|
| 全部通过 | 跳过 Step 2，直接进入 Step 3 |
| 存在失败 | 进入 Step 2 修复 |

### 1.4 结果记录

```markdown
| 模块 | Suite | 通过 | 失败 | 跳过 | 耗时 |
|------|-------|------|------|------|------|
| core | checkin | XX | X | X | Xs |
| impl | checkin | XX | X | X | Xs |
```

---

## Step 2: 失败修复（内循环）

**前提**：Step 1 存在失败用例时才执行。全部通过则跳过。

### 内循环流程

```
Step 1 失败用例列表
    ↓
记录初始失败快照：{用例名: 错误信息}
    ↓
┌─ 修复迭代（≤3 次）────────────────────┐
│                                        │
│  逐个分析失败原因                       │
│      ↓                                 │
│  优先级 1-3 → 修复测试/生产代码         │
│  优先级 4-5 → 标记 UNRESOLVED/ENV_ISSUE │
│      ↓                                 │
│  ★ 回到 Step 1 重新执行全部测试 ★       │
│      ↓                                 │
│  ── 熔断检查 ──                         │
│  仍有可修复的失败 → 下一次迭代           │
│  全部通过或全部 UNRESOLVED → 退出       │
│                                        │
└────────────────────────────────────────┘
    ↓
进入 Step 3（采集覆盖率）
```

**关键设计**：每次修复后必须回到 Step 1 重新执行全部测试（不是只跑失败用例），因为：
1. 修复可能引入新的失败（改了一个 Mock 配置可能影响其他用例）
2. 需要验证修复确实生效
3. 只有全部测试通过后，Step 3 采集的覆盖率数据才有意义

### 熔断机制

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

### 修复记录

```markdown
| 迭代 | 修复用例 | 失败类型 | 修复内容 | 结果 |
|------|----------|----------|----------|------|
| 1 | XxxTest.test_a | Mock 配置 | 更新 when().thenReturn() | FIXED |
| 1 | YyyTest.test_b | 业务 bug | - | UNRESOLVED |
| 2 | ZzzTest.test_c | 断言值 | 更新 assertEquals | FIXED |
```

---

## Step 3: 采集 JaCoCo 覆盖率

**前提**：Step 1 全部通过（或 Step 2 修复后全部通过）。

### 3.1 运行覆盖率采集

**保障措施**：

| 措施 | 原因 |
|------|------|
| 使用 `mvn clean test -pl -am` | `-am` 让 reactor 一次构建所有依赖模块，避免分步 install 被 FindBugs 阻断 |
| 跳过静态分析插件 | `-Dfindbugs.skip=true` 等，覆盖率采集不需要静态分析，加速构建 |
| 采集期间禁止修改代码 | JaCoCo 注入到报告生成之间，源码变更会导致 exec 文件与 .class 文件不匹配 |
| 采集后校验 class ID | exec 文件的 class ID 必须与 .class 文件一致，否则覆盖率数据无效 |

**根据项目结构选择命令**：

```bash
# 单模块结构：在测试模块运行，-am 自动构建依赖
mvn clean test -pl {test-module} -am \
  -DsuiteXmlFile=src/test/resources/testng_ut_checkin.xml \
  -Dfindbugs.skip=true -Dpmd.skip=true -Dcheckstyle.skip=true 2>&1
# 然后单独生成报告
mvn jacoco:report -pl {test-module} -q 2>&1

# 跨模块结构：在根目录运行，-am 构建所有依赖模块
mvn clean test -pl {test-module} -am \
  -DsuiteXmlFile=src/test/resources/testng_ut_checkin.xml \
  -Dfindbugs.skip=true -Dpmd.skip=true -Dcheckstyle.skip=true 2>&1
# 然后在根目录生成聚合报告
mvn jacoco:report-aggregate -q 2>&1
```

**为什么用 `-am` + 跳过静态分析**：
- `-am`（also-make）：让 Maven reactor 在同一构建中编译依赖模块，避免分步 install 被 FindBugs 等插件阻断
- `-Dfindbugs.skip=true` 等：覆盖率采集阶段不需要静态分析，跳过可避免构建中断且加快速度
- 不使用 `mvn verify`：避免触发不必要的 post-test 阶段插件

**采集期间禁止事项**：

```
❌ 修改任何 .java 源文件
❌ 修改 pom.xml（除了 Step 0 的 JaCoCo 注入）
❌ 运行其他 mvn 命令（避免并发编译）
❌ IDE 自动编译（关闭或忽略）
```

**报告位置**：

| 结构类型 | 报告路径 |
|----------|----------|
| 单模块 | `{module}/target/site/jacoco/jacoco.csv` |
| 跨模块 | `target/site/jacoco-aggregate/jacoco.csv` 或 `{module}/target/site/jacoco-aggregate/jacoco.csv` |

```bash
# 查找覆盖率报告
find . -path "*/site/jacoco*/jacoco.csv" -type f 2>/dev/null
```

### 3.2 校验覆盖率数据有效性

**Class ID 校验**（防止 exec 与 class 文件不匹配）：

JaCoCo 通过 class ID（类文件的 CRC64）关联覆盖率数据。如果 exec 文件记录的 class ID 与当前 .class 文件不一致，覆盖率数据会被静默忽略。

```bash
# 检查 exec 文件中的 class ID
java -jar jacococli.jar execinfo target/jacoco.exec

# 与当前 class 文件对比
# 如果发现 "Execution data for class XxxService does not match" 警告
# 说明覆盖率数据无效，需要重新采集
```

**校验规则**：

| 检查项 | 期望 | 异常处理 |
|--------|------|----------|
| exec 文件存在 | `target/jacoco.exec` 存在且非空 | 如果缺失，说明 JaCoCo agent 未正确注入 |
| class ID 匹配 | exec 中的 class ID 与 .class 文件一致 | 不匹配 → 清理 target → 重新运行 `mvn clean verify` |
| 报告类数量 | ≥ 变更的生产类数量 | 远少于预期 → 检查是否跨模块结构未正确处理 |

**自动重新采集条件**：

如果发现以下情况，必须重新执行覆盖率采集：
1. exec 文件不存在或为空
2. 控制台有 "does not match" 警告
3. 报告中缺少预期变更类

```bash
# 重新采集（强制清理）
rm -rf target/
mvn clean verify jacoco:report-aggregate 2>&1
```

### 3.3 提取变更行号

**关键**：覆盖率只统计**新增和修改的代码行**，不包含历史代码。

```bash
# 提取变更行号（只取新增/修改行，忽略删除行）
git diff --unified=0 HEAD~1...HEAD -- "*.java" | \
  grep -E "^@@.*\+[0-9]" | \
  # 输出格式: 文件名 起始行 行数
```

解析 `git diff --unified=0` 输出，提取每个文件的变更行号：
- `@@ -a,b +c,d @@` 中 `+c,d` 表示新文件的第 c 行开始共 d 行
- 只取 `src/main` 下的生产代码变更，忽略测试代码
- 忽略纯删除行（只有 `-` 没有 `+`）

输出变更行清单：

```markdown
| 变更类 | 变更行号 | 变更行数 |
|--------|----------|----------|
| XxxService | 45-48, 62, 78-82 | 10 |
| YyyLogic | 23-30, 55-60 | 14 |
| **合计** | | **24** |
```

### 3.4 交叉比对 JaCoCo 行级覆盖数据

解析 JaCoCo **XML** 报告（非 CSV，CSV 只有类级粒度）：

```bash
# 单模块报告
find . -path "*/site/jacoco/jacoco.xml" -type f 2>/dev/null

# 跨模块聚合报告
find . -path "*/site/jacoco-aggregate/jacoco.xml" -type f 2>/dev/null
```

JaCoCo XML 中每个 `<line>` 元素包含行号和覆盖状态：

```xml
<!-- nr=行号, mi=missed instructions, ci=covered instructions -->
<line nr="45" mi="0" ci="3" mb="0" cb="2"/>  <!-- 已覆盖 -->
<line nr="46" mi="4" ci="0" mb="1" cb="0"/>  <!-- 未覆盖 -->
```

**交叉比对算法**：

```
对于每个变更类:
  1. 从 git diff 提取变更行号集合: changed_lines = {45, 46, 47, 48, 62, 78, 79, 80, 81, 82}
  2. 从 JaCoCo XML 提取该类所有 <line> 的覆盖状态
  3. 交集: 只看 changed_lines 中的行
     - covered = changed_lines 中 ci > 0 的行数
     - missed  = changed_lines 中 ci = 0 且 mi > 0 的行数
     - no_data = changed_lines 中无 <line> 元素的行（空行/注释/import → 视为非可执行行，不计入）
  4. 变更行覆盖率 = covered / (covered + missed)
     注意: no_data 的行不计入分母
```

**覆盖率数据验证**：

| 检查项 | 期望 | 异常处理 |
|--------|------|----------|
| 变更类是否在 XML 中 | 所有变更的生产类都应有覆盖率数据 | 如果缺失，可能是跨模块结构未正确处理 |
| 变更行是否有 `<line>` | 变更行应有对应元素 | 空行/注释/import 等无指令行可能没有，不计入覆盖率分母 |

**跨模块覆盖率缺失诊断**：

如果变更的生产类不在报告中：

```bash
# 1. 检查 XML 中包含哪些类
grep -o 'name="[^"]*"' {report_path}/jacoco.xml | head -20

# 2. 如果是跨模块结构但未用 report-aggregate
# 需要在根目录重新运行: mvn test jacoco:report-aggregate
```

### 3.5 生成覆盖率快照

```markdown
| 变更类 | 变更行数 | 已覆盖 | 未覆盖 | 变更行覆盖率 | 未覆盖行号 |
|--------|----------|--------|--------|--------------|------------|
| XxxService | 10 | 7 | 3 | 70% | 46, 47, 80 |
| YyyLogic | 14 | 8 | 6 | 57% | 25-28, 58-59 |
| **合计** | **24** | **15** | **9** | **62.5%** | |
```

**注意区分**：
- **变更行覆盖率**（本 skill 的核心指标）：只统计 git diff 中新增/修改行的覆盖情况
- **类级覆盖率**（仅供参考）：JaCoCo CSV 中整个类的覆盖率，包含历史代码

---

## Step 4: 覆盖率门控

### 4.1 门控标准

| 指标 | 阈值 | 说明 |
|------|------|------|
| 变更行覆盖率 | ≥ 80% | 仅统计 git diff 新增/修改行的 JaCoCo 覆盖率 |
| 变更行分支覆盖率 | ≥ 70% | 仅统计 git diff 新增/修改行中的分支覆盖率 |

### 4.2 门控判定

| 判定 | 条件 | 后续动作 |
|------|------|----------|
| **PASS** | 行覆盖率 ≥ 80% 且 分支覆盖率 ≥ 70% | 退出循环，进入 Step 6（报告） |
| **FAIL** | 行覆盖率 < 80% 或 分支覆盖率 < 70% | 进入 Step 5 生成用例 |
| **FORCE_EXIT** | 已达 3 轮外循环上限 | 退出循环，在报告中标记 WARN |

### 4.3 门控日志

```markdown
## 覆盖率门控 - 第 {N} 轮

- 行覆盖率: {XX}% (阈值: 80%) → {PASS/FAIL}
- 分支覆盖率: {XX}% (阈值: 70%) → {PASS/FAIL}
- 判定: {PASS / FAIL → 进入 Step 5 / FORCE_EXIT → 已达上限}
```

---

## Step 5: 针对未覆盖行生成测试用例

**前提**：Step 4 判定 FAIL（覆盖率不达标）。

### 5.1 生成目标分析

基于 Step 3.3 的未覆盖行清单，确定需要生成的测试：

| 分析维度 | 说明 |
|----------|------|
| 未覆盖行所在方法 | 确定需要测试的具体方法 |
| 现有测试是否覆��该方法 | 有 → 补充分支用例；无 → 新建测试方法 |
| 未覆盖原因推断 | 缺少异常分支 / 缺少边界条件 / 缺少 null 处理 / 完全无测试 |

### 5.2 生成确认

使用 `AskUserQuestion` 确认：

```
Question: "第 {N} 轮覆盖率 {XX}%，未达 80% 阈值。以下方法需要补充测试用例："

| 变更类 | 未覆盖方法 | 未覆盖行 | 建议用例 |
|--------|-----------|----------|----------|
| XxxService | methodA | 45-48 | 异常分支 + null 输入 |
| YyyLogic | handleError | 23-30 | 错误码分支覆盖 |

Options:
1. "全部生成（推荐）"
2. "选择性生成"
3. "跳过，接受当前覆盖率"
```

> 用户选择"跳过"时，退出循环，在报告中标记 PASS_WITH_WARNINGS。

### 5.3 单元测试生成规范

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

**针对未覆盖行的用例设计**：
- 未覆盖的 if-else 分支 → 构造触发该分支的输入
- 未覆盖的 catch 块 → Mock 抛出对应异常
- 未覆盖的 null 检查 → 传入 null 参数
- 未覆盖的循环体 → 构造非空集合输入

### 5.4 生成后验证

生成的测试必须运行通过：

```bash
mvn -pl {module} test -Dtest={NewTestClass} 2>&1
```

生成验证的熔断规则：

| 规则 | 阈值 | 触发后行为 |
|------|------|-----------| 
| 单个测试类修复上限 | 2 次 | 放弃该测试类，从项目中删除，标记 GEN_FAILED |
| 同一错误重复出现 | 连续 2 次相同错误信息 | 判定为理解偏差，放弃并删除 |
| 生成总失败上限 | 累计 3 个测试类生成失败 | 停止后续生成，仅保留已成功的 |

**关键原则**：生成失败的测试代码必须从项目中删除，不能留下不可编译或不可运行的测试文件。

### 5.5 回到 Step 1

生成完成后，**回到 Step 1 重新执行全部测试**，开始下一轮外循环：
- 验证新生成的用例能通过
- 重新采集覆盖率（Step 3）
- 重新检查门控（Step 4）

---

## Step 6: 输出测试报告 + 清理

### 6.1 JaCoCo 清理（仅临时注入时）

如果 Step 0.3.1 执行了临时注入（`jacoco_injected = true`），**必须恢复 pom.xml**：

```bash
# 恢复备份
for module in {affected_modules}; do
  mv "/pom.xml.bak" "/pom.xml"
done
```

验证恢复成功：

```bash
# 确认 pom.xml 无变更
git diff --name-only | grep pom.xml
# 应该无输出，如有输出说明恢复失败
```

**绝对原则**：
- JaCoCo 注入仅用于覆盖率采集，**绝不提交到 git**
- 恢复 pom.xml 是必须步骤，即使测试失败也要执行
- 如果恢复失败，在报告中标记 `WARN: pom.xml 恢复失败，请手动检查`
- Step 6 完成后通过 `git diff` 确认 pom.xml 无变更

### 6.2 输出路径

- 工作流模式：`~/.claude/specs/{需求名称}/测试验证/test-report-{YYYYMMDD}.md`
- 独立模式：项目根目录 `test-report-{YYYYMMDD}.md`

### 6.3 报告结构

参考 `references/report-template.md` 模板。

### 6.4 验证标准体系

验证结论基于 3 个维度综合判定：

#### 维度 1：测试执行结果

| 检查项 | PASS 条件 | FAIL 条件 |
|--------|-----------|-----------|
| 单元测试 | 全部通过（允许修复后通过） | 存在 UNRESOLVED 失败 |

#### 维度 2：覆盖率门控（核心指标）

| 指标 | 阈值 | 说明 |
|------|------|------|
| 变更行覆盖率 | ≥ 80% | 仅统计 git diff 新增/修改行的 JaCoCo 覆盖率 |
| 变更行分支覆盖率 | ≥ 70% | 仅统计 git diff 新增/修改行中的分支覆盖率 |
| 变更类覆盖率 | 100% | 每个变更的生产类必须有对应测试类 |

#### 维度 3：覆盖率提升轨迹

记录循环过程中的覆盖率变化：

```markdown
| 轮次 | 行覆盖率 | 分支覆盖率 | 新增用例 | 动作 |
|------|----------|-----------|----------|------|
| 初始 | 45% | 30% | - | - |
| 第 1 轮 | 68% | 55% | 8 | 继续 |
| 第 2 轮 | 82% | 72% | 5 | 达标退出 |
```

### 6.5 验证结论

综合 3 个维度，得出最终结论：

| 结论 | 条件 |
|------|------|
| **PASS** | 测试全部通过 + 行覆盖率 ≥ 80% + 分支覆盖率 ≥ 70% |
| **PASS_WITH_WARNINGS** | 测试全部通过，但覆盖率未达标（达到 3 轮上限或用户主动跳过） |
| **FAIL** | 存在 UNRESOLVED 失败用例 |

验证结论摘要格式：

```markdown
## 验证结论：{PASS / PASS_WITH_WARNINGS / FAIL}

### 各维度评分

| 维度 | 结果 | 详情 |
|------|------|------|
| 测试执行 | PASS / FAIL | 单测 XX/XX 通过 |
| 行覆盖率 | PASS / WARN | {XX}%（阈值 80%），经 {N} 轮循环 |
| 分支覆盖率 | PASS / WARN | {XX}%（阈值 70%） |

### 覆盖率驱动循环摘要

- 总轮次: {N}
- 初始覆盖率: {XX}% → 最终覆盖率: {XX}%
- 新增测试用例: {N} 个
- 修复测试用例: {N} 个
```

### 6.6 后续建议

- FAIL → 列出 UNRESOLVED 失败用例，建议修复后重新运行 test-verify
- PASS_WITH_WARNINGS → 列出覆盖率不足的方法和未覆盖行，建议补充但不阻塞
- PASS → 建议执行 `dev-cr` 进行代码评审

---

## 用户指令

| 指令 | 说明 |
|------|------|
| `/test-stop` | 终止测试验证 |
| `/test-status` | 查看当前测试进度（含循环轮次和覆盖率） |
| `/test-skip <step>` | 跳过某个步骤（如 coverage） |
| `/test-rerun` | 重新执行全部测试 |
| `/test-accept` | 接受当前覆盖率，跳过后续生成轮次 |

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
