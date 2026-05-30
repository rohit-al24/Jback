import django, os
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
django.setup()
from django.db import connection
c = connection.cursor()
c.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in c.fetchall()]
print("All tables:")
for t in sorted(tables):
    print(" ", t)

print("\nGrammar-related tables:")
for t in tables:
    if 'grammar' in t.lower() or 'pakka' in t.lower():
        c2 = connection.cursor()
        c2.execute(f'SELECT COUNT(*) FROM "{t}"')
        print(f"  {t}: {c2.fetchone()[0]} rows")
