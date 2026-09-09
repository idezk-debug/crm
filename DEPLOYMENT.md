# SaaS Deployment Guide (Django)

This project now supports:
- Company self-registration
- 7-day free trial
- Billing submission by company admin
- Platform owner approval to extend paid access
- Multi-company usage with strict tenant separation

## Render Deployment (existing services)

Since the Render web service and PostgreSQL database already exist, reuse them. Do not create another database or apply the blueprint as a new service.

In the existing Render web service, configure:

```text
Build Command: pip install -r requirements.txt && bash build.sh
Start Command: gunicorn MyProject.wsgi:application --bind 0.0.0.0:$PORT --workers 2
```

Add the existing Render PostgreSQL connection string to the web service as `DATABASE_URL`. Also set `DJANGO_SECRET_KEY` to a strong secret and `DJANGO_DEBUG=False`. The existing database remains the source of production data.

The build script automatically runs `collectstatic`, migrations, and `cities_light`, so no Render Shell or Pre-Deploy Command is required. Leave the Pre-Deploy Command empty if the field is locked on your plan.

Because the free tier does not provide Render Shell access, create the first admin account locally using the Render database URL. In PowerShell, run:

```powershell
$env:DATABASE_URL="paste-your-render-postgresql-url-here"
& .\env\Scripts\python.exe manage.py createsuperuser
Remove-Item Env:DATABASE_URL
```

Use the Render PostgreSQL **External Database URL** temporarily, and never commit it to Git.

The repository includes `render.yaml` as a reference for these web-service settings; its `DATABASE_URL` is intentionally entered manually so it does not create or replace your existing database.

After deployment, open the existing service URL. Create the platform owner locally using the hosted database procedure above.

For a custom domain, add these Render environment variables:

```text
DJANGO_ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
```

Render web-service disks are ephemeral. Uploaded work files and company logos stored in `media/` can be lost during a redeploy or restart. Use persistent object storage such as Amazon S3 or Cloudinary before relying on production uploads.

The included Render blueprint uses the free PostgreSQL plan when available. Choose a paid database for production workloads and backups.

## 1. Prepare Server (Ubuntu example)

```bash
sudo apt update
sudo apt install -y python3-venv python3-pip nginx
```

## 2. Upload Project

Copy this project folder to server, e.g. `/var/www/site_app`.

## 3. Create Virtual Environment

```bash
cd /var/www/site_app
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 4. Environment Variables

Set these in the server environment or in the project-root `.env` file for self-hosted deployments. Django loads `.env` automatically:

```bash
export DJANGO_SECRET_KEY="your-strong-secret"
export DJANGO_DEBUG="False"
export DJANGO_ALLOWED_HOSTS="yourdomain.com,www.yourdomain.com"
export DJANGO_CSRF_TRUSTED_ORIGINS="https://yourdomain.com,https://www.yourdomain.com"

# PostgreSQL (recommended for production)
export DJANGO_DB_ENGINE="postgresql"
export DJANGO_DB_NAME="site_app"
export DJANGO_DB_USER="postgres"
export DJANGO_DB_PASSWORD="your-db-password"
export DJANGO_DB_HOST="localhost"
export DJANGO_DB_PORT="5432"

# Email (SMTP)
export EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend"
export EMAIL_HOST="smtp.example.com"
export EMAIL_PORT="587"
export EMAIL_HOST_USER="noreply@yourdomain.com"
export EMAIL_HOST_PASSWORD="your-email-password"
export DEFAULT_FROM_EMAIL="noreply@yourdomain.com"
```

## 5. Run Migrations + Static Files + Geo Data

```bash
python manage.py migrate
python manage.py cities_light
python manage.py collectstatic --noinput
python manage.py createsuperuser
```

These commands are for self-hosted deployments or local development. Render runs the first three automatically from `build.sh`; use the local PowerShell procedure above for `createsuperuser` because the free tier has no Shell access.

## 6. Gunicorn Service

Create `/etc/systemd/system/site_app.service`:

```ini
[Unit]
Description=Gunicorn for site_app
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/site_app
Environment="DJANGO_SECRET_KEY=your-strong-secret"
Environment="DJANGO_DEBUG=False"
Environment="DJANGO_ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com"
Environment="DJANGO_CSRF_TRUSTED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com"
ExecStart=/var/www/site_app/.venv/bin/gunicorn MyProject.wsgi:application --bind 127.0.0.1:8000 --workers 3

[Install]
WantedBy=multi-user.target
```

Then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable site_app
sudo systemctl restart site_app
sudo systemctl status site_app
```

## 7. Nginx Reverse Proxy

Create `/etc/nginx/sites-available/site_app`:

```nginx
server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;

    location /static/ {
        alias /var/www/site_app/staticfiles/;
    }

    location /media/ {
        alias /var/www/site_app/media/;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Enable:

```bash
sudo ln -s /etc/nginx/sites-available/site_app /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

## 8. Add HTTPS

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com
```

## 9. SaaS Flow

1. Company registers from `/register-company/`
2. Trial starts instantly for 7 days
3. After trial expiry, company workspace is redirected to `/company/billing/`
4. Company admin submits payment request with transaction reference
5. Platform owner approves payment from `/admin/subscriptions/`
6. Access extends by 30 days per approved payment

## 10. Production Recommendation

- Use PostgreSQL (`DJANGO_DB_ENGINE=postgresql`) before scaling to many companies.
- Schedule daily cleanup:

```bash
# crontab example (2 AM daily)
0 2 * * * cd /var/www/site_app && /var/www/site_app/.venv/bin/python manage.py cleanup_expired_work_files
```

This removes expired notifications and work files from disk and database.
