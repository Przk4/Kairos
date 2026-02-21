#!/usr/bin/env python
"""
Ver detalles de items en módulos problemáticos
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kairos_project.settings')
django.setup()

from tu_app.models import Module, ModuleItem
from django.contrib.auth.models import User

print("=" * 80)
print("[DETALLES] Items en módulos 4, 5, 6")
print("=" * 80)

user = User.objects.first()

for module_id in [4, 5, 6]:
    module = Module.objects.filter(id=module_id, course__user=user).first()
    if not module:
        continue
    
    print(f"\n📚 Módulo {module_id}: {module.name}")
    print("-" * 80)
    
    items = module.items.all()
    print(f"Total items: {items.count()}\n")
    
    for item in items:
        print(f"Item ID: {item.id}")
        print(f"  Título: {item.title}")
        print(f"  Tipo: {item.get_item_type_display()}")
        if item.url:
            print(f"  URL: {item.url[:80]}")
        print()

print("=" * 80)
