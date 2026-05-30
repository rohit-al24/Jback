import django, os
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
django.setup()
from django.db import connection
c = connection.cursor()
c.execute("SELECT sql FROM sqlite_master WHERE type='index' AND tbl_name='core_grammarpakkaitem'")
for row in c.fetchall():
    print(row[0])
    print()
c.execute("SELECT sql FROM sqlite_master WHERE type='table' AND tbl_name='core_grammarpakkaitem'")
print("TABLE:")
for row in c.fetchall():
    print(row[0])
