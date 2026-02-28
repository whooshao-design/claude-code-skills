# 核心代码规范（从 dev-cr 提取）

> 开发过程中自动遵循的规范，减少后续 CR 问题。

---

## 1. 幂等性设计

### 必须幂等的场景
- 所有写操作（INSERT/UPDATE/DELETE）
- MQ 消费者
- 定时任务
- 回调接口

### 幂等实现方式
| 方式 | 适用场景 | 示例 |
|------|----------|------|
| 唯一键约束 | 数据库写入 | `UNIQUE KEY (biz_no, biz_type)` |
| 幂等表 | 通用场景 | 插入幂等记录，冲突则跳过 |
| 状态机 | 状态流转 | 只允许合法状态转移 |
| 版本号 | 并发更新 | `WHERE version = #{version}` |

---

## 2. 埋点规范

### 三类必须埋点
| 类型 | 位置 | 方法 |
|------|------|------|
| 入口埋点 | 方法入口 | `sumReport` / `counterReport` |
| 决策埋点 | 关键分支 | `counterReport` |
| 异常埋点 | catch 块 | `errorReport` |

### 埋点命名规范
```
{系统}.{模块}.{操作}.{结果}
例：hawk.dispatcher.route.success
例：hawk.dispatcher.route.fail
```

---

## 3. 异常处理

### 规则
- ❌ 不允许空 catch 块
- ❌ 不允许 catch (Exception e) 后只打日志不处理
- ✅ 捕获具体异常类型
- ✅ 异常信息包含上下文（入参、状态）
- ✅ 业务异常和系统异常分开处理

### 示例
```java
// ❌ 错误
try {
    doSomething();
} catch (Exception e) {
    log.error("error", e);
}

// ✅ 正确
try {
    doSomething();
} catch (BizException e) {
    log.warn("业务异常, bizNo={}, code={}", bizNo, e.getCode(), e);
    return Result.fail(e.getCode(), e.getMessage());
} catch (Exception e) {
    log.error("系统异常, bizNo={}", bizNo, e);
    monitorReport.errorReport("hawk.xxx.systemError");
    throw e;
}
```

---

## 4. 并发控制

### 检查清单
- [ ] 共享变量是否线程安全
- [ ] 是否需要加锁（乐观锁/悲观锁/分布式锁）
- [ ] 锁粒度是否合理（不要锁整个方法）
- [ ] 是否有死锁风险

### 常见模式
| 场景 | 推荐方案 |
|------|----------|
| 数据库并发更新 | 乐观锁（version 字段） |
| 分布式资源竞争 | Redis 分布式锁 |
| 内存共享状态 | ConcurrentHashMap / AtomicXxx |
| 计数器 | AtomicLong / LongAdder |

---

## 5. 日志规范

### 规则
- 关键节点必须有日志（入口、出口、异常、状态变更）
- 日志级别正确（ERROR/WARN/INFO/DEBUG）
- 不打印敏感信息（密码、身份证、银行卡）
- 日志包含上下文（traceId、bizNo、userId）

### 日志级别
| 级别 | 使用场景 |
|------|----------|
| ERROR | 系统异常、需要人工介入 |
| WARN | 业务异常、可自动恢复 |
| INFO | 关键业务节点、状态变更 |
| DEBUG | 调试信息、详细参数 |

---

## 6. 数据库操作

### 规则
- SELECT 必须有 WHERE 条件
- UPDATE/DELETE 必须有 WHERE 条件
- 批量操作必须分批（每批 ≤500）
- 事务范围最小化
- 索引覆盖常用查询

### DDL 兼容性
| 操作 | 兼容性 | 注意事项 |
|------|--------|----------|
| 新增字段 | ✅ | 必须有默认值或允许 NULL |
| 删除字段 | ⚠️ | 先停止使用，再删除 |
| 修改字段类型 | ❌ | 新增字段 + 数据迁移 |
| 新增索引 | ✅ | 注意锁表时间 |

---

## 7. 性能规范

### 检查清单
- [ ] 循环内无数据库查询（N+1 问题）
- [ ] 大集合操作使用 Stream 或分批
- [ ] 缓存命中率是否合理
- [ ] 锁持有时间是否最短
- [ ] 事务范围是否最小

### 常见优化
| 问题 | 优化方案 |
|------|----------|
| N+1 查询 | 批量查询 + Map 关联 |
| 大事务 | 拆分事务、异步处理 |
| 热点 Key | 本地缓存 + 分片 |
| 慢查询 | 索引优化、分页查询 |

---

## 8. 状态机规范

### 规则
- 状态枚举必须完整定义
- 状态流转必须有明确的触发条件
- 不允许出现孤立状态（无法到达或无法离开）
- 异常状态必须有补偿机制

### 示例
```java
public enum OrderStatus {
    INIT("初始"),
    PROCESSING("处理中"),
    SUCCESS("成功"),
    FAILED("失败");

    // 合法状态转移
    private static final Map<OrderStatus, Set<OrderStatus>> TRANSITIONS = Map.of(
        INIT, Set.of(PROCESSING),
        PROCESSING, Set.of(SUCCESS, FAILED),
        FAILED, Set.of(PROCESSING)  // 允许重试
    );

    public boolean canTransitTo(OrderStatus target) {
        return TRANSITIONS.getOrDefault(this, Set.of()).contains(target);
    }
}
```
