# Course Import Documentation

## Overview

The BenGo administration panel now supports bulk import of Vocabulary Items and Grammar Content via Excel/CSV files.

## Exam Management

### Available Exams
- **N5** - JLPT N5 (Beginner)
- **N4** - JLPT N4 (Elementary)

### Adding New Exams
1. Navigate to `Administration > Exams` in the admin panel
2. Click "Add Exam"
3. Enter the exam code (e.g., N3, N2, N1)
4. Fill in name, description, and order
5. Save

## Vocabulary Import

### Access
1. Login to admin panel
2. Navigate to `Course > Vocabulary items`
3. Click "Import Excel/CSV" button at the top right

### File Format

**Required Columns (in order):**
1. `unit_number` - Unit number (whole number like 1,2,3; if missing, the Unit will be created automatically) (required)
2. `exam_code` - Exam code (e.g., N5, N4, optional)
3. `target` - Target word in Hiragana (required)
4. `correct` - Correct English translation (required)
5. `wrong1` - Wrong option 1 (required)
6. `wrong2` - Wrong option 2 (required)
7. `wrong3` - Wrong option 3 (required)

**Example CSV:**
```csv
unit_number,exam_code,target,correct,wrong1,wrong2,wrong3
1,N5,わたし,I / Me,Teacher,Student,Friend
1,N5,あなた,You,He,She,They
1,N5,せんせい,Teacher,Student,Doctor,Driver
```

**Example Excel:**
| unit_number | exam_code | target | correct | wrong1 | wrong2 | wrong3 |
|---------|-----------|--------|---------|--------|--------|--------|
| 1       | N5        | わたし | I / Me  | Teacher| Student| Friend |
| 1       | N5        | あなた | You     | He     | She    | They   |

### Notes
- The system automatically shuffles options and calculates the `correct_answer` field
- Existing items with the same `unit` and `target` will be updated
- Leave `exam_code` empty if not applicable
- The import will skip rows with missing required fields

## Grammar Import

### Access
1. Login to admin panel
2. Navigate to `Course > Grammar contents`
3. Click "Import Excel/CSV" button at the top right

### File Format

**Required Columns (in order):**
1. `unit_number` - Unit number (whole number like 1,2,3; if missing, the Unit will be created automatically) (required)
2. `exam_code` - Exam code (e.g., N5, N4, optional)
3. `title` - Grammar topic title (required)
4. `content` - Full grammar explanation and examples (required)

**Example CSV:**
```csv
unit_number,exam_code,title,content
1,N5,Basic Sentence Pattern,"[Noun 1] は [Noun 2] です

Examples:
わたしは がくせいです。"
1,N5,Particle は (wa),"The particle は marks the topic.

Examples:
わたしは アメリカじんです。"
```

**Example Excel:**
| unit_number | exam_code | title                    | content                                    |
|---------|-----------|--------------------------|-------------------------------------------|
| 1       | N5        | Basic Sentence Pattern   | [Noun 1] は [Noun 2] です...              |
| 1       | N5        | Particle は (wa)         | The particle は marks the topic...        |

### Notes
- Existing items with the same `unit` and `title` will be updated
- Leave `exam_code` empty if not applicable
- Content can include multi-line text with examples
- The import will skip rows with missing required fields

## Grammar Learn Import (Lean Page)

This import powers the **Grammar → Learn** page (interactive sections rendered by `visual_type`).

### Access

This import runs via a management command (not the Django admin import button).

### Command

```bash
# Use your project virtualenv Python if available
# Example (from repo root): .\.venv\Scripts\python.exe backend\manage.py import_grammar_learn backend\sample_grammar_learn_import.csv --dry-run

python manage.py import_grammar_learn backend/sample_grammar_learn_import.csv --dry-run
python manage.py import_grammar_learn backend/sample_grammar_learn_import.csv
```

### File Format

Grammar Learn uses **one row per teaching point**.

**Required columns:**
- `exam_code` (required; always use this for filtering, e.g. `N5_G02`)
- `unit_id` (required; must exist)
- `title` (required)

**Recommended columns:**
- `exam_level` (integer; use `5` for N5, `4` for N4)
- `topic_order` (integer; controls ordering on the Learn page)
- `logic_formula` (string; e.g. `[N1] の [N2]`)
- `explanation` (text; punchy “why”)
- `example_jp` (string)
- `example_en` (string)
- `visual_type` (string; UI trigger like `Distance_Map`, `Particle_Link`, `Tense_Shift`)
- `pakka_tip` (text; Sensei tip)

## Grammar Pakka Import (Quiz 4-Step Flow)

This import powers the **Grammar → Quiz** and **Grammar → Pakka Adaptive** pages (4-phase mastery system).

### Access

This import runs via a management command (not the Django admin import button).

### Command

```bash
# Use your project virtualenv Python if available
python manage.py import_grammar_pakka backend/sample_grammar_pakka_import.csv --dry-run
python manage.py import_grammar_pakka backend/sample_grammar_pakka_import.csv
```

### File Format

Grammar Pakka uses **one row per step per teaching point** (typically 4 rows: Blueprint/Builder/Heavy Loop/Beast Mode).

**Required columns:**
- `exam_code` (required; always use this for filtering, e.g. `N5_G02`)
- `unit_id` (required; must exist)
- `step_type` (required; `1` = Blueprint, `2` = Builder, `3` = Heavy Loop, `4` = Beast Mode)
- `english_prompt` (required)
- `correct_sentence` (required; the full Japanese answer)

**Recommended columns:**
- `exam_level` (integer; use `5` for N5, `4` for N4)
- `logic_formula` (string; e.g. `[N1] の [N2]` for step 1)
- `word_blocks` (CSV string; e.g. `ミラーさん,の,ほん,です` for step 2)
- `particle_target` (string; the correct particle for step 3, e.g. `の`)
- `distractors` (CSV string; wrong options for step 3, e.g. `は,を,も`)
- `explanation_hint` (text; feedback shown when user makes a mistake)

### Step-Specific Usage

- **Step 1 (Blueprint)**: Show `logic_formula` + `correct_sentence` + `explanation_hint`
- **Step 2 (Builder)**: User drags `word_blocks` to build the sentence
- **Step 3 (Heavy Loop)**: User picks from `[particle_target, ...distractors]`; wrong answers re-queue
- **Step 4 (Beast Mode)**: User types the full sentence from memory

## Getting Unit Numbers

Use the numeric unit number you want (e.g., 1, 2, 3). If the Unit does not exist yet, it will be created automatically during import.

## Troubleshooting

### Common Errors

**"File must have X columns"**
- Ensure your CSV/Excel has the exact number of columns required
- Don't skip columns - use empty values if optional

**"Missing dependency: pandas"**
- Contact system administrator to install pandas library

**Items showing as "skipped"**
- Check that `unit_id` exists in the database
- Verify all required fields are filled
- Check for invalid exam codes

### Import Results

After import, you'll see a success message showing:
- **Created**: New items added
- **Updated**: Existing items modified
- **Skipped**: Rows that couldn't be processed

## Sample Files

Sample import files are available in the backend directory:
- `sample_vocabulary_import.csv` - Vocabulary example
- `sample_grammar_import.csv` - Grammar example
- `sample_grammar_learn_import.csv` - Grammar Learn (Lean Page) example (update `unit_id` for your DB)
- `sample_grammar_pakka_import.csv` - Grammar Pakka (Quiz 4-step flow) example

## Best Practices

1. **Test with small files first** - Import 2-3 items to verify format
2. **Backup before bulk import** - Always backup your database
3. **Use consistent formatting** - Keep exam codes uppercase (N5, N4)
4. **Validate data** - Review imported data in admin after import
5. **Use UTF-8 encoding** - Ensure proper Japanese character support

## Future Enhancements

Planned features:
- Export functionality
- Validation preview before import
- Batch delete options
- Import history tracking
