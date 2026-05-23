# Render Backend Deployment

## Render service settings

Use the root `render.yaml` blueprint, or create a Web Service manually with:

```txt
Root Directory: Backend
Build Command: pip install -r requirements.txt
Start Command: uvicorn main:app --host 0.0.0.0 --port $PORT
Health Check Path: /health
```

## Required environment variables

```txt
MONGODB_URI=mongodb+srv://<user>:<password>@<cluster-url>/?retryWrites=true&w=majority
MONGODB_DB_NAME=ingres_db
MONGODB_TIMEOUT_MS=5000
HF_TOKEN=<your-huggingface-token>
CORS_ORIGINS=*
```

After the frontend is deployed, replace `CORS_ORIGINS=*` with the frontend URL.

## Migrate data to MongoDB Atlas

Run this locally after creating the Atlas cluster and setting `MONGODB_URI`:

```powershell
$env:MONGODB_URI="mongodb+srv://<user>:<password>@<cluster-url>/?retryWrites=true&w=majority"
$env:MONGODB_DB_NAME="ingres_db"
python migrate_to_mongodb.py
```

The migration imports `ingres.db` into the `assessments` and `state_trends` collections and creates basic indexes for state, district, category, and extraction fields.
