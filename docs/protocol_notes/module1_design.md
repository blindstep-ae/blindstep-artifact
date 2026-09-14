# BlindStep Module 1: Secure Cross-Agent Path Composition 设计文档

本文档定义了 BlindStep 中 Module 1 的设计规范与边界。当前工作阶段（WP3）的核心目标是打通其与 Module 2 (Secure Insertion Queue) 之间的数据流。

## 1. 原则限制与声明边界
- **当前阶段定位**：本阶段**只允许实现 mock join**，通过线性扫描构造模拟交集记录，以便顺利贯通前后端的管道并向后续流水线供数。
- **禁止项约束**：本模块目前代码**禁止实现或嵌入真实的 PSI（Private Set Intersection）逻辑**，避免造成框架复杂度不可控的膨胀。
- **未来接入点**：我们将真实的 PSI 逻辑的选型、设计预留在架构接口上，并将纳入未来的迭代与性能补充（即论文基线外扩充）。

## 2. 输入输出接口定义

### 输入规范
模拟分布式架构中双方的不同局部视图与候选池：
*   **Agent A (查询发起端 / Client Side)**：拥有局部扩展点集 $E_A$，以及各个节点的 Local Score $s_A$。
*   **Agent B (本地知识图谱 / Server Side)**：拥有图谱索引 $G_B$，并能在提取子图点集时携带 Local Score $s_B$。

### 输出规范（严格对齐 Module 2）
- **类型**：`Array(N_max, sint)` 
- **编码结构**：产生的输出需逐项对齐 `[valid] [score] [inverted_tie]`，并被塞入大小为 $N_{max}$ 的一位维数组。
- **计算派生项**：
  *   **score_total** 组合打分 = $s_A + s_B$
  *   **tie** = 原始候选的索引 (用于稳定排序去重)
  *   **valid** = 逻辑 Join 后该条目的有效性标记（0 或 1）

## 3. Mock Join 与 Mock 链路说明

目前的 `mock_private_join` 采用等长遍历（假设双边的空间上限被均齐化处理到了 $N_{max}$ 内）。双方输入直接做对位加载与相乘。
例如，由于本阶段不包含复杂 LSH 或 OPRF hashing，我们仅做线性扫描，令预先约定了的模拟索引输出 `valid = 1`，其他标记为空载 `valid = 0`。随后再进行 $s_A$ 和 $s_B$ 的加密域重组。

**核心接口链路：**
`Mock Input -> mock_private_join -> compose_scores -> prepare_candidate_table (Packed Array)`

## 4. 真实 PSI 未来评估架构预留

为了支持论文撰写和后续进阶扩展设计，我们在模块前置层提供两个技术替换候选方案：

### 候选方案 A：OPRF-based PSI (首选)
- **说明**：一种基于不经意伪随机函数 (Oblivious Pseudo-Random Function) 的非对称集合求交法。
- **优势**：极低的通信代价。客户端只需向服务端传递哈希过的数据请求。服务端即可利用 OPRF 构建查找表提取对应的边评分 ($s_B$)。这完美适配 RAG 请求架构下 Client-Cloud 的负载不均问题。

### 候选方案 B：Circuit-PSI (备选)
- **说明**：通过 Sort-Compare-Shuffle 或者布尔电路完全求解交集的通用求解器。
- **优势**：保证了更强大的电路通用可组合性。由于在全加密下执行，未来如果需计算非常复杂的非线性 `score_root`，可以通过相同的算术门管道顺畅下传。
