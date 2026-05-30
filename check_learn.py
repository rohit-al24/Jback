import django, os
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
django.setup()
from course.models import GrammarLearnItem, Unit

u = Unit.objects.first()
print('First unit:', u, 'id=', u.id if u else None)
for it in GrammarLearnItem.objects.filter(unit=u)[:10]:
    print(f'  lid={it.id} title={it.title!r} char={it.main_character!r} formula={it.logic_formula!r}')
