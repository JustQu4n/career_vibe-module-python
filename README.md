# Job Recommendation Service

AI-powered job recommendation system using FastAPI, PostgreSQL, skill matching, and NLP semantic similarity.

## Features

- **Skill-based Matching**: Jaccard similarity + weighted endorsement scoring
- **NLP Semantic Similarity**: Using sentence-transformers for text similarity
- **Combined Scoring**: 60% skill-based + 40% semantic similarity
- **REST API**: FastAPI with automatic docs
- **Docker Support**: Fully containerized with docker-compose

## Quick Start (Development)

### Prerequisites

- Python 3.10+
- PostgreSQL 15+ (or use Docker)

### 1. Setup Environment

Create and activate virtual environment (Windows PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 2. Install Dependencies

```powershell
pip install -r requirements.txt
pip install -r dev-requirements.txt
```

### 3. Configure Environment

Copy `.env.example` to `.env` and update with your database credentials:

```powershell
Copy-Item .env.example .env
```

Edit `.env`:
```
DATABASE_URL=postgresql://user:password@localhost:5432/jobdb
MODEL_NAME=sentence-transformers/all-MiniLM-L6-v2
```

### 4. Run the Server

```powershell
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

API will be available at:
- **API**: http://localhost:8000
- **Docs**: http://localhost:8000/docs
- **Health**: http://localhost:8000/health

## Quick Start (Docker)

### Run with Docker Compose

```powershell
docker-compose up -d
```

This will start:
- PostgreSQL database on port 5432
- FastAPI application on port 8000

### Stop containers

```powershell
docker-compose down
```

## API Endpoints

### Get Recommendations

```
GET /recommendations/{job_seeker_id}?top_n=10
```

**Parameters:**
- `job_seeker_id` (UUID, required): Job seeker's unique ID
- `top_n` (int, optional): Number of recommendations (default: 10)

**Response:**
```json
[
  {
    "job_post_id": "d0f1df23-92fd-4aa8-a38a-f55c7ff2b121",
    "title": "Python Backend Developer",
    "score": 0.87
  }
]
```

### Health Check

```
GET /health
```

## Project Structure

```
/app
  /models          - SQLAlchemy models
  /schemas         - Pydantic schemas
  /routes          - API routes
  /services        - Business logic (recommendation algorithm)
  /repositories    - Database queries
  db.py           - Database connection
  main.py         - FastAPI application
.env              - Environment variables
Dockerfile        - Docker image
docker-compose.yml - Docker services
```

## Algorithm

### Skill Score (60% weight)
- **Jaccard Similarity**: intersection / union of skill sets
- **Weighted Score**: Sum of endorsement counts for matched skills
- **Combined**: 70% Jaccard + 30% weighted endorsements

### Semantic Score (40% weight)
- Uses `sentence-transformers/all-MiniLM-L6-v2`
- Compares: job_seeker (skills + bio) vs job_post (description + requirements)
- Cosine similarity of embeddings

### Final Score
```
final_score = 0.6 * skill_score + 0.4 * semantic_score
```

## Database Schema

Required tables:
- `job_seekers` - Job seeker profiles
- `user_skills` - Job seeker skills with endorsement counts
- `job_posts` - Job postings
- `job_post_skills` - Required skills for jobs

See `RECOMMENDER_MODULE.md` for full schema.

## Testing

```powershell
pytest
```

## Development

Run tests:
```powershell
pytest
```

Run with hot reload:
```powershell
uvicorn app.main:app --reload
```
# career_vibe-module-python
# career_vibe-module-python
