# 测试检查清单

## 框架探测规则

| 框架 | pom.xml 关键字 | 版本探测 |
|------|---------------|----------|
| TestNG | `<artifactId>testng</artifactId>` | `<version>` 标签 |
| JUnit 4 | `<artifactId>junit</artifactId>` | `<version>` 标签 |
| JUnit 5 | `<artifactId>junit-jupiter</artifactId>` | `<version>` 标签 |
| Mockito | `<artifactId>mockito-core</artifactId>` | `<version>` 标签 |
| Mockito Inline | `<artifactId>mockito-inline</artifactId>` | 支持 static mock |
| Spring Test | `<artifactId>spring-test</artifactId>` | scope=test |

## TestNG Suite 类型

| Suite 文件 | 用途 | 执行阶段 |
|-----------|------|----------|
| `testng_ut_checkin.xml` | 特性分支单测 | Step 1 |
| `testng_ut_pre_integration.xml` | 集成前验证 | Step 4 |
| `testng_ut_post_integration.xml` | 集成后验证 | Step 4 |

## 测试用例生成标准

### 必须覆盖的场景

| 场景 | 说明 | 优先级 |
|------|------|--------|
| 正常流程 | happy path，标准输入标准输出 | P0 |
| 边界条件 | 空集合、最大值、最小值、零值 | P0 |
| 异常处理 | 方法声明的异常、运行时异常 | P0 |
| null 值 | null 输入参数 | P1 |
| 并发场景 | 多线程调用（视情况） | P2 |

### 测试代码规范

- 类名：`{被测类名}Test`
- 方法名：`test_{场景}_{预期结果}`
- 注解：`@Test`（TestNG）
- Mock 初始化：`@BeforeMethod` + `MockitoAnnotations.initMocks(this)`
- 结构：Given-When-Then
- 断言：使用 TestNG 的 `assertEquals`、`assertNotNull`、`assertThrows`

## 覆盖率标准

| 指标 | 建议值 | 说明 |
|------|--------|------|
| 行覆盖率 | ≥ 80% | 变更代码的行覆盖 |
| 分支覆盖率 | ≥ 70% | if/else/switch 分支 |
| 方法覆盖率 | ≥ 90% | 变更类的公开方法 |

## 修复循环规则

| 规则 | 值 |
|------|-----|
| 最大迭代次数 | 3 |
| 可自动修复 | Mock 配置、断言值、编译错误 |
| 不可自动修复 | 业务逻辑 bug |
| 生成后验证重试 | 2 次 |
