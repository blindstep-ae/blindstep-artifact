# BlindStep WP4.5: Baseline Kernel Design

本文档旨在统一 BlindStep WP5 性能评估（Benchmark）阶段 2×2 基准测试矩阵的底层内核设计机制。四种配置必须在公平、统一的标准下进行对比，避免因底层语义分歧导致的性能“虚高”或“虚低”。

**评估矩阵 (2×2 Baseline Matrix)**：
1. All-Boolean + Full Sort (最朴素基准)
2. All-Boolean + Insertion Queue
3. Hybrid + Full Sort
4. Hybrid + Insertion Queue (**Ours**, BlindStep 提出的最终原型)

---

## 1. Tuple Comparator 基准约束

- **统一语义**：所有的 baseline 必须且仅能使用同一套 Tuple 语义定义，即 $\tau = (\text{valid}, \text{score}, \text{tie})$，以及其严格的排序顺序字典序优先级：$(\text{valid}, \text{score}, -\text{tie})$降序。
- **一致性要求**：底层 Comparator 在 Full Sort 网络和 Insertion Queue 队列中必须保持**绝对一致的计算消耗**。它本质是一个安全算子。
- **输入输出格式**：
  - **输入**：两个待比较的元组 $X$ 和 $Y$（无论是拆分为 3 个独立的加密类型，还是统一打包为单一大整数）。
  - **输出**：一个加密位（Secret Bit / 0 or 1 sint），表示 `is_greater` 的布尔真值，用于后续的数据交换多路复用（Oblivious Swap）。

---

## 2. Sort Network (全排序网络基线)

- **统一选型**：Full Sort Baseline 统一且唯一使用 **Bitonic Sort (双向调序网)**。
- **为什么推荐 Bitonic Sort？**：因为它是一种 Data-Oblivious 的排序网络，天然满足安全多方计算要求。其控制流不随输入数据改变，仅依赖网络结构固定的 $O(N_{max} \log^2 N_{max})$ 次比较。
- **高层表达（MP-SPDZ 实现规范）**：为了防止不同跨度 MP-SPDZ 版本因为底层 `Compiler/` 预置库变更导致的非一致性，必须使用显式的双层/三层 `@for_range` 结合上文定义的 Tuple Comparator 与 `if_else` 组合来实现。坚决避免直接调用难以控制内部逻辑的宏封装方法。

---

## 3. Domain Boundary (运算域边界)

需要深刻划分域转换点，以突显出本方案 (Hybrid + Insertion Queue) 的性能。

*   **All-Boolean Baseline 定义**：
    *   **限制**：一旦数据从 Input Share 加载进入 Module 1，直接投射至 Boolean Circuit（如 `sbitint` 二进制域）。
    *   **边界**：聚合步 $S_{total} = s_A + s_B$ 需要付出较高昂的布尔加法器代价计算；所有的 Comparator 及 Multiplexer 完全发生在 Boolean 环境中。
*   **Hybrid Baseline 定义 (盲步默认算子)**：
    *   **限制**：融合算术域与布尔域的优势。
    *   **边界切换**：聚合步 $S_{total} = s_A + s_B$ 单纯使用廉价的 Arithmetic Circuits (`sint` 加法)；随后将加法的密文结果（基于 Secret Shared 整型）送入 Comparator。当遭遇 `<` 或 `>` 关系运算符时，底层协议自动经由 edaBits (或同等域转换算数) 落入隐式 Boolean 执行判断，获取指示位（flag）后，最后使用域原生的乘法或者 `if_else` 来路由数值。这极大降低了数据在传输和运算中的非必要展开。

---

## 4. I/O Format (统一出入参设定)

为了让数据本身不带来干扰：
- **一致性输入**：四种 Baseline **必须共享同一个 mock 数据生成器模块** (`module1_design.md` 中的 Mock 数据或相同的外部输入)。
- **一致性输出**：四种 Baseline 的末端管道，必须能经过同样的解包逻辑被转化为相同的 CSV 输出记录。
- 这是跑通前设架构中统一 Python Plaintext Oracle（`compare_module2_results.py`）比对的前提条件。

---

## 5. Complexity Claims (口径与复杂度声张)

如何区分在论文中展现的数据和纯开发日志数据：

1. **可以写入论文的声明 (Formal Claims)**：
   - 比较器调用总量：Full Sort 为 $O(N_{max} \log^2 N_{max})$ 阶次，Insertion Queue 为 $O(N_{max} \times K)$ 阶次。在 $K \ll N_{max}$ 时理论存在代差。
   - 域划分优势：理论证明 Hybrid 由于直接复用算术加法并简化比较宽度，通信 Rounds 总轮次及数据通信字节数（Communication Overhead, bit/bytes）的降低。
   - 系统级扩展性。
2. **仅供实现日志，不放入纸的记录 (Internal Logs)**：
   - 具体的 MP-SPDZ 命令行标记（如 `-R 64`, `-X`）。
   - 由于测试服务器或者云主机负载波动导致的不稳定挂钟耗时（Wall-clock ms），除相对趋势外的绝对耗时应该作为补充，不可宣称其为硬件恒定。
