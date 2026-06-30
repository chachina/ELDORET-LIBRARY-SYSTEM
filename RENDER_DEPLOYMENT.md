# Render Free Deployment

This app is ready for Render Free.

## Settings

- Environment: Python
- Build command: `pip install -r requirements.txt`
- Start command: `gunicorn app:app`
- Plan: Free

## Environment variable

- `SECRET_KEY`: Render can auto-generate this from `render.yaml`.

## Notes

- This app uses SQLite (`library.db`). On Render Free this is acceptable for demo/submission links, but not for permanent production data because disk can reset after redeploys/restarts.
- Demo admin login:
  - Email: `admin@library.co.ke`
  - Password: `admin123`
