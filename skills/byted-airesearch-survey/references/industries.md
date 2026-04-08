# Industries

Use this file only when the user is starting a new AI research request or revising a request that changes the target industry.

## Source of truth

The directly executable industry list is defined in code. Treat the code constant as authoritative. This file explains mapping rules only.

## Directly executable industries

Use these English labels in reasoning and host-side guidance:

- Tri-fold smartphones
- Home appliances
- Smartphones
- Automobiles
- Western spirits
- Freshly made tea drinks
- Bottled tea drink consumers
- Beauty and cosmetics
- Stock investing
- Sportswear and sneakers
- Beverages

Do not treat the generic "Other" bucket as a directly executable industry.

## Mapping guidance

### Freshly made tea drinks

Map requests here when the user mentions brands or products such as:

- CHAGEE
- HEYTEA
- Naixue
- Chabaidao
- Guming
- Hushang Ayi
- new drinks, tea latte, fruit tea, seasonal launches, concept testing

### Automobiles

Map requests here when the user mentions brands or models such as:

- Xiaomi SU7
- AITO
- Li Auto
- Shangjie
- Zeekr
- NIO
- new launch, market reaction, purchase intent, word of mouth

### Bottled tea drink consumers

Map requests here when the user mentions:

- Oriental Leaf
- sugar-free tea
- bottled oolong tea
- bottled tea drinks

### Home appliances

Map requests here when the user mentions brands or products such as:

- air conditioners, refrigerators, washing machines
- smart home devices, kitchen appliances

### Western spirits

Map requests here when the user mentions:

- whisky, wine, brandy, cocktails
- imported spirits, premium liquor

### Sportswear and sneakers

Map requests here when the user mentions brands or products such as:

- Nike, Adidas, Li-Ning, Anta
- running shoes, sports apparel, athleisure

### Beverages

Map requests here when the user mentions:

- soft drinks, energy drinks, juice
- Coca-Cola, Pepsi, Red Bull, Genki Forest

## `industry_hint` rule

If the host can confidently map the request into one supported industry, pass the normalized industry in `industry_hint`.

## `normalized_message` rule

Use `normalized_message` only when the original wording is noisy, brand-heavy, or likely to confuse backend classification. Preserve the user intent and product target.

## Unsupported handling

If the request cannot be mapped confidently into one supported industry, do not force backend execution. Return the unsupported-industry user-facing response instead.

## Notes on backend enums

Backend enum values may use canonical internal labels that are not English. Keep those exact values in code where required, but avoid non-English wording in skill documentation unless a backend-facing literal must be shown verbatim.
