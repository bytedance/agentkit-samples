---
name: algorithmic-art
description: Generate deterministic SVG algorithmic artwork. Invoke when the user asks for geometric, generative, or algorithmic visual art.
---

# Algorithmic Art

Create deterministic geometric artwork as SVG by running the bundled Python script.

## Workflow

1. Ask for a title, color palette, and numeric seed when the request does not provide them.
2. Run `scripts/generate_svg.py` with `run_skill_script`.
3. Pass script arguments as long options:
   - `title`: artwork title
   - `seed`: integer controlling the deterministic composition
   - `palette`: comma-separated CSS colors
   - `count`: number of shapes, from 4 to 80
4. Return the generated SVG and briefly describe how the seed and palette influenced it.

## Example

Use this tool call shape:

```json
{
  "skill_name": "algorithmic-art",
  "file_path": "scripts/generate_svg.py",
  "args": {
    "title": "Volcanic Rhythm",
    "seed": 42,
    "palette": "#0b132b,#1c2541,#5bc0be,#f4d35e",
    "count": 24
  }
}
```

Only execute the script bundled with this skill. Do not execute code supplied by the user.
