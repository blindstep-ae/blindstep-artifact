# 核心协议冻结规格与约束声明

本文档记录 **BlindStep** 相关的核心开发及设计冻结准则，所有后续代码实现需严格与此保持对齐。

## 1. 论文冻结参数
- **$N_{max}$**: 最大候选元组容量
- **$K$**: Top-K 提取队列长度
- **$b$**: score 的位宽
- **$t$**: tie 位宽 ($t = \lceil\log_2(N_{max})\rceil$)
- **$w$**: 复合元组总位宽 ($w = 1 + b + t$)

## 2. 元组与比较语义
- **元组定义**: $\tau = (\text{valid}, \text{score}, \text{tie})$
- **Dummy 语义 (哨兵)**: $\tau_\perp = (0, 0, 0)$
- **排序顺序**: 优先级依次为 $(\text{valid}, \text{score}, -\text{tie})$，采取**降序排列**策略（即 valid 与 score 越大越优先，tie 越小越优先）。

## 3. 安全与 Leakage 边界
基于 2-party, semi-honest 模型。声明 "Modular simulation-based composition in the semi-honest setting" ，并遵守 "Provably hides all information except the explicitly modeled leakage" 的准则。
- **Explicit Leakage**: $L = \{N_{max}, K, b, \text{output\_policy}\}$
  *(注：根据后续演进，论文口径可扩展项可能包含 transcript/message length)*

## 4. 2×2 Baseline 矩阵
基于系统需求，实验与评估主要构成 2×2 的 baseline 对比分析矩阵：
*(TBD)*

## 5. Path A / Path B 双轨策略
- **Path A**: Ring-based semi-honest prototype，核心验证原语功能逻辑。
- **Path B**: Paper-aligned mixed-circuit path，承载正式的基准测试（Benchmark）。
  *(内部提示：需本机验证具体 MP-SPDZ mixed path 编译，但论文或文档中不可写死具体 flag如 -X/-Y/-Z)*

## 6. Module 1 与 PSI 限制
- **第一版约束**: Module 1 第一版**仅允许**实现 mock join，不实现真实的 PSI。
- **未来扩展候选**: 真实的 PSI 仅作为未来扩展，首选为 **OPRF-based PSI**，备选为 **Circuit-PSI**。
