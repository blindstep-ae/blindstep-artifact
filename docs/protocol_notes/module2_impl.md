# BlindStep Module 2: Secure Insertion Queue 实现文档

本文档为 BlindStep 中 Module 2 (Secure Insertion Queue) 的详细实现约束与架构笔记，必须严格遵守前置的协议设计冻结规格。

## 1. 论文冻结参数

以下参数为系统核心安全与性能评估时约定的明确数值，在后续论文与实现中统一定义：

| 参数 | 符号 | 描述 | 计算公式 / 默认值 |
|---|---|---|---|
| 最大候选数量 | $N_{max}$ | 参与比较的最大候选元组容量 | 默认 = $128$ |
| Top-K 大小 | $K$ | 最终输出的队列缓冲区长度 | 默认 = $5$ |
| Score 位宽 | $b$ | 打分的非负整数位宽，范围 $[0, 2^b)$ | 默认 = $16$ |
| Tie 位宽 | $t$ | 用于解决同分数冲突的位宽 | $t = \lceil\log_2(N_{max})\rceil$ |
| 总位宽 | $w$ | 单个元组打包后的总位数 | $w = 1 + b + t$ |

---

## 2. 元组编码 (Tuple Encoding)

系统内的候选元组结构为 $\tau = (\text{valid}, \text{score}, \text{tie})$。系统强制采用字典序比较 $(\text{valid}, \text{score}, -\text{tie})$ 降序排列。为简化实现，我们设计了将其映射为单个大整数的 conceptual packed representation。

### Packing 布局图
```text
[MSB]                                                            [LSB]
+---------------+-----------------------+----------------------------+
| valid (1 bit) |     score (b bits)    |    inverted_tie (t bits)   |
+---------------+-----------------------+----------------------------+
```

### 位移计算与编码公式
- **score_shift** = $t$
- **valid_shift** = $t + b$
- **inverted_tie** = $(2^t - 1) - \text{tie}$

**编码公式示例**：
$$Packed = \text{valid} \times 2^{\text{valid\_shift}} + \text{score} \times 2^{\text{score\_shift}} + \text{inverted\_tie}$$

> [!WARNING] 
> **声明边界**：上述的 packed representation 仅是为了 Path A 原型的工程抽象便利。在撰写论文和理论论证时，不能错误暗示这种组合映射在所有安全框架下意味着“原生的免费整数比较”。真实混合电路 (mixed-circuit) 可能会对其进行 bit-decomposition，该部分将在 Path B 中评估。

---

## 3. MemValue 约束与流水线状态

在 MP-SPDZ 中构造时间复杂度严格为 $O(N_{max} \times K)$ 的嵌套 `@for_range` 循环时，流水线内部传递临时状态存在严格的语法限制。

**原理与限制**：
MP-SPDZ 的 `@for_range` 并非 Python 原生的动态环境，而是用来生成底层安全汇编指令的宏。尝试在其内部重新绑定外层 python 对象的引用，将导致编译器状态捕获失效。

**错误 vs 正确示例**：
❌ **错误** (直接重绑定局部变量):
```python
current_candidate = input_array[i]
@for_range(K)
def _(j):
    # current_candidate 在运行时不会被正确更新
    is_greater = current_candidate > queue[j]
    current_candidate = is_greater.if_else(queue[j], current_candidate)
```
✅ **正确** (使用 MemValue 操作底层寄存器):
```python
current_candidate = MemValue(input_array[i])
@for_range(K)
def _(j):
    # 强制执行 read/write 对底层内存单元操作
    active_c = current_candidate.read()
    active_q = queue[j]
    is_greater = active_c > active_q
    
    queue[j] = is_greater.if_else(active_c, active_q)
    current_candidate.write(is_greater.if_else(active_q, active_c))
```

---

## 4. 开发路径 双轨策略

- **Path A: 原型验证 (Ring-based semi-honest prototype)**
  - 基于 `sint` 实装逻辑，利用环算术和模拟环境。
  - **主要作用**：用于前期的管道设计、排错 (debug)、验证 queue 逻辑正确性及打包框架。
  - **局限**：不是最终用于论文 benchmark 对齐的真实耗时版本。
- **Path B: 论文对齐 (Mixed-circuit execution path)**
  - 承载高效率的安全位运算与选路混用。
  - **指令口径**：(TBD)，需在本机 MP-SPDZ 版本验证具体 flag 组合（例如 `-X/-Y`），不在本文档提前锁死。

---

## 5. Dummy Semantics (哨兵语义)

系统中使用的 Dummy 哨兵元素被统一设定为 $\tau_\perp = (0, 0, 0)$。

- **为什么不使用 $-\infty$**：在常规有符号整数中引入负无穷意味着需要增加严格的有符号逻辑处理以及可能引发溢出问题。
- **天然的字典序最低点**：$\tau_\perp = (0, 0, 0)$ 在 packing 公式中等同于 `sint(0)`（前提：假定 `tie` = $2^t - 1$ 最大值被反转位0）。由于布局的高位为 `valid` 参数，任何 `valid=1` 的真实数据通过移位都会处于绝对数值的顶端。即便某节点的 `score=0`，只要 `valid=1`，其数值也会在 `valid=0` 面前占据压倒性优势，从而确保 Dummy 数据自然沉积于 Top-K 队列尾部。

---

## 6. Prototype vs Paper-Aligned Backend 策略论述

当前原型的角色是逻辑验证。但在最终论文撰写中，面临可能的 Reviewer 针对计算深度的拷问时，我们需采用如下**推荐防御性话术**：

1. **组合度量**：强调我们测量的是 "Modular simulation-based composition"，将底层比较算子进行解耦。
2. **泄露定义**：明确 $L = \{N_{max}, K, b, \text{output\_policy}\}$，不随意扩散至 "zero leakage"。
3. **混合协议设计**：在 benchmark 中声明我们借助了 mixed-circuit 的形式对 Tuple Comparison 实施了专门的降维，保证了通信开销。我们在代码层面展示的 $O(N_{max} \times K)$ 本质上代表了调用下层安全比较算子的总次数边界。

---

## 7. 验证清单 (Verification Checklist)

后续需配套对应的 test scripts 与 mock 数据满足以下单元测试要求：

- [ ] **Test A**: 递增分数（模拟常见排序）
- [ ] **Test B**: 全 Invalid（满载 Dummy 注入）
- [ ] **Test C**: 同分数 tie-breaking（考验 tie 反向排序有效性）
- [ ] **Test D**: 不同 K 值的压力测试极值
- [ ] **Test E**: 恰好含有 $K$ 个 Valid 元素
- [ ] **Test F**: 含有少于 $K$ 个 Valid 元素（测试 Dummy 与有效元素的混排边界）
