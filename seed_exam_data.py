# Seed script for Exam data (N5, N4)
# Run this in Django shell: Get-Content seed_exam_data.py | python manage.py shell

from administration.models import Exam

# Create N5 Exam
n5, created = Exam.objects.get_or_create(
    code='N5',
    defaults={
        'name': 'JLPT N5',
        'description': 'Japanese Language Proficiency Test Level N5 (Beginner)',
        'is_active': True,
        'order': 1,
    }
)
if created:
    print(f"✓ Created: {n5.code} - {n5.name}")
else:
    print(f"ℹ Already exists: {n5.code} - {n5.name}")

# Create N4 Exam
n4, created = Exam.objects.get_or_create(
    code='N4',
    defaults={
        'name': 'JLPT N4',
        'description': 'Japanese Language Proficiency Test Level N4 (Elementary)',
        'is_active': True,
        'order': 2,
    }
)
if created:
    print(f"✓ Created: {n4.code} - {n4.name}")
else:
    print(f"ℹ Already exists: {n4.code} - {n4.name}")

print("\n✓ Exam data seeding completed!")
print("Available exam codes: N5, N4")
