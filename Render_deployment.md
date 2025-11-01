# 🚀 Flask App Deployment on Render (with PostgreSQL, Environment Variables, and Cloudinary)

## 1. Project Setup
- **Main file:** `main.py`
- **Flask instance:** `app`
- **Backend:** Flask + SQLAlchemy
- **Database:** PostgreSQL (hosted on Render)
- **Media Storage:** Cloudinary (for permanent image storage)
- **Deployment platform:** Render

## 2. Required Files
### Procfile
```
web: gunicorn main:app
```

### requirements.txt
```
Flask
gunicorn
SQLAlchemy
psycopg2-binary
requests
jinja2
python-dotenv
cloudinary
flask_sqlalchemy
```

### runtime.txt
```
python-3.11.5
```

### (Optional) .render.yaml
```yaml
services:
  - type: web
    name: parking-system
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: gunicorn main:app
    plan: free
    envVars:
      - key: DATABASE_URL
        fromDatabase:
          name: parking-db
          property: connectionString
      - key: SECRET_KEY
        value: your-secret-key
      - key: DEBUG
        value: false
      - key: CLOUDINARY_CLOUD_NAME
        value: dgpahvl9m
      - key: CLOUDINARY_API_KEY
        value: 397185777883491
      - key: CLOUDINARY_API_SECRET
        sync: false

  - type: postgres
    name: parking-db
    plan: free
```

## 3. Environment Variables
In Render Dashboard → **Environment → Environment Variables**, add:
| Variable | Example Value | Description |
|-----------|----------------|-------------|
| `DATABASE_URL` | (auto from Render) | PostgreSQL connection string |
| `SECRET_KEY` | your-random-secret | Flask secret key |
| `DEBUG` | false | disable debug mode |
| `FLASK_ENV` | production | Flask environment |
| `CLOUDINARY_CLOUD_NAME` | dgpahvl9m | Cloudinary cloud name |
| `CLOUDINARY_API_KEY` | 397185777883491 | Cloudinary API key |
| `CLOUDINARY_API_SECRET` | your-secret-key | Cloudinary API secret |

## 4. Cloudinary Integration
We use **Cloudinary** to store uploaded images permanently since Render’s local storage is **not persistent**.

Safe configuration method:
```python
import cloudinary
import os

cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET")
)
```

Example upload usage:
```python
upload_result = cloudinary.uploader.upload(file)
image_url = upload_result['secure_url']
```

## 5. Steps to Deploy
1. Push your Flask project to **GitHub**.
2. Go to [https://render.com](https://render.com).
3. Create a **New Web Service** and connect your repo.
4. Render auto-detects Python.
5. Use:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn main:app`
6. Add a **PostgreSQL Database** and link it.
7. Add all **Environment Variables** (including Cloudinary keys).
8. Click **Deploy** — Render installs dependencies, sets up your DB, and starts your app.

## 6. Testing
- Visit your Render app URL.
- Upload an image → verify it’s stored on Cloudinary.
- Check logs on Render for any config issues.
