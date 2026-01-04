from fastapi import FastAPI, HTTPException, Query, UploadFile, File
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
import os

from .main import greet
from . import db
from .services import recommendation
from .services import chatbot, vector_store, cv_matcher

load_dotenv()

app = FastAPI(
    title="AI Project API",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# OPTIMIZATIONS: Add compression middleware for faster response
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Configure CORS
_cors_origins = os.getenv("CORS_ORIGINS", "").strip()
if _cors_origins:
    _allowed_origins = [o.strip() for o in _cors_origins.split(",") if o.strip()]
else:
    # Default to localhost origins if not set
    _allowed_origins = ["http://localhost:5173", "http://localhost:3000"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    max_age=3600,  # Cache preflight requests for 1 hour
)


class ChatRequest(BaseModel):
    question: str
    n_results: int = 5


@app.get("/")
def read_root():
    return {"status": "ok", "message": "AI Project API with RAG Chatbot"}


@app.get("/greet/{name}")
def read_greet(name: str):
    return {"message": greet(name)}


@app.get("/job_posts")
def get_job_posts(limit: int = Query(100, ge=1, le=1000)):
    """Return job posts from the database. Use `limit` to limit rows returned."""
    try:
        posts = db.fetch_all_job_posts(limit=limit)
    except Exception as exc:
        # Surface a clear HTTP error rather than raw traceback
        raise HTTPException(status_code=500, detail=str(exc))
    return posts


@app.get("/job_seekers/{job_seeker_id}")
def get_job_seeker(job_seeker_id: str):
    """Return a job seeker profile and their skills by `job_seeker_id`."""
    try:
        profile = db.fetch_job_seeker_by_id(job_seeker_id)
        if profile is None:
            raise HTTPException(status_code=404, detail="job_seeker not found")
        skills = db.fetch_job_seeker_skills(job_seeker_id)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return {"profile": profile, "skills": skills}

@app.get("/recommendations/{job_seeker_id}")
def get_recommendations(job_seeker_id: str, top_n: int = Query(5, ge=1, le=50)):
    """Return top N recommended job posts for given job_seeker_id."""
    try:
        recs = recommendation.recommend(job_seeker_id, top_n=top_n)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    if not recs:
        # Distinguish between not found and empty recommendations
        seeker = db.fetch_job_seeker_by_id(job_seeker_id)
        if seeker is None:
            raise HTTPException(status_code=404, detail="job_seeker not found")
    return recs


# ===== RAG CHATBOT ENDPOINTS =====

@app.post("/chat")
def chat_with_bot(request: ChatRequest):
    """
    Chat with AI about job recruitment.
    Ask questions like:
    - "Tìm việc làm ở Đà Nẵng"
    - "Công việc nào yêu cầu NodeJS và ExpressJS?"
    - "Đề xuất việc làm cho lập trình viên Python"
    """
    try:
        response = chatbot.chat(request.question, n_results=request.n_results)
        return response
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/chat/stream")
async def chat_stream_endpoint(request: ChatRequest):
    """
    Stream chat responses for real-time interaction.
    """
    try:
        def generate():
            for chunk in chatbot.chat_stream(request.question, n_results=request.n_results):
                yield chunk
        
        return StreamingResponse(generate(), media_type="text/plain")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/search/jobs")
def search_jobs_endpoint(query: str = Query(..., description="Search query"), 
                         n_results: int = Query(5, ge=1, le=20)):
    """
    Quick search for jobs without AI generation.
    Returns relevant jobs based on semantic similarity.
    """
    try:
        results = chatbot.quick_search_jobs(query, n_results=n_results)
        return {"query": query, "results": results, "count": len(results)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/index/jobs")
def index_jobs_endpoint(force_reindex: bool = Query(False, description="Force rebuild index")):
    """
    Index or re-index all jobs into the vector database.
    This should be called once after setup or when jobs are updated.
    """
    try:
        vector_store.index_jobs(force_reindex=force_reindex)
        stats = vector_store.get_collection_stats()
        return {"message": "Indexing completed", "stats": stats}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/index/stats")
def get_index_stats():
    """Get statistics about the vector database."""
    try:
        stats = vector_store.get_collection_stats()
        return stats
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ===== CV MATCHING ENDPOINTS =====

@app.post("/cv/upload-and-match")
async def upload_cv_and_match(
    file: UploadFile = File(...),
    top_n: int = Query(10, ge=1, le=50, description="Number of top matching jobs to return")
):
    """
    Upload CV (PDF or DOCX) and get matching job recommendations.
    
    The system will:
    1. Parse the CV file
    2. Extract skills, experience, and education
    3. Match against available job posts
    4. Return ranked recommendations with match scores
    
    Supported formats: PDF, DOCX
    """
    # Validate file type
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")
    
    filename_lower = file.filename.lower()
    if not (filename_lower.endswith('.pdf') or filename_lower.endswith('.docx')):
        raise HTTPException(
            status_code=400,
            detail="Invalid file format. Only PDF and DOCX files are supported."
        )
    
    # Check file size (max 10MB)
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:  # 10MB
        raise HTTPException(status_code=400, detail="File too large. Maximum size is 10MB.")
    
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Empty file uploaded.")
    
    try:
        result = cv_matcher.match_cv_with_jobs(
            cv_content=content,
            filename=file.filename,
            top_n=top_n
        )
        return result
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"CV matching failed: {str(exc)}")


@app.post("/cv/analyze")
async def analyze_cv_only(file: UploadFile = File(...)):
    """
    Analyze CV without job matching.
    
    Returns extracted information:
    - Skills found
    - Years of experience
    - Education level
    - CV preview
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")
    
    filename_lower = file.filename.lower()
    if not (filename_lower.endswith('.pdf') or filename_lower.endswith('.docx')):
        raise HTTPException(
            status_code=400,
            detail="Invalid file format. Only PDF and DOCX files are supported."
        )
    
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large. Maximum size is 10MB.")
    
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Empty file uploaded.")
    
    try:
        cv_text = cv_matcher.parse_cv(content, file.filename)
        analysis = cv_matcher.analyze_cv(cv_text)
        
        return {
            "filename": file.filename,
            "skills_found": analysis["skills"],
            "skills_count": len(analysis["skills"]),
            "experience_years": analysis["experience_years"],
            "education_level": analysis["education"],
            "preview": analysis["full_text"]
        }
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"CV analysis failed: {str(exc)}")


@app.post("/cv/analyze-with-ai")
async def analyze_cv_with_ai(
    file: UploadFile = File(...),
    job_post_id: str = Query(None, description="Optional job post ID to compare against")
):
    """
    Analyze CV using Gemini AI for detailed insights and improvement suggestions.
    
    Features:
    - Detailed strengths and weaknesses analysis
    - Skill gap identification
    - Improvement suggestions with priorities
    - Format and content recommendations
    - Optional job fit analysis (if job_post_id provided)
    
    Returns comprehensive AI-powered CV analysis.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")
    
    filename_lower = file.filename.lower()
    if not (filename_lower.endswith('.pdf') or filename_lower.endswith('.docx')):
        raise HTTPException(
            status_code=400,
            detail="Invalid file format. Only PDF and DOCX files are supported."
        )
    
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large. Maximum size is 10MB.")
    
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Empty file uploaded.")
    
    try:
        # Parse CV
        cv_text = cv_matcher.parse_cv(content, file.filename)
        
        # Get job post if provided
        job_post = None
        if job_post_id:
            job_post = db.fetch_job_post_by_id(job_post_id)
            if not job_post:
                raise HTTPException(status_code=404, detail="Job post not found")
        
        # Analyze with Gemini
        analysis = cv_matcher.analyze_cv_with_gemini(cv_text, job_post)
        
        return {
            "filename": file.filename,
            "analysis": analysis,
            "job_comparison": job_post_id is not None
        }
    except HTTPException:
        raise
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"AI analysis failed: {str(exc)}")


@app.post("/cv/improve-section")
async def improve_cv_section(
    file: UploadFile = File(...),
    section: str = Query(..., description="Section to improve: summary, experience, skills, education"),
    target_job: str = Query(None, description="Optional target job title/description")
):
    """
    Get specific improvement suggestions for a CV section using Gemini AI.
    
    Sections available:
    - summary: Professional summary/objective
    - experience: Work experience section
    - skills: Skills section
    - education: Education section
    
    Returns before/after comparison with specific improvements.
    """
    valid_sections = ["summary", "experience", "skills", "education", "all"]
    if section.lower() not in valid_sections:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid section. Must be one of: {', '.join(valid_sections)}"
        )
    
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")
    
    filename_lower = file.filename.lower()
    if not (filename_lower.endswith('.pdf') or filename_lower.endswith('.docx')):
        raise HTTPException(
            status_code=400,
            detail="Invalid file format. Only PDF and DOCX files are supported."
        )
    
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large. Maximum size is 10MB.")
    
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Empty file uploaded.")
    
    try:
        # Parse CV
        cv_text = cv_matcher.parse_cv(content, file.filename)
        
        # Get improvement suggestions
        improvements = cv_matcher.improve_cv_section_with_gemini(
            cv_text=cv_text,
            section=section.lower(),
            target_job=target_job
        )
        
        return {
            "filename": file.filename,
            "section": section,
            "target_job": target_job,
            "improvements": improvements
        }
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Section improvement failed: {str(exc)}")