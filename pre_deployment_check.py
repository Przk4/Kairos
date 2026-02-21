#!/usr/bin/env python
"""
PRE-DEPLOYMENT CHECKLIST
Ejecutar antes de hacer push a DigitalOcean
"""
import os
import sys

print("\n" + "="*80)
print("KAIROS - PRE-DEPLOYMENT CHECKLIST")
print("="*80 + "\n")

checks = []

# 1. .env debe estar en .gitignore (se valida más abajo)
if os.path.exists('.env'):
    print("✅ .env exists locally (checking .gitignore...)")
    checks.append(("Keep .env secure", True))  # Validación real abajo
else:
    print("ℹ️  .env not yet created (will be needed for local dev)")
    checks.append(("Keep .env secure", True))  # Not critical yet

# 2. requirements.txt
if os.path.exists('requirements.txt'):
    print("✅ requirements.txt exists")
    checks.append(("requirements.txt", True))
else:
    print("❌ requirements.txt missing - run: pip freeze > requirements.txt")
    checks.append(("requirements.txt", False))

# 3. .env.example
if os.path.exists('.env.example'):
    print("✅ .env.example exists (template para otros)")
    checks.append((".env.example template", True))
else:
    print("❌ .env.example missing")
    checks.append((".env.example template", False))

# 4. .gitignore has .env
if os.path.exists('.gitignore'):
    with open('.gitignore', 'r') as f:
        gitignore = f.read()
        if '.env' in gitignore:
            print("✅ .env in .gitignore (secrets protected)")
            checks.append((".gitignore has .env", True))
        else:
            print("❌ .env NOT in .gitignore - add it NOW")
            checks.append((".gitignore has .env", False))
else:
    print("❌ .gitignore missing")
    checks.append((".gitignore", False))

# 5. migrations folder
if os.path.exists('tu_app/migrations'):
    print("✅ migrations folder exists")
    checks.append(("migrations", True))
else:
    print("❌ migrations folder missing")
    checks.append(("migrations", False))

# 6. Django setup
try:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "kairos_project.settings")
    import django
    django.setup()
    from tu_app.models import ModuleEmbedding, Module, ModuleAnalysis
    
    embed_count = ModuleEmbedding.objects.count()
    module_count = Module.objects.count()
    
    print(f"✅ Django OK - {module_count} modules, {embed_count} embeddings in DB")
    checks.append(("Django & Database", True))
except Exception as e:
    print(f"❌ Django ERROR: {e}")
    checks.append(("Django & Database", False))

# 6. Static files
if os.path.exists('tu_app/static'):
    print("✅ Static files folder exists")
    checks.append(("Static files", True))
else:
    print("⚠️  Static files folder missing (may be ok if using S3)")
    checks.append(("Static files", True))  # Not critical

# 7. Git repository
if os.path.exists('.git'):
    print("✅ Git repository initialized")
    checks.append(("Git repo", True))
else:
    print("❌ Git repository NOT initialized - run: git init")
    checks.append(("Git repo", False))

# SUMMARY
print("\n" + "="*80)
print("SUMMARY")
print("="*80 + "\n")

passed = sum(1 for _, status in checks if status)
total = len(checks)

for check, status in checks:
    symbol = "✅" if status else "❌"
    print(f"{symbol} {check}")

print(f"\n{passed}/{total} checks passed\n")

if passed == total:
    print("🎉 READY FOR DEPLOYMENT!")
    print("\nNext steps:")
    print("1. git add . && git commit -m 'Ready for cloud deployment'")
    print("2. git push origin main")
    print("3. DigitalOcean App Platform will auto-deploy")
    print("4. Run on cloud: python manage.py migrate")
    sys.exit(0)
else:
    print("⚠️  FIX ISSUES ABOVE BEFORE DEPLOYING")
    sys.exit(1)
