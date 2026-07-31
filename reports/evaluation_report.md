# 模型评测报告

- 评测集：冻结人工金标准 100 条
- 语言分布：英语 50 条，西班牙语 50 条
- 对比版本：Baseline `v1_basic`；Improved `v9_consistency_guard`
- 模型：两版均为 `gpt-5.6-luna`
- 评测原则：相同模型、相同100条评论、相同结构化输出Schema；只改变提示词指导。
- 报告状态：`complete`

## 总体自动评测

| 指标 | Baseline | Improved | 建议目标 | Improved结果 |
|---|---:|---:|---:|---|
| JSON解析成功率 | 100.0% | 100.0% | ≥95% | pass |
| 情感 Accuracy | 87.0% | 89.0% | ≥80% | pass |
| 情感 Macro-F1 | 65.6% | 67.2% | — | — |
| 属性 Precision | 72.2% | 83.2% | — | — |
| 属性 Recall | 63.3% | 66.7% | — | — |
| 属性 F1 | 67.5% | 74.0% | ≥70% | pass |
| 痛点完全匹配率 | 64.0% | 71.0% | — | — |
| 证据原文子串有效率 | 100.0% | 100.0% | — | — |

说明：属性指标采用多标签微平均；痛点完全匹配率以人工金标问题集合为准；原文子串有效率只证明引用来自评论，语义是否真正支持标签另由人工抽查。

## 多语言表现

| 版本 | 语言 | 情感Accuracy | 情感Macro-F1 | 属性Precision | 属性Recall | 属性F1 |
|---|---|---:|---:|---:|---:|---:|
| Baseline | en | 90.0% | 89.9% | 69.7% | 62.5% | 65.9% |
| Baseline | es | 84.0% | 63.7% | 75.0% | 64.1% | 69.1% |
| Improved | en | 92.0% | 92.0% | 78.8% | 65.4% | 71.5% |
| Improved | es | 86.0% | 65.2% | 88.1% | 67.9% | 76.7% |

## 人工复核状态

- 证据语义有效性：50 / 50，状态 `complete`。
- 商业建议四维评分：40 / 40，状态 `complete`。
- 商业建议评分维度：具体性、数据依据、可执行性、过度推断控制，均为1—5分。

### 证据语义有效性人工抽查

| 版本 | 有效/抽查 | 语义有效率 | 目标 | 结果 |
|---|---:|---:|---:|---|
| Baseline | 22 / 25 | 88.0% | — | — |
| Improved | 24 / 25 | 96.0% | ≥90% | pass |

### 商业建议人工评分

| 维度 | Baseline | Improved | Improved差值 |
|---|---:|---:|---:|
| 具体性 | 3.95 | 4.00 | +0.05 |
| 数据依据 | 4.85 | 4.85 | +0.00 |
| 可执行性 | 4.10 | 3.95 | -0.15 |
| 过度推断控制 | 4.40 | 4.55 | +0.15 |
| **总体均分** | **4.325** | **4.338** | **+0.013** |

## 版本对比结论

- Improved 情感准确率比 Baseline 提高 2.0 个百分点。
- Improved 属性 F1 提高 6.55 个百分点，主要来自误报减少和Precision提升。
- Improved 痛点 F1 提高 2.30 个百分点，痛点集合完全匹配率提高 7.0 个百分点。
- 人工证据语义有效率由 88.0% 提高到 96.0%。
- 商业建议总体人工均分基本持平：4.325 对 4.338；Improved在过度推断控制上更好，但可执行性略低。
- 以上为100条冻结评测集上的描述性结果；人工证据与建议评分为平衡抽样，不作统计显著性外推。

## 失败案例

### 1. baseline · en_0657287 · en · 1星

- 失败类型：`sentiment_mismatch|aspect_false_positive|aspect_false_negative|issue_false_positive`
- 人工情感：`mixed`；预测：`negative`
- 属性误报：`product.quality.durability_breakage|product.usability.dispenser`
- 属性漏报：`fulfillment.item_accuracy|product.appearance.design_look|product.quality.material_build`
- 痛点误报：`durability_problem|other_explicit_issue`
- 痛点漏报：`无`
- 评论原文：Two bows missing& alligator clips are flimsy not sturdy — Cute bows, but definitely not what I expected! Two bows that my daughter wanted didn’t come inside so two missing bows and the alligator clips used are cheap! We didn’t use the bows at all a waste of money I missed the return window so now we are stuck with bows that won’t be used 👎🏽

### 2. improved · en_0977370 · en · 3星

- 失败类型：`aspect_false_positive|aspect_false_negative|issue_false_positive|issue_false_negative`
- 人工情感：`mixed`；预测：`mixed`
- 属性误报：`product.appearance.design_look|product.efficacy.general_effect`
- 属性漏报：`product.appearance.color_shade|value.price_value|value.size_quantity`
- 痛点误报：`insufficient_effect|other_explicit_issue`
- 痛点漏报：`price_value_problem|size_quantity_mismatch`
- 评论原文：Buy 2 — Really soft and silky and matches pretty well but I needed a more full look as I have shoulder length hair and these didn't deliver. They are definitely not as full as the pictures. I was pretty disappointed. I need them for Easter and mothers day and had to buy an extra set and paid an extra 3.99 for one day shipping. We will see how they hold up

### 3. baseline · es_0262123 · es · 3星

- 失败类型：`sentiment_mismatch|aspect_false_positive|aspect_false_negative|issue_false_positive`
- 人工情感：`positive`；预测：`mixed`
- 属性误报：`product.efficacy.general_effect|product.sensory.scent|product.suitability.body_area_fit`
- 属性漏报：`product.efficacy.cleansing|product.usability.ease_of_use`
- 痛点误报：`insufficient_effect`
- 痛点漏报：`无`
- 评论原文：Si es para vapeo, usar con cuidado — Como algodón para desmaquillarse es perfecto. Para vapeo, hay que quitar las capas mas externas para que no de ningún sabor.

### 4. baseline · es_0912409 · es · 4星

- 失败类型：`sentiment_mismatch|aspect_false_positive|aspect_false_negative`
- 人工情感：`mixed`；预测：`positive`
- 属性误报：`product.efficacy.speed_duration`
- 属性漏报：`product.sensory.greasiness|product.sensory.scent|product.suitability.skin_hair_fit|value.size_quantity`
- 痛点误报：`无`
- 痛点漏报：`无`
- 评论原文：Me encanta — Me encanta!! Tengo la piel grasa y nunca pense en usar un aceite.pero este me gusta mucho.no ha aportado mas grasa de la que ya tengo.la piel la noto mas hidratada y muy suave.en los poros no he notado que los haya disminuido.el olor me encanta.estoy deseando que llegue la noche para aplicarmelo porque es como un momento de relax.cunde muchisimo.lo volveria a comprar

### 5. baseline · en_0077091 · en · 3星

- 失败类型：`aspect_false_positive|aspect_false_negative|issue_false_positive`
- 人工情感：`negative`；预测：`negative`
- 属性误报：`fulfillment.item_accuracy|product.efficacy.general_effect|product.quality.mechanical_electrical`
- 属性漏报：`product.quality.material_build|product.usability.ease_of_use`
- 痛点误报：`mechanical_malfunction|other_explicit_issue`
- 痛点漏报：`无`
- 评论原文：Drainage Tube — Just opened, but the drainage tub doesn't clip/attach to the unit. So much for product testing before shipping. Hopefully it works well.

### 6. improved · en_0116976 · en · 1星

- 失败类型：`sentiment_mismatch|aspect_false_positive|aspect_false_negative|issue_false_negative`
- 人工情感：`negative`；预测：`mixed`
- 属性误报：`product.efficacy.hair_styling`
- 属性漏报：`product.sensory.comfort_irritation|product.suitability.skin_hair_fit`
- 痛点误报：`无`
- 痛点漏报：`other_explicit_issue`
- 评论原文：Tears out hair - Do Not Buy!!! — I wore these for an 8hr day at work. I put 2 in my hair to keep my bangs back. I got home to take them out and they tore out huge chunks of hair!! If you value your hair you will not buy these. My hair was straightened, smooth, and dry. No excuse for the amount of hair I lost in only 1 day.

### 7. improved · en_0146413 · en · 1星

- 失败类型：`sentiment_mismatch|aspect_false_negative|issue_false_positive|issue_false_negative`
- 人工情感：`negative`；预测：`mixed`
- 属性误报：`无`
- 属性漏报：`product.suitability.skin_hair_fit`
- 痛点误报：`insufficient_effect`
- 痛点漏报：`no_effect|texture_problem`
- 评论原文：I would not recommend it for oily or complex skin types — It has nice smell but that's all. It feels heavy and very oily on your skin. It does not supply any moisture nor effectively keeps it from your skin. I've gotten a lot of pimples and my skin even got itchy. Not recommend at all...

### 8. baseline · es_0497325 · es · 4星

- 失败类型：`aspect_false_positive|aspect_false_negative|issue_false_positive|issue_false_negative`
- 人工情感：`mixed`；预测：`mixed`
- 属性误报：`product.appearance.finish_shine|product.efficacy.general_effect`
- 属性漏报：`product.quality.durability_breakage|product.suitability.skin_hair_fit|value.price_value`
- 痛点误报：`other_explicit_issue`
- 痛点漏报：`difficult_to_use`
- 评论原文：Están muy bien, apenas se notan — La verdad es que, sin ser excesivamente largas, sí que hacen que parezca que tengo el pelo bastante más largo y, sobre todo, aportan muchísimo volumen. Vienen muy bien peinadas así que además cuando te las pones parece que tienes unos rizos muy bonitos. a mí no me parece que sean excesivamente brillantes, pero lo que es verdad es que a la luz toman un tono rojizo y se notan algo distintas a mi color (castaño oscuro) aunque más que quedar poco natural parece que llevo reflejos. La mayor pega es que se enredan mucho, muchísimo. Además como las peines se quedan sin forma y que parecen un estropajo,Yo me muevo bastante y mi pelo es fino y se enreda mucho por lo que dudo que me duren más de 15 de puestas sin quedarse totalmente enredadas y dejar de estar bonitas. Otra pega es que los enganches no aguantan muy bien en el pelo fino (prefiero los de clip). De todos modos, teniendo en cuenta el precio, están muy bien de calidad y no es demasiado costoso comprarse otras cuando se estropeen, cosa que haré.

### 9. baseline · es_0702047 · es · 4星

- 失败类型：`sentiment_mismatch|aspect_false_positive|aspect_false_negative`
- 人工情感：`mixed`；预测：`positive`
- 属性误报：`product.appearance.finish_shine|product.efficacy.general_effect`
- 属性漏报：`product.efficacy.cleansing|product.efficacy.hair_styling`
- 痛点误报：`无`
- 痛点漏报：`无`
- 评论原文：Muy brillante — No hace mucha espuma, pero te deja el pelo muy brillante

### 10. baseline · es_0301352 · es · 1星

- 失败类型：`sentiment_mismatch|aspect_false_positive|aspect_false_negative|issue_false_positive`
- 人工情感：`mixed`；预测：`negative`
- 属性误报：`fulfillment.seller_service`
- 属性漏报：`packaging.seal_leak_protection`
- 痛点误报：`seller_support_problem`
- 痛点漏报：`无`
- 评论原文：Producto recibido en malas condiciones — Producto recibido en condiciones no adecuadas, el envase estaba abierto, las botellas vienen dentro de una bolsa de plástico con parte del producto fuera de las mismas, no se corresponde con la imagen de venta en la que se aprecia que cada producto viene en su propia caja. Adjunto foto. Se aprecia que el vendedor no cuida la calidad de su envío, una lástima ya que el producto no se lo merece.

## 失败原因归纳

1. 多属性长评论容易出现细粒度属性漏报，尤其同一句同时包含效果、适配与使用体验时。
2. `mixed` 与单一正负情感的边界依赖是否存在明确、独立的相反评价。
3. 属性与具体痛点标签粒度不同：模型可能识别到属性，但未输出对应问题类型，或反之。
4. 短评论上下文不足，星级能够辅助判断，但不能替代文本证据。
5. 英西表达中的省略、缓和、比较和口语拼写会影响细粒度标签召回。

## 下一轮改进建议

- 失败案例只能用于下一轮开发，不在本次金标准上修改Prompt后重测。
- 另建新的开发集补充多属性长评论、短文本及英西口语边界案例。
- 将高频混淆属性整理为成对反例，并增加细粒度标签互斥或共现规则。
- 下一版本完成后必须换用新的冻结评测集，避免对本次100条过拟合。

## 产物

- `reports/model_version_comparison.svg`
- `reports/failure_cases.csv`
- `data/evaluation/evidence_manual_review.csv`
- `data/evaluation/business_advice_manual_review.csv`
