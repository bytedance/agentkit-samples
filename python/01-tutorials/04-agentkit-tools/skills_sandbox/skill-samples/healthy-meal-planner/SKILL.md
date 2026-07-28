---
name: healthy-meal-planner
description: A comprehensive meal planning tool for creating customized weekly meal plans based on dietary preferences, budget constraints, cooking time limits, and nutritional requirements. Use when users need personalized meal plans for specific diets (vegan, vegetarian, omnivore), budget targets, cooking time restrictions, or fitness goals (muscle gain, weight loss, maintenance).
---

# Healthy Meal Planner

## Overview

This skill helps users create customized weekly meal plans tailored to their specific needs, including dietary restrictions, budget limits, cooking time constraints, and fitness goals. The planner generates balanced meal plans with nutritional information, ingredient lists, and simple recipes.

## Core Capabilities

### 1. Dietary Preferences Support
- Vegan, vegetarian, omnivore, pescatarian, keto, paleo, gluten-free, dairy-free diets
- Custom ingredient exclusions (e.g., no mushrooms, no nuts)

### 2. Budget Planning
- Set weekly or daily budget limits
- Generate cost-effective meal plans using affordable ingredients
- Provide detailed cost breakdowns per meal and weekly total

### 3. Time Constraints
- Quick meals (under 30 minutes)
- Advanced prep options
- Batch cooking recommendations

### 4. Fitness Goals
- Muscle gain (high protein)
- Weight loss (calorie deficit)
- Maintenance (balanced nutrition)
- Custom macro targets

## Workflow

### Step 1: Gather User Requirements
When a user requests a meal plan, ask for:
1. Number of people
2. Dietary preferences and restrictions
3. Weekly budget
4. Maximum cooking time per meal
5. Fitness goals (if any)
6. Ingredient exclusions

### Step 2: Generate Meal Plan
Use the gathered information to create a 7-day meal plan including:
- Breakfast, lunch, dinner, and optional snacks
- Detailed recipes with cooking instructions
- Ingredient shopping list organized by store section
- Nutritional information per meal and daily totals
- Cost breakdown per meal and weekly total

### Step 3: Review and Adjust
Present the meal plan to the user and offer adjustments:
- Swap specific meals
- Adjust portion sizes
- Modify recipes based on available ingredients
- Update budget or time constraints

## Example Usage

**User Request:**
"Create a 7-day vegan meal plan for 2 people with $350 weekly budget, all meals under 30 minutes, no mushrooms, focused on muscle gain."

**Response:**
Generate a complete weekly plan with:
- High-protein vegan meals (tofu, tempeh, lentils, chickpeas, seitan)
- 30-minute or less preparation time
- Detailed ingredient list with cost estimates
- Nutritional info highlighting protein content
- Simple cooking instructions

## Reference Files

- `vegan_protein_sources.md`: Comprehensive list of high-protein vegan ingredients and their costs
- `quick_meal_recipes.md`: Collection of 30-minute or less recipes for various diets
- `budget_ingredient_guide.md`: Tips for creating cost-effective meal plans

## Resources

This skill includes example resource directories that demonstrate how to organize different types of bundled resources:

### scripts/
Executable code (Python/Bash/etc.) that can be run directly to perform specific operations.

**Examples from other skills:**
- PDF skill: `fill_fillable_fields.py`, `extract_form_field_info.py` - utilities for PDF manipulation
- DOCX skill: `document.py`, `utilities.py` - Python modules for document processing

**Appropriate for:** Python scripts, shell scripts, or any executable code that performs automation, data processing, or specific operations.

**Note:** Scripts may be executed without loading into context, but can still be read by Claude for patching or environment adjustments.

### references/
Documentation and reference material intended to be loaded into context to inform Claude's process and thinking.

**Examples from other skills:**
- Product management: `communication.md`, `context_building.md` - detailed workflow guides
- BigQuery: API reference documentation and query examples
- Finance: Schema documentation, company policies

**Appropriate for:** In-depth documentation, API references, database schemas, comprehensive guides, or any detailed information that Claude should reference while working.

### assets/
Files not intended to be loaded into context, but rather used within the output Claude produces.

**Examples from other skills:**
- Brand styling: PowerPoint template files (.pptx), logo files
- Frontend builder: HTML/React boilerplate project directories
- Typography: Font files (.ttf, .woff2)

**Appropriate for:** Templates, boilerplate code, document templates, images, icons, fonts, or any files meant to be copied or used in the final output.

---

**Any unneeded directories can be deleted.** Not every skill requires all three types of resources.
