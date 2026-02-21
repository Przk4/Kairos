# 🎯 QUICK DEPLOY GUIDE

**Copy-paste these commands to deploy to DigitalOcean**

---

## Step 1: Commit and Push to GitHub

```powershell
# Review changes
git status

# Stage all changes
git add .

# Commit
git commit -m "Cloud ready: Database-backed embeddings, centralized state sync"

# Push to main branch
git push origin main
```

---

## Step 2: Create Resources on DigitalOcean

### 2.1 Create PostgreSQL Database

Go to: https://cloud.digitalocean.com/databases

1. Click "Create Database"
2. Choose PostgreSQL
3. Select version 15.x
4. Size: **1 GB ($15/month)**
5. Datacenter: Choose your region
6. You'll get credentials like:
   ```
   Host: db-xyz.ondigitalocean.com
   Port: 25060
   Database: defaultdb
   Username: doadmin
   Password: <random-password>
   ```

---

### 2.2 Create DigitalOcean App Platform

Go to: https://cloud.digitalocean.com/apps

1. Click "Create App"
2. Connect GitHub account (if not already)
3. Select your repository: `<your-user>/Kairos`
4. Choose main branch
5. Auto-detect settings (or manually choose):
   - Framework: Django
   - Build command: (leave blank)
   - Run command: `gunicorn kairos_project.wsgi:application --bind 0.0.0.0:8080`
6. Click "Next"

---

### 2.3 Add Environment Variables

In App Platform, go to Settings → "Edit" → Environment

Add these variables (values from your local `.env`):

```
DEBUG=False
ALLOWED_HOSTS=<your-app>.ondigitalocean.app
SECRET_KEY=<your-django-secret-key>
DATABASE_URL=postgresql://doadmin:<password>@db-xyz.ondigitalocean.com:25060/defaultdb?sslmode=require
CANVAS_CLIENT_ID=<your-canvas-id>
CANVAS_CLIENT_SECRET=<your-canvas-secret>
DEEPSEEK_API_KEY=<your-deepseek-key>
```

**How to get each value**:
- `DATABASE_URL`: From PostgreSQL cluster page
- `SECRET_KEY`: Run `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`
- Other keys: From your `.env` file

---

### 2.4 Deploy App

1. Click "Deploy"
2. Wait 15-20 minutes for build and deploy
3. App will be live at: `https://<your-app>.ondigitalocean.app`

---

## Step 3: Final Setup (Run on Cloud)

Once app is deployed, open a terminal on the app:

```bash
# Run migrations
python manage.py migrate

# Create admin account
python manage.py createsuperuser
# Follow prompts for username/password

# Verify status
python manage.py check
```

---

## Step 4: Test Your App

1. Open: `https://<your-app>.ondigitalocean.app`
2. Login with superuser account
3. Navigate to a module
4. Click "Analizar Módulo" to test RAG
5. Check if embeddings load from database

**Expected**: Everything works exactly like local dev!

---

## ✅ Verify Everything Works

### Test Checklist

- [ ] App loads at DigitalOcean URL
- [ ] Admin login works
- [ ] Can access modules
- [ ] Module analysis works (calls DeepSeek API)
- [ ] Embeddings load without filesystem errors
- [ ] Database queries are fast

### If Something Breaks

1. **Check logs**: App Platform → Logs
2. **Common errors**:
   - `ModuleNotFoundError: No module named 'module'` → Missing `requirements.txt`
   - `Database connection refused` → Check `DATABASE_URL`
   - `DisallowedHost` → Check `ALLOWED_HOSTS` has your domain
   - `No such table` → Migrations didn't run

3. **Re-run migrations on cloud**:
   ```bash
   heroku run "python manage.py migrate" --app=<app-name>
   # or use DigitalOcean CLI
   doctl apps exec <app-id> -- python manage.py migrate
   ```

---

## 💾 Backup Your Database

On DigitalOcean, go to your PostgreSQL cluster:

**Backups** tab → Enable automatic backups (automatic by default)

This saves your data if anything goes wrong.

---

## 🎉 You're Done!

Your Kairos app is now:
- ✅ Running on the cloud
- ✅ Using PostgreSQL (not local SQLite)
- ✅ Auto-deploying on GitHub push
- ✅ Backed up automatically

---

## 📊 Monitor Your App

After a few days, check:

1. **Logs**: App Platform → Logs (look for errors)
2. **CPU/Memory**: Usually < 50%
3. **Database**: PostgreSQL page shows query count
4. **Uptime**: Should be 99.9%+

---

## 🔒 Security Notes

**NEVER share**:
- `.env` file
- `DATABASE_URL`
- `SECRET_KEY`
- API keys

These are already protected:
- ✅ `.env` in `.gitignore`
- ✅ Environment variables stored securely in DigitalOcean
- ✅ Database password encrypted

---

## 💰 Billing

You'll be charged:
- PostgreSQL: $15/month
- App Platform: $12/month
- **Total: $27/month**

Check your DigitalOcean billing dashboard after 48 hours.

---

## 📞 Need Help?

If deployment fails:
1. Check `pre_deployment_check.py` ran successfully locally
2. Verify environment variables in DigitalOcean match your `.env`
3. Check App logs for specific error message
4. Make sure `requirements.txt` was created: `ls -la requirements.txt`

---

**Summary**: 4 steps, ~20 minutes, cloud deployment complete! 🚀
