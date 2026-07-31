# 数据来源与抽样说明

## 数据集

- 数据集名称：Multilingual Amazon Reviews Corpus（MARC）
- 论文：Phillip Keung、Yichao Lu、György Szarvas、Noah A. Smith，EMNLP 2020
- Amazon Science：https://www.amazon.science/publications/the-multilingual-amazon-reviews-corpus
- AWS Open Data 登记页：https://registry.opendata.aws/amazon-reviews-ml/
- 本次下载镜像：https://huggingface.co/datasets/goosmanlei/amazon_reviews_multi
- 镜像文件：
  - `en/train.jsonl.gz`
  - `es/train.jsonl.gz`
- 使用的数据切分：`train`

Amazon Science 说明 MARC 包含英语、西班牙语等六种语言的 Amazon 评论，每种语言的训练集包含 200,000 条评论，且五个星级各占 20%。每条记录包含评论标题、正文、星级、匿名评论者 ID、匿名商品 ID和粗粒度商品类别。

## 数据时间与筛选范围

- 原评论时间范围：2015-11-01 至 2019-11-01
- 语言：英语（`en`）、西班牙语（`es`）
- 商品类别：`beauty`
- 每种语言：500 条
- 每个“语言 × 星级”组合：100 条
- 最终总数：1,000 条

MARC 论文说明，语料仅包含经验证购买的评论；每个商品和每位评论者最多保留 20 条评论；评论正文不少于 20 个字符，并经过语言识别和词汇过滤。

## 保留字段

```text
review_id
product_id
language
stars
review_title
review_body
product_category
```

`reviewer_id` 未纳入本项目分析，因此没有写入抽样文件。

## 可复现抽样方法

抽样脚本为 `scripts/sample_marc.mjs`，随机种子为 `crossborder-voice-v1`。

脚本先筛选训练集中的 `language ∈ {en, es}` 且 `product_category = beauty` 的记录，再按语言和星级划分为 10 个分层。对每个分层中的 `review_id` 计算 `SHA-256(seed + NUL + review_id)`，按哈希值从小到大选取前 100 条。该方法等价于不依赖文件遍历顺序的确定性伪随机抽样，可在相同源文件和种子下复现。

运行示例：

```powershell
node scripts/sample_marc.mjs <源文件目录> data/raw/amazon_reviews_raw.csv crossborder-voice-v1
```

源文件目录应包含：

```text
en_train.jsonl.gz
es_train.jsonl.gz
```

## 使用限制

MARC 由 Amazon 在 AWS Open Data 上发布，论文将其用途描述为供研究团体进行非商业研究。镜像页面要求使用者遵循原始数据集条款。该数据集不应被重新解释为不受限制的商业数据。

由于评论采集于 2015—2019 年，本项目只用它验证数据处理方法、模型评测和系统能力，不宣称分析结果代表 2026 年或当前消费趋势。最终跨语言结论仅适用于本项目的抽样数据，不直接外推为所有英语或西班牙语消费者的普遍文化差异。

## 原始数据保护

- `data/raw/amazon_reviews_raw.csv`：未经清洗的分层抽样结果，只保留上述字段；
- `data/processed/`：后续步骤保存清洗或新增派生字段的数据；
- `data/annotation/`：后续步骤保存人工标注与评测数据；
- 后续处理不得覆盖 `data/raw/amazon_reviews_raw.csv`。
