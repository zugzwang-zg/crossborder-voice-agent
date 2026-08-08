# Review data contract

Contract version: `1.0.0`

The review contract separates source metadata from model-generated analysis.
Identifiers and product scope are validated before inference and copied into
each prediction record under `source`; the model is never asked to infer them.

## Required input columns

| Field | Rule |
|---|---|
| `review_id` | Non-empty and unique within one input file |
| `language` | `en` or `es` |
| `stars` | Integer from 1 to 5 |
| `review_title` | May be empty only when the body is non-empty |
| `review_body` | May be empty only when the title is non-empty |

## Canonical product metadata

| Canonical field | Accepted source aliases | Missing-value behavior |
|---|---|---|
| `product_id` | `product_id` | `unknown` |
| `product_title` | `product_title` | `unknown` |
| `brand` | `brand` | `unknown` |
| `product_category` | `product_category`, `category` | `unknown` |
| `product_subcategory` | `product_subcategory`, `subcategory` | `unknown` |
| `review_date` | `review_date` | `unknown` |
| `locale_or_market_proxy` | `locale_or_market_proxy`, `locale`, `market_proxy` | `unknown` |

`locale_or_market_proxy` is descriptive metadata only. Language must not be
silently converted into a country, nationality, culture, or market claim.

MARC supplies `product_id` and the coarse `product_category`, but it does not
supply product title, brand, subcategory, or a reliable target-country field.
Those unavailable fields therefore remain `unknown` unless a future data source
provides them directly.

## Output traceability

Each successful JSONL record stores the following beside `analysis`:

```json
{
  "source": {
    "contract_version": "1.0.0",
    "language": "en",
    "stars": 5,
    "title": "...",
    "body": "...",
    "product_id": "...",
    "product_title": "unknown",
    "brand": "unknown",
    "product_category": "beauty",
    "product_subcategory": "unknown",
    "review_date": "unknown",
    "locale_or_market_proxy": "unknown"
  }
}
```

Downstream product- or subcategory-level insights may only be generated when
the corresponding field is not `unknown`.
