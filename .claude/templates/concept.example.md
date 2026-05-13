---
tags:
  - transformer
  - attention
  - deep-learning
source: "[[happy-llm]]"
source_range: "lines 595-711"
---

注意力机制（Attention Mechanism）是 Transformer 架构的核心，源于计算机视觉领域，后在 NLP 中大放异彩。核心思想：处理信息时无需关注全部内容，只将注意力集中在重点部分即可。机制通过三个核心变量 Query（查询）、Key（键）、Value（真值）运作——计算 Query 与 Key 的相关性，为 Value 加权求和，从而拟合序列中每个词与其他词的相关关系。

## 核心原理

### 字典类比：从精确匹配到模糊匹配

理解注意力机制最直观的切入点是字典查询。假设有字典：

```json
{"apple": 10, "banana": 5, "chair": 2}
```

Key 是字典的键，Value 是字典的值。如果 Query 是 "apple"，可以精确匹配得到 Value=10。

但如果 Query 是一个**抽象概念**（例如 "fruit"），就无法精确匹配到任一 Key——apple 和 banana 都该匹配，chair 不该匹配。此时需要给每个 Key 赋予不同权重，再对 Value 加权求和：

```json
{"apple": 0.6, "banana": 0.4, "chair": 0}
```

最终结果 = 0.6 × 10 + 0.4 × 5 + 0 × 2 = 8。这里给 Key 赋予的权重就是**注意力分数**——为了查询 Query，应该在每个 Key 上分配多少注意力。

### 用点积衡量相关性

如何为任意 Query 计算出合理的注意力分数？核心假设：Key 与 Query 相关性越高，权重越大。

利用词向量的性质：语义相似的词对应向量点积较大，语义远的词点积小（甚至为负）。因此用点积度量 Query 与 Key 的相似程度：

$$
\boldsymbol{v} \cdot \boldsymbol{w} = \sum_{i} v_i w_i
$$

将所有 Key 的词向量堆叠成矩阵 K，Query 向量记为 q，则 q 与每个 Key 的相似程度可一次性计算：

$$
x = q K^T
$$

### Softmax 归一化为权重

得到的 x 还不是和为 1 的权重，需要通过 Softmax 转换：

$$
\operatorname{softmax}(x)_i = \frac{e^{x_i}}{\sum_j e^{x_j}}
$$

用这份权重对 Value 向量加权求和，就得到注意力输出。合并成公式：

$$
\text{attention}(Q, K, V) = \operatorname{softmax}(q K^T) V
$$

### 从单 Query 到矩阵形式

单次只查询一个 Query 效率低，把多个 Query 堆叠成矩阵 Q，得到：

$$
\text{attention}(Q, K, V) = \operatorname{softmax}(Q K^T) V
$$

### 缩放因子 √d_k：防止梯度不稳

当 Q、K 的维度 $d_k$ 较大时，$QK^T$ 的数值范围会随维度线性扩大，进入 Softmax 后梯度非常小（Softmax 在输入数值大时趋于饱和）。解决办法是对点积结果做缩放：

$$
\text{attention}(Q, K, V) = \operatorname{softmax}\left(\frac{Q K^T}{\sqrt{d_k}}\right) V
$$

这就是注意力机制的标准公式。

## 关键细节

### PyTorch 最小实现

```python
def attention(query, key, value, dropout=None):
    # 获取键向量的维度（与值向量维度相同）
    d_k = query.size(-1)
    # 计算 Q·K^T / √d_k
    scores = torch.matmul(query, key.transpose(-2, -1)) / math.sqrt(d_k)
    # Softmax 得到注意力权重
    p_attn = scores.softmax(dim=-1)
    if dropout is not None:
        p_attn = dropout(p_attn)
    # 加权求和得到输出
    return torch.matmul(p_attn, value), p_attn
```

假设传入的 q、k、v 已是经过线性变换的词向量矩阵。核心代码约 6 行。

### 为什么不用欧式距离

点积计算更高效（矩阵乘法高度并行化），且语义相似度的排序与欧式距离一致——对于归一化向量，两者单调相关。

### 核心优势（相比 RNN）

- **并行计算**：RNN 需按序列依次处理，GPU 并行能力受限；注意力机制的矩阵乘法可完全并行。
- **长距离依赖**：任意位置间的相关性直接通过一次点积计算，不会因距离变远而衰减；RNN/LSTM 对远距离依赖捕获能力弱。

### 计算复杂度

序列长度 N、维度 d 时，$QK^T$ 产生 N×N 矩阵，显存和时间复杂度均为 $O(N^2 d)$。这是长序列的瓶颈，催生了 [[flash-attention]] 等优化方案。

## 与其他概念的关联

- 变体：[[self-attention]]（Q、K、V 来自同一输入）、[[masked-self-attention]]（加未来掩码）、[[multi-head-attention]]（多组并行注意力）
- 基础架构：[[transformer]]
- 优化实现：[[flash-attention]]
- 任务范式：[[seq2seq]]（早期在 Encoder-Decoder 中作为增强）
