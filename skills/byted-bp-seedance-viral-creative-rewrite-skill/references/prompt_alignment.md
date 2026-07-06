# Prompt Alignment

This skill intentionally keeps prompt structure aligned with `meta-ads-creative-skill`.

## Reused Alignment

- Video analysis prompt keeps the same schema family:
  - `summary`
  - `style`
  - `structure`
  - `segments`
  - `editable_points`
- Rewrite planning prompt keeps the same output style as the old variant-plan stage:
  - structured JSON
  - storyboard block
  - prompt package block
  - constraints around hook, pacing, product proof, CTA

## Simplification

The main simplification is scope:

- old flow: multiple variants + generation + evaluation
- new flow: one rewrite plan + one rewritten video output

## Practical Effect

This keeps the language model instructions familiar and stable while making the delivered package much smaller and easier to operate.
