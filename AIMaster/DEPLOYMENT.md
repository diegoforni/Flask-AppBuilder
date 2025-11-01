# AIMaster Flask-AppBuilder Deployment Guide

## Overview

This is a Flask-AppBuilder application that provides a backend API for a magic routine builder mobile app. It uses Flask-AppBuilder for authentication and user management, with custom API endpoints for routines, decks, and the "actuar" feature.

**Production URL**: https://d.cursodemagia.com.ar

## System Requirements

- **OS**: Ubuntu 20.04+ (tested on Ubuntu 20.04)
- **Python**: Python 3.8 (system Python, no venv)
- **Web Server**: Nginx (for HTTPS proxy)
- **Process Manager**: systemd with gunicorn

## Architecture

```
Internet → Nginx (HTTPS) → Gunicorn (port 5000) → Flask-AppBuilder App
                                                    ↓
                                                  app.db (SQLite)
```

## Installation Steps

### 1. Install System Dependencies

```bash
sudo apt update
sudo apt install -y python3 python3-pip nginx gunicorn
```

### 2. Install Python Packages (System-wide)

```bash
sudo pip3 install Flask-AppBuilder Flask-Cors requests
```

**Important**: Install packages system-wide (not in a venv) because the service runs with system Python 3.8.

### 3. Clone the Repository

```bash
cd /home/ubuntu
git clone git@github.com:diegoforni/Flask-AppBuilder.git
cd Flask-AppBuilder/AIMaster
```

### 4. Configure the Application

The main configuration is in `config.py`:

```python
# Database (SQLite)
SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(basedir, "app.db")

# Authentication
AUTH_TYPE = AUTH_DB  # Database authentication

# Secret key (change in production!)
SECRET_KEY = "aaaaaaaaaaaaaaaaaaaa"
```

### 5. Initialize the Database

On first run, Flask-AppBuilder will create the database and tables automatically:

```bash
cd /home/ubuntu/Flask-AppBuilder/AIMaster
python3 -c "from app import app; print('Database initialized')"
```

To create an admin user via Flask-AppBuilder CLI:

```bash
export FLASK_APP=app
flask fab create-admin
```

### 6. Set Up Systemd Service

Copy the service file:

```bash
sudo cp deploy/gunicorn.service /etc/systemd/system/gunicorn-flaskapp.service
```

**Service configuration** (`/etc/systemd/system/gunicorn-flaskapp.service`):

```ini
[Unit]
Description=Gunicorn instance to serve Flask App
After=network.target

[Service]
User=ubuntu
Group=www-data
WorkingDirectory=/home/ubuntu/Flask-AppBuilder/AIMaster
# Using system python3 without venv
ExecStart=/usr/bin/gunicorn --workers 3 --bind 0.0.0.0:5000 app:app

[Install]
WantedBy=multi-user.target
```

**Key points**:
- Runs as user `ubuntu`
- Uses system Python 3.8 (NOT venv)
- Binds to all interfaces on port 5000
- Starts `app:app` (Flask-AppBuilder backend)

Enable and start the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable gunicorn-flaskapp.service
sudo systemctl start gunicorn-flaskapp.service
sudo systemctl status gunicorn-flaskapp.service
```

### 7. Configure Nginx (HTTPS Proxy)

Create nginx configuration:

```bash
sudo nano /etc/nginx/sites-available/d.cursodemagia.conf
```

Example configuration:

```nginx
server {
    listen 443 ssl http2;
    server_name d.cursodemagia.com.ar;

    ssl_certificate /path/to/fullchain.pem;
    ssl_certificate_key /path/to/privkey.pem;

    location / {
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

server {
    listen 80;
    server_name d.cursodemagia.com.ar;
    return 301 https://$server_name$request_uri;
}
```

Enable the site:

```bash
sudo ln -s /etc/nginx/sites-available/d.cursodemagia.conf /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

## Database

The application uses **SQLite** with the database file at:
```
/home/ubuntu/Flask-AppBuilder/AIMaster/app.db
```

### Important Tables

- **ab_user**: Flask-AppBuilder users (email, password_hash, etc.)
- **credits**: User credits (separate table)
- **pending_credits**: Credits for users who haven't registered yet
- **routines**: Magic routines with nodes (JSON)
- **decks**: Card decks with order (JSON)
- **actuar**: User's latest actuar text

### Backup Database

```bash
cp /home/ubuntu/Flask-AppBuilder/AIMaster/app.db /home/ubuntu/Flask-AppBuilder/AIMaster/app.db.backup.$(date +%Y%m%d_%H%M%S)
```

## API Endpoints

### Authentication

- `POST /api/register` - Register new user
- `POST /api/login` - Login (returns token)
- `POST /api/logout` - Logout
- `GET /api/user` - Get current user info

### Routines

- `GET /api/routines` - List user's routines
- `POST /api/routines` - Create routine
- `GET /api/routines/<id>` - Get routine
- `PUT /api/routines/<id>` - Update routine
- `DELETE /api/routines/<id>` - Delete routine

### Decks

- `GET /api/decks` - List user's decks
- `POST /api/decks` - Create deck
- `GET /api/decks/<id>` - Get deck
- `PUT /api/decks/<id>` - Update deck
- `DELETE /api/decks/<id>` - Delete deck

### Actuar

- `POST /api/actuar` - Save actuar text (authenticated)
- `GET /api/actuar/<username>` - Get public actuar text

### Credits

- `GET /api/user/credits` - Get user credits
- `POST /api/user/credits` - Add/consume credits
- `POST /api/add-credits` - Admin endpoint to add credits (password: "daf")

## Troubleshooting

### Check Service Status

```bash
sudo systemctl status gunicorn-flaskapp.service
```

### View Logs

```bash
# Service logs
sudo journalctl -u gunicorn-flaskapp.service -f

# Nginx logs
sudo tail -f /var/log/nginx/error.log
sudo tail -f /var/log/nginx/access.log
```

### Test Locally

```bash
# Test app loads
cd /home/ubuntu/Flask-AppBuilder/AIMaster
python3 -c "from app import app; print('OK')"

# Test API endpoint
curl http://localhost:5000/api/actuar/diegof
```

### Common Issues

#### 1. Service fails with "ModuleNotFoundError"

**Solution**: Install missing packages system-wide:
```bash
sudo pip3 install Flask-AppBuilder Flask-Cors requests
```

#### 2. Service fails with "TypeError: 'type' object is not subscriptable"

**Cause**: Using venv with Python 3.9+ type hints on Python 3.8.

**Solution**: Use system Python 3.8 without venv (already configured in service file).

#### 3. Login returns 401 but user exists

**Cause**: Service running `backend.app:app` instead of `app:app`.

**Solution**: Check service file points to `app:app`:
```bash
sudo systemctl cat gunicorn-flaskapp.service | grep ExecStart
# Should show: ExecStart=/usr/bin/gunicorn --workers 3 --bind 0.0.0.0:5000 app:app
```

#### 4. Import error: "No module named 'flask_appbuilder.models.sqla.base'"

**Cause**: Incorrect import for Flask-AppBuilder 4.x.

**Solution**: Use `from flask_appbuilder.models.sqla import SQLA` instead of `from flask_appbuilder.models.sqla.base import SQLA`.

### Restart Service After Code Changes

```bash
sudo systemctl restart gunicorn-flaskapp.service
```

## Development

### Run Locally (Development Server)

```bash
cd /home/ubuntu/Flask-AppBuilder/AIMaster
python3 run.py
```

This will start Flask's development server on http://0.0.0.0:5000 (not recommended for production).

### Access Flask-AppBuilder Admin UI

Navigate to: https://d.cursodemagia.com.ar/

Login with admin credentials to manage users, roles, and permissions.

## File Structure

```
/home/ubuntu/Flask-AppBuilder/AIMaster/
├── app/
│   ├── __init__.py          # Main app initialization
│   ├── api.py               # API endpoints blueprint
│   ├── models.py            # Database models
│   ├── views.py             # Flask-AppBuilder views
│   ├── defaults.py          # Default routines
│   ├── static/
│   │   └── actuar/          # Static HTML files for actuar
│   └── templates/
├── backend/                 # Legacy backend (not used in production)
├── deploy/
│   ├── gunicorn.service     # Systemd service template
│   └── README.md            # Deployment instructions
├── config.py                # App configuration
├── requirements.txt         # Python dependencies
├── run.py                   # Development server entry point
└── app.db                   # SQLite database (production data)
```

## Production Checklist

- [ ] Change `SECRET_KEY` in `config.py`
- [ ] Set up SSL certificates for HTTPS
- [ ] Configure nginx properly
- [ ] Enable firewall (allow 80, 443, 22)
- [ ] Set up database backups
- [ ] Monitor disk space (SQLite database growth)
- [ ] Set up log rotation
- [ ] Test login with existing users
- [ ] Verify `/api/actuar/<username>` endpoints work

## Maintenance

### Update Code from Git

```bash
sudo -u ubuntu bash -c "cd /home/ubuntu/Flask-AppBuilder/AIMaster && git pull origin master"
sudo systemctl restart gunicorn-flaskapp.service
```

### Database Migration

If you need to add columns or tables, Flask-AppBuilder will attempt to create them automatically on startup. For manual migrations, use `flask db` commands or raw SQL.

### Monitoring

Check service is running:
```bash
sudo systemctl is-active gunicorn-flaskapp.service
```

Check listening ports:
```bash
sudo ss -ltnp | grep :5000
```

## Support

For issues or questions, contact the repository owner or check the GitHub repository:
https://github.com/diegoforni/Flask-AppBuilder

## License

[Specify license here]
