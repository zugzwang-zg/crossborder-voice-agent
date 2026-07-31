# CrossBorder Voice 人工标注手册

版本：v1.0
适用数据：Amazon Beauty 英语、西班牙语评论
标注单位：一条完整评论（标题 + 正文）

## 1. 标注目标

本项目不是只判断评论“正面还是负面”，而是将消费者表达转化为可追溯的产品和内容运营信息。标注需要回答：

1. 评论整体表达什么情感，强度如何？
2. 消费者评价了哪些对象，每个对象的极性是什么？
3. 出现了什么具体问题？
4. 是否明确提到购买动机、使用场景或用户背景？
5. 是否存在预期落差？
6. 评论者在执行什么语用行为，例如表扬、抱怨、警告或建议？
7. 每个重要判断由哪段原文支持？

所有结论必须来自评论文本。星级可以用于最后的对照，但不能代替文本判断。

## 2. 标注输入与输出

### 2.1 输入字段

```text
review_id
language
stars
review_title
review_body
```

### 2.2 建议输出字段

| 字段 | 类型 | 说明 |
|---|---|---|
| `gold_sentiment` | 单选 | `positive`、`neutral`、`negative`、`mixed`、`uncertain` |
| `gold_intensity` | 1—3 | 情绪表达强度，不等同于星级 |
| `gold_aspects` | 多选 | 二级属性代码，以 `|` 分隔 |
| `gold_aspect_polarities` | JSON | 属性、极性、观点和证据的列表 |
| `gold_issue_types` | 多选 | 明确出现的具体问题 |
| `gold_purchase_motivations` | 多选 | 文本明确说明的购买驱动 |
| `gold_usage_scenarios` | 多选 | 文本明确出现的使用场景 |
| `gold_user_context` | 多选/短文本 | 明确出现的肤质、发质、角色等背景 |
| `gold_expectation_gap` | 单选 | `yes`、`no`、`uncertain` |
| `gold_expectation_gap_types` | 多选 | 图片、颜色、尺寸、效果等落差对象 |
| `gold_speech_acts` | 多选 | 表扬、抱怨、警告、建议等 |
| `gold_experience_status` | 单选 | `used`、`not_used`、`delivery_only`、`unclear` |
| `gold_star_text_alignment` | 单选 | `aligned`、`mild_mismatch`、`strong_mismatch`、`insufficient_text` |
| `gold_evidence` | JSON | 各标签对应的最小充分原文证据 |
| `ambiguous` | 布尔值 | 是否存在无法依据手册稳定解决的歧义 |
| `annotation_confidence` | 1—3 | 人工标注置信度 |
| `annotation_note` | 文本 | 记录边界判断、冲突和无法确定之处 |

多标签字段使用规范化代码，不填写自由翻译。没有明确证据时留空，不填写 `unknown` 作为占位，除非该字段的允许值中明确包含 `uncertain`。

## 3. 标注顺序

为减少星级造成的先入偏见，按以下顺序操作：

1. 先阅读标题和正文，暂不依据星级判断；
2. 判断评论者是否实际使用产品；
3. 圈出所有明确的评价对象和证据片段；
4. 为每个属性分别判断极性；
5. 根据全部评价判断整体情感和强度；
6. 标注具体问题、购买动机、使用场景、用户背景和预期落差；
7. 标注语用行为；
8. 判断歧义和人工置信度；
9. 最后将文本情感与星级对照，标注 `star_text_alignment`。

## 4. 总体原则

### 4.1 允许多标签

一条评论可以包含多个属性、问题、动机、场景和语用行为。

例：

> “The cream itself is really good ... The pump was broken.”

应同时标注：

- `product.efficacy.general_effect`：positive；
- `product.texture.skin_feel`：positive；
- `product.usability.dispenser`：negative；
- 整体情感：`mixed`；
- 问题：`broken_dispenser`。

### 4.2 不进行常识补全

评论只说 “Perfect for travel” 时，可以标注 `travel`，但不能推断产品一定便携、容量一定小或符合航空规定。

评论只说 “My skin felt smooth” 时，可以标注肤感和效果，不能推断成分安全、适合敏感肌或经过临床验证。

### 4.3 区分产品与交易链路

产品效果好但配送差时，产品属性可以是正面，配送属性为负面，整体通常为 `mixed`。不要把配送、卖家或退货问题错误归入产品质量。

### 4.4 保留不确定性

文本过短、代词指向不清、拼写错误严重或可能存在反讽时，优先：

- 只标注有把握的标签；
- 将无法确定的字段留空；
- `ambiguous = true`；
- 在 `annotation_note` 说明原因。

## 5. 整体情感 `gold_sentiment`

### 5.1 `positive`

评论整体明确满意、认可、推荐或表达积极结果，且没有实质性负面评价。

正例：

- EN：`“They leave my face feeling nice and smooth.”`
- ES：`“Realmente iluminan la piel.”`

不是正例：

- `“Good product, but the pump broke on every bottle.”` 包含实质负面信息，应为 `mixed`。

### 5.2 `negative`

评论整体明确不满、失望、拒绝购买、警告他人或描述失败结果，且没有实质性正面评价。

正例：

- EN：`“All leaked out ... Do not buy this.”`
- ES：`“El producto no se corresponde con la descripción.”`

### 5.3 `neutral`

只有事实陈述、没有清晰评价；或信息本身无法支持满意/不满意判断。

例：

- `“I have not used it yet.”`
- `“The package arrived on Tuesday.”`

不要因为星级为 3、4 或 5 自动标注正面。

### 5.4 `mixed`

评论同时包含明确的正面和负面评价，无论两者指向同一属性还是不同属性。

正例：

- EN：`“It is definitely making our teeth whiter. Unfortunately my breath still stinks.”`
- ES：`“Buena cobertura pero es muy grasa.”`

轻微让步也需判断是否构成实质评价：

- `“Great product, a little expensive.”`：价格抱怨明确但轻微，标 `mixed`，强度可为 1；
- `“Great product, arrived Tuesday.”`：后半句是中性事实，仍标 `positive`。

### 5.5 `uncertain`

只在无法稳定解释文本立场时使用，例如严重残缺、反讽证据不足或代词指向不明。不能把“自己不愿意做判断”当作 `uncertain`。

## 6. 情绪强度 `gold_intensity`

强度描述表达方式，不描述产品问题严重程度，也不直接由星级决定。

| 值 | 判断标准 | 典型线索 |
|---:|---|---|
| 1 | 轻微、克制或带缓和 | `a little`、`not bad`、`no me convence`、`una pena` |
| 2 | 清晰、直接但不过度强化 | `disappointed`、`works great`、`no volveré a comprar` |
| 3 | 强烈强化、警告或激烈评价 | 全大写、连续感叹、`DO NOT BUY`、`MUY MAL`、强烈退货或指责 |

标点或大写只能作为线索，不能单独决定强度。长篇理性投诉可能强度为 2；一句明确警告可能为 3。

## 7. 属性标签 `gold_aspects`

属性标签回答“消费者在评价什么”。允许多选，并为每个二级属性单独标注 `positive`、`neutral`、`negative` 或 `mixed`。

### 7.1 一级属性

| 一级代码 | 范围 |
|---|---|
| `product.efficacy` | 是否达到宣称或期望的功能效果 |
| `product.sensory` | 气味、质地、油腻、黏度、吸收、残留、舒适度 |
| `product.appearance` | 颜色、妆效、光泽、外观设计 |
| `product.usability` | 使用难易、涂抹、喷头、泵头、说明书、操控 |
| `product.quality` | 材质、耐用性、破损、机械或电气性能 |
| `product.suitability` | 对明确肤质、发质、部位、经验水平或专业用途的适配 |
| `value` | 价格、数量、尺寸、性价比 |
| `packaging` | 容器、密封、到货状态、包装保护 |
| `fulfillment` | 配送、错发、缺件、退换、卖家与客服 |
| `listing_trust` | 图片、描述、真实性、商品与页面一致性 |

二级标签的完整定义见 `label_dictionary.xlsx`。

### 7.2 属性与问题的区别

- 属性表示评价对象：`packaging.seal_leak_protection`；
- 问题表示发生的失败：`leakage_spillage`。

一句 “The bottle leaked in transit” 应同时具有包装属性负面极性和泄漏问题。

### 7.3 属性证据

每个属性至少绑定一个最小充分证据片段。若同一属性包含正负观点，可记录两个证据片段并将属性极性标为 `mixed`。

## 8. 具体问题 `gold_issue_types`

只标注明确发生、观察到或被评论者明确怀疑的问题。常见类别包括：

- 功能无效或效果不足；
- 不良反应、疼痛或刺激；
- 质地、气味、油腻、黏腻、残留或染色；
- 破损、耐用性差、机械或电气故障；
- 泄漏、开封、疑似使用过；
- 错发、少件、颜色或型号错误；
- 商品与图片或描述不符；
- 延迟、未送达、包装运输损坏；
- 退货、退款或卖家沟通问题；
- 价格上涨或性价比差。

如果评论只说 `“Not good”`，没有具体失败表现，只标负面情感，不强行选择问题类型。

## 9. 购买动机 `gold_purchase_motivations`

购买动机回答“为什么买”，必须是评论明确说明的购买前驱动，不能把使用后的满意点自动当成购买动机。

正例：

- `“I bought these to use while traveling.”` → `travel_portability`
- `“I ordered after my hairdresser used it.”` → `recommendation`
- `“I bought it because it was cheaper.”` → `price_value`

反例：

- `“It smells good.”` 只说明使用后评价，不能自动标 `scent_preference` 动机；
- 五星不等于品牌忠诚或复购。

当评论明确说“再次购买”“用了很多年”时，可标 `repeat_purchase` 或 `brand_familiarity`。

## 10. 使用场景与用户背景

### 10.1 使用场景

只标注明确出现的场景，例如：

- 日常护理；
- 旅行；
- 送礼；
- 家庭或家务用途；
- 专业/沙龙；
- 初学者练习；
- 特殊活动；
- 敏感部位；
- 客户使用。

### 10.2 用户背景

只记录文本明确出现的背景：

- 肤质：油性、干性、敏感、痘肌、熟龄；
- 发质：卷发、浓密、细软、长发、染烫；
- 角色：初学者、专业人士、家长、青少年、客户；
- 身体部位或特殊需求。

不要依据产品类别推断用户性别、年龄、肤质或发质。

## 11. 预期落差

### 11.1 `yes`

文本明确比较“预期/页面/图片/以往经验”和实际结果，且两者不一致。

常见类型：

- `photo_description`
- `color_shade`
- `size_quantity`
- `product_form`
- `performance`
- `delivery`
- `price`
- `authenticity`

正例：

- EN：`“Smaller than pictured.”`
- ES：`“El color es más claro de lo esperado.”`

### 11.2 `no`

没有任何明确落差信息。不能因为评论是负面就推断存在预期落差。

### 11.3 `uncertain`

文本暗示落差但比较对象不清，例如 `“Not what I thought”` 且上下文不足。

## 12. 语用行为 `gold_speech_acts`

允许多选。

| 标签 | 核心功能 |
|---|---|
| `praise` | 表达认可或满意 |
| `complaint` | 描述个人不满或问题 |
| `recommendation` | 明确推荐产品或做法 |
| `warning` | 告诫他人避免风险或不要购买 |
| `suggestion` | 提出改进或使用建议 |
| `comparison` | 与其他产品、价格或过去经验对比 |
| `repurchase_intent` | 明确表示会再次购买 |
| `rejection_no_repurchase` | 明确表示不会再买 |
| `return_refund_intent` | 退货、退款或索赔意图 |
| `request_help` | 向卖家、平台或读者提出问题/求助 |
| `uncertainty_hedging` | 明确表示不确定、可能或个人适配性 |
| `sarcasm_irony` | 表层字面与真实立场相反 |

区分：

- `complaint`：说明自己的问题；
- `warning`：面向他人发出规避建议；
- `suggestion`：提出可以怎样改进；
- `recommendation`：认可并建议使用或购买。

`“Do not buy”` 通常同时是 `complaint + warning`。
`“Apply a very thin layer or it won't dry”` 是 `suggestion`，不一定是抱怨。

## 13. 使用状态 `gold_experience_status`

| 标签 | 标准 |
|---|---|
| `used` | 明确描述使用过程或结果 |
| `not_used` | 明确说明尚未使用 |
| `delivery_only` | 未评价使用，只描述未到货、错发或运输 |
| `unclear` | 无法判断是否使用 |

`not_used` 评论不能标注产品实际效果，即使星级很高。

## 14. 星级与文本一致性

先完成文本标注，再查看星级。

| 标签 | 判断 |
|---|---|
| `aligned` | 星级与文本整体立场基本一致 |
| `mild_mismatch` | 星级方向一致，但强度或混合程度有差异 |
| `strong_mismatch` | 星级与文本主要立场相反 |
| `insufficient_text` | 文本不足以判断一致性 |

参考方向：

- 1—2 星：通常负面；
- 3 星：通常中性或混合；
- 4—5 星：通常正面。

该参考只用于一致性检查，不用于反向修改文本标签。

## 15. 原文证据 `gold_evidence`

### 15.1 选择原则

1. 必须逐字来自标题或正文，不翻译、不改写；
2. 选择能够独立支持标签的最短连续片段；
3. 保留否定词、程度词和比较对象；
4. 多个独立标签可以分别记录证据；
5. 星级不是证据；
6. 文本没有证据时，标签留空。

推荐结构：

```json
[
  {
    "label_type": "aspect",
    "label": "product.usability.dispenser",
    "polarity": "negative",
    "evidence": "the pump was broken in every single bottle"
  }
]
```

### 15.2 最小充分原则

过长：

> `“I received four bottles and every pump was broken, so I opened each bottle and moved the cream to another container.”`

推荐：

> `“the pump was broken in every single bottle”`

不要截掉否定：

- 错误：`“works”`
- 正确：`“doesn’t work”`

## 16. 双语与语言学边界规则

### 16.1 英语缓和与强化

- `not bad`：通常轻度正面，结合上下文；
- `didn't work for me`：负面效果，但带个体适配缓和；
- `seems`、`maybe`：降低确定性，不自动变为中性；
- `DO NOT BUY`：通常强警告。

### 16.2 西班牙语缓和与强化

- `no está mal`：通常轻度正面或保留性认可；
- `ni fu ni fa`：中性偏负或轻度负面；
- `no me convence`：轻度负面；
- `cumple su función`：通常轻度正面；
- `una pena`：表达遗憾，需结合问题内容；
- `por el precio`：可能是性价比认可，也可能降低期望；
- `MUY MAL`、连续感叹：强度线索。

### 16.3 反讽

只有当上下文清楚表明字面和真实立场相反时标 `sarcasm_irony`。单独的夸张、感叹号或拼写错误不足以证明反讽。

### 16.4 代码转换和拼写错误

保留原文，不纠正证据。根据完整语境标注语义；若拼写错误导致无法稳定解释，标 `ambiguous = true`。

## 17. 边界案例

### 案例 A：产品好，包装坏

> `“The cream itself is really good ... the pump was broken.”`

- sentiment：`mixed`
- aspects：效果 positive；泵头 negative
- issue：`broken_dispenser`
- speech acts：`praise`、`complaint`

### 案例 B：产品满意，配送差

> `“El producto me ha resultado satisfactorio ... el envío no.”`

- sentiment：`mixed`
- aspects：产品效果 positive；配送 negative
- 不得将配送问题标为产品质量差

### 案例 C：五星但未使用

> `“What I expected haven't used yet.”`

- sentiment：可标轻度 `positive`，因为“符合预期”是明确认可；
- experience：`not_used`
- 不标产品效果；
- star-text alignment：`mild_mismatch` 或 `insufficient_text`，需在备注中说明。

### 案例 D：明确个体适配

> `“Maybe this stuff works, but it didn't for me.”`

- sentiment：`negative`
- aspect：效果 negative
- speech act：`uncertainty_hedging`
- 不得扩展为“对所有人无效”

### 案例 E：短评但信息明确

> `“El color es más claro de lo esperado.”`

- sentiment：`negative`
- aspect：颜色 negative
- expectation gap：`yes / color_shade`
- 短文本不等于模糊文本

### 案例 F：使用建议不是问题

> `“Apply a very thin layer or it won't dry.”`

- speech act：`suggestion`
- usability 可根据完整上下文判断；
- 不能只因出现 `won't dry` 就标产品无效。

## 18. 歧义与置信度

### 18.1 `ambiguous = true`

满足任一情况：

- 两种解释都合理且手册无法排除；
- 评价对象指向不清；
- 反讽可能性较高但证据不足；
- 文本残缺或语言错误严重；
- 标题和正文直接冲突且无法判断主导立场。

### 18.2 `annotation_confidence`

| 值 | 标准 |
|---:|---|
| 3 | 证据明确，规则直接适用 |
| 2 | 基本明确，但存在轻微边界判断 |
| 1 | 需要复核或存在多种合理解释 |

`ambiguous = true` 通常对应置信度 1，但不是强制；可在备注中解释。

## 19. 一致性检查与仲裁流程

1. 两名标注者先独立标注相同的 20 条试标数据；
2. 对整体情感计算一致率或 Cohen's Kappa；
3. 对多标签属性计算样本级或标签级 F1；
4. 集中讨论所有不一致案例；
5. 只通过补充手册规则解决系统性歧义，不针对单个样本临时改变定义；
6. 冻结 v1.0 后再开始正式 100 条评测集；
7. 第一遍标注完成后至少间隔一天复核；
8. 最终评测集不得用于提示词优化。

建议试标门槛：

- 整体情感一致率 ≥ 85%；
- 一级属性一致率 ≥ 80%；
- 关键证据片段能够支持标签；
- 未达门槛时继续修订手册，不进入正式标注。

## 20. 提交前检查清单

- [ ] 是否只依据标题和正文标注？
- [ ] 是否将产品与配送、卖家、退换问题分开？
- [ ] 是否允许一条评论包含多个属性？
- [ ] 每个属性是否有独立极性？
- [ ] 是否正确处理混合情感？
- [ ] 是否避免推断评论未提及的信息？
- [ ] 是否保留否定词和程度词作为证据？
- [ ] 未使用产品的评论是否避免标注实际效果？
- [ ] 是否记录预期落差的具体对象？
- [ ] 是否标记语用行为和强度？
- [ ] 歧义案例是否填写备注？
- [ ] 星级是否只在最后用于一致性对照？
