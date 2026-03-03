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
