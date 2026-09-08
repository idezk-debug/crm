# Multi-Tenant CRM / Work Management SaaS

Django-based platform for companies to manage clients, staff, work tasks, file uploads, and subscription billing.

## Features

- Company self-registration with 7-day free trial
- Multi-tenant data isolation per company
- Client and staff management with admin-set passwords
- Work tracking with file uploads (auto-expire after 7 days)
- Manual billing flow with platform owner approval
- Platform owner dashboard for subscriptions

## Local Setup

### 1. Prerequisites

- Python 3.11+
- pip

### 2. Virtual environment

```bash
python -m venv env
# Windows
env\Scripts\activate
# Linux/macOS
source env/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Environment variables

Copy the example file and edit values:

```bash
copy .env.example .env
```

For local development, keep `DJANGO_DEBUG=True`. A dev-only secret key is used automatically when debug is on.

### 5. Database and geo data

```bash
python manage.py migrate
python manage.py cities_light
python manage.py createsuperuser
```

The superuser account is the **platform owner** (subscriptions, platform dashboard).

### 6. Run the server

```bash
python manage.py runserver
```

Open:

- Marketing site: http://127.0.0.1:8000/
- Company registration: http://127.0.0.1:8000/register-company/
- Login: http://127.0.0.1:8000/login/
- Django admin: http://127.0.0.1:8000/admin/

## Running Tests

```bash
python manage.py test MyApp
```

## Scheduled Cleanup

Expired notifications and work files are cleaned by a management command (not on every page load):

```bash
python manage.py cleanup_expired_work_files
```

Schedule daily:

- **Linux cron:** `0 2 * * * cd /path/to/project && /path/to/venv/bin/python manage.py cleanup_expired_work_files`
- **Windows Task Scheduler:** run the same command once per day

## Production Notes

- Set `DJANGO_DEBUG=False` and a strong `DJANGO_SECRET_KEY`
- Use PostgreSQL: set `DJANGO_DB_ENGINE=postgresql` and DB credentials in `.env`
- Configure SMTP email settings for welcome and payment emails
- Run `python manage.py collectstatic --noinput`
- See [DEPLOYMENT.md](DEPLOYMENT.md) for Gunicorn + Nginx setup

## User Roles

| Role | Login | Dashboard |
|------|-------|-----------|
| Platform owner | Superuser | `/admin/platform-dashboard/` |
| Company admin | Login ID or business email | `/staff/dashboard/` |
| Staff | Staff ID | `/staff/dashboard/` |
| Client | Client ID | `/client/dashboard/` |

## Project Structure

```
MyProject/          Django project settings
MyApp/              Main application
  models.py         Company, Client, Staff, Work, billing
  views.py          HTTP handlers
  templates/        HTML templates
  static/           CSS, JS, assets
  management/       Cleanup commands
DEPLOYMENT.md       Production deployment guide
```

## Optional Future Work

- Razorpay/Stripe payment gateway (env keys prepared in settings)
- Split `views.py` into smaller modules
- Trial-ending reminder emails (SMTP required)



## For My Reference

staff pass = staff@123
company pass = code@123
admin pass = admin@123