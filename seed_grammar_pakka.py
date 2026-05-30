"""
Seed sample GrammarPakkaItems for Unit 1.
Run with: python seed_grammar_pakka.py
"""
import django, os
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
django.setup()

from course.models import GrammarPakkaItem, Unit

unit = Unit.objects.get(id=1)
EXAM_CODE  = 'N5_G01'
EXAM_LEVEL = 5

ITEMS = [
    # ── Step 2: Builder ────────────────────────────────────────────────────
    dict(
        step_type=2, order=10, exam_code=EXAM_CODE, exam_level=EXAM_LEVEL,
        logic_formula="[N1] は [N2] です",
        english_prompt="I am a student.",
        correct_sentence="わたしはがくせいです",
        word_blocks="わたし,は,がくせい,です",
        particle_target="", distractors="",
        explanation_hint="Topic marker は goes between the subject and the description.",
    ),
    dict(
        step_type=2, order=20,
        logic_formula="[N1] は [N2] です",
        english_prompt="She is a teacher.",
        correct_sentence="かのじょはせんせいです",
        word_blocks="かのじょ,は,せんせい,です",
        particle_target="", distractors="",
        explanation_hint="Use は to mark the topic, then state what they are with です.",
    ),
    dict(
        step_type=2, order=30, exam_code=EXAM_CODE, exam_level=EXAM_LEVEL,
        logic_formula="[N1] は [N2] じゃありません",
        english_prompt="He is not a doctor.",
        correct_sentence="かれはいしゃじゃありません",
        word_blocks="かれ,は,いしゃ,じゃありません",
        particle_target="", distractors="",
        explanation_hint="じゃありません is the negative form — it replaces です at the end.",
    ),
    dict(
        step_type=2, order=40, exam_code=EXAM_CODE, exam_level=EXAM_LEVEL,
        logic_formula="... ですか",
        english_prompt="Are you a student?",
        correct_sentence="あなたはがくせいですか",
        word_blocks="あなた,は,がくせい,です,か",
        particle_target="", distractors="",
        explanation_hint="Questions end with ですか. The か particle always comes last.",
    ),
    dict(
        step_type=2, order=50, exam_code=EXAM_CODE, exam_level=EXAM_LEVEL,
        logic_formula="[N1] も [N2] です",
        english_prompt="I am also a student.",
        correct_sentence="わたしもがくせいです",
        word_blocks="わたし,も,がくせい,です",
        particle_target="", distractors="",
        explanation_hint="も means 'also/too'. It replaces は when adding another topic.",
    ),
    # ── Step 3: Heavy Loop ─────────────────────────────────────────────────
    dict(
        step_type=3, order=10, exam_code=EXAM_CODE, exam_level=EXAM_LEVEL,
        logic_formula="[N1] は [N2] です",
        english_prompt="I am a student.  →  わたし＿がくせいです",
        correct_sentence="わたしはがくせいです",
        word_blocks="",
        particle_target="は", distractors="が,を,も",
        explanation_hint="は is the topic marker — it marks what the sentence is about.",
    ),
    dict(
        step_type=3, order=20, exam_code=EXAM_CODE, exam_level=EXAM_LEVEL,
        logic_formula="[N1] も [N2] です",
        english_prompt="She is also a teacher.  →  かのじょ＿せんせいです",
        correct_sentence="かのじょもせんせいです",
        word_blocks="",
        particle_target="も", distractors="は,が,の",
        explanation_hint="も means 'also'. Use it instead of は when saying 'too/as well'.",
    ),
    dict(
        step_type=3, order=30, exam_code=EXAM_CODE, exam_level=EXAM_LEVEL,
        logic_formula="[N1] の [N2]",
        english_prompt="It's my book.  →  わたし＿ほんです",
        correct_sentence="わたしのほんです",
        word_blocks="",
        particle_target="の", distractors="は,も,に",
        explanation_hint="の connects a possessor to the thing owned — like 's in English.",
    ),
    # ── Step 4: Beast Mode ─────────────────────────────────────────────────
    dict(
        step_type=4, order=10, exam_code=EXAM_CODE, exam_level=EXAM_LEVEL,
        logic_formula="[N1] は [N2] じゃありません",
        english_prompt="He is not a doctor.",
        correct_sentence="かれはいしゃじゃありません",
        word_blocks="かれ,は,いしゃ,じゃありません",
        particle_target="", distractors="",
        explanation_hint="No hints this time — build it from memory!",
    ),
    dict(
        step_type=4, order=20, exam_code=EXAM_CODE, exam_level=EXAM_LEVEL,
        logic_formula="... ですか",
        english_prompt="Are you a student?",
        correct_sentence="あなたはがくせいですか",
        word_blocks="あなた,は,がくせい,です,か",
        particle_target="", distractors="",
        explanation_hint="Remember: sentence enders go last — verb (です) then か.",
    ),
]

created = 0
for d in ITEMS:
    obj, was_new = GrammarPakkaItem.objects.update_or_create(
        unit=unit,
        step_type=d['step_type'],
        english_prompt=d['english_prompt'],
        defaults={k: v for k, v in d.items() if k not in ('step_type', 'english_prompt')},
    )
    if was_new:
        created += 1

print(f"Done. {created} new items created, {len(ITEMS) - created} already existed.")
print(f"Total GrammarPakkaItems for Unit 1: {GrammarPakkaItem.objects.filter(unit=unit).count()}")
