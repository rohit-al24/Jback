# Sample data for testing the Course system
# Run this in Django shell: python manage.py shell < seed_course_data.py

from course.models import Level, Unit, VocabularyItem, GrammarContent

# Create Level 1
level1, _ = Level.objects.get_or_create(
    level_number=1,
    defaults={
        'name': 'Beginner Japanese',
        'description': 'Introduction to Japanese language basics',
        'is_active': True,
        'order': 1,
    }
)

# Create Unit 1 for Level 1
unit1, _ = Unit.objects.get_or_create(
    level=level1,
    unit_number=1,
    defaults={
        'name': 'Greetings and Self-Introduction',
        'description': 'Learn basic greetings and how to introduce yourself',
        'is_active': True,
        'order': 1,
    }
)

# Add vocabulary items for Unit 1
vocab_data = [
    {'target': 'わたし', 'correct': 'I / Me', 'wrong1': 'Teacher', 'wrong2': 'Student', 'wrong3': 'Friend'},
    {'target': 'あなた', 'correct': 'You', 'wrong1': 'He', 'wrong2': 'She', 'wrong3': 'They'},
    {'target': 'せんせい', 'correct': 'Teacher', 'wrong1': 'Student', 'wrong2': 'Doctor', 'wrong3': 'Driver'},
    {'target': 'がくせい', 'correct': 'Student', 'wrong1': 'Teacher', 'wrong2': 'Doctor', 'wrong3': 'Worker'},
    {'target': 'にほん', 'correct': 'Japan', 'wrong1': 'China', 'wrong2': 'Korea', 'wrong3': 'America'},
    {'target': 'アメリカ', 'correct': 'America', 'wrong1': 'Japan', 'wrong2': 'Canada', 'wrong3': 'England'},
]

for idx, data in enumerate(vocab_data):
    VocabularyItem.objects.get_or_create(
        unit=unit1,
        target=data['target'],
        defaults={
            'correct': data['correct'],
            'wrong1': data['wrong1'],
            'wrong2': data['wrong2'],
            'wrong3': data['wrong3'],
            'order': idx + 1,
        }
    )

# Add grammar content for Unit 1
grammar_items = [
    {
        'title': 'Basic Sentence Pattern: Noun 1 wa Noun 2 desu',
        'content': '''The most basic sentence pattern in Japanese:

[Noun 1] は [Noun 2] です
(Noun 1 wa Noun 2 desu)

は (wa) - topic particle
です (desu) - copula (to be)

Examples:
わたしは がくせいです。
(Watashi wa gakusei desu.)
I am a student.

せんせいは にほんじんです。
(Sensei wa nihonjin desu.)
The teacher is Japanese.'''
    },
    {
        'title': 'Particle は (wa)',
        'content': '''The particle は (written "ha" but pronounced "wa") marks the topic of the sentence.

Topic: What the sentence is about
は: Topic marker particle

Structure:
[Topic] は [Comment]

Examples:
わたしは アメリカじんです。
(I am American.)

これは ほんです。
(This is a book.)'''
    },
    {
        'title': 'Polite Form: です (desu)',
        'content': '''です (desu) is the polite copula meaning "to be" or "is/am/are".

Always use です in polite/formal situations:
✓ わたしは せんせいです。
  (I am a teacher.)

Casual form だ (da) - use only with close friends:
わたしは せんせいだ。'''
    }
]

for idx, item in enumerate(grammar_items):
    GrammarContent.objects.get_or_create(
        unit=unit1,
        title=item['title'],
        defaults={
            'content': item['content'],
            'order': idx + 1,
        }
    )

print(f"✓ Created Level 1: {level1.name}")
print(f"✓ Created Unit 1: {unit1.name}")
print(f"✓ Added {len(vocab_data)} vocabulary items")
print(f"✓ Added {len(grammar_items)} grammar topics")
print("\nSample course data created successfully!")
print("Visit /app/course in the frontend to see the results.")
