"""CV Matching Service: Parse CV and match with job posts.

Features:
- Parse PDF/DOCX CV files
- Extract skills, experience, education
- Calculate matching score with job posts
- Return ranked job recommendations
"""
from __future__ import annotations

import re
import os
import json
import time
from typing import List, Dict, Any, Optional, BinaryIO, Tuple
from functools import lru_cache
import tempfile

try:
    import google.generativeai as genai
    _HAS_GEMINI = True
except ImportError:
    _HAS_GEMINI = False

try:
    import PyPDF2
    _HAS_PDF = True
except ImportError:
    _HAS_PDF = False

try:
    import docx
    _HAS_DOCX = True
except ImportError:
    _HAS_DOCX = False

try:
    from sentence_transformers import SentenceTransformer
    import numpy as np
    _HAS_ST = True
except ImportError:
    _HAS_ST = False

from .. import db

_MODEL = None
_GEMINI_MODEL = None
_SKILLS_CACHE = {}
_SKILLS_CACHE_TIME = 0
SKILLS_CACHE_TTL = 300  # 5 minutes
_JOB_SKILLS_CACHE = {}
_JOB_SKILLS_CACHE_TIME = 0
JOB_SKILLS_CACHE_TTL = 60  # 1 minute


def _load_gemini_model():
    """Initialize Gemini AI model for CV analysis."""
    global _GEMINI_MODEL
    if _GEMINI_MODEL is None and _HAS_GEMINI:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            return None
        try:
            genai.configure(api_key=api_key)
            _GEMINI_MODEL = genai.GenerativeModel('gemini-2.5-flash')
        except Exception:
            _GEMINI_MODEL = None
    return _GEMINI_MODEL


def _load_model():
    """Load sentence transformer model for embeddings."""
    global _MODEL
    if _MODEL is None:
        model_name = os.getenv("MODEL_NAME", "sentence-transformers/all-MiniLM-L6-v2")
        try:
            _MODEL = SentenceTransformer(model_name)
        except Exception:
            _MODEL = None
    return _MODEL


def _cosine_similarity(vec1, vec2):
    """Calculate cosine similarity between two vectors."""
    if vec1 is None or vec2 is None:
        return 0.0
    vec1 = np.array(vec1)
    vec2 = np.array(vec2)
    if np.linalg.norm(vec1) == 0 or np.linalg.norm(vec2) == 0:
        return 0.0
    return float(np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2)))


def parse_pdf(file_content: bytes) -> str:
    """Extract text from PDF file."""
    if not _HAS_PDF:
        raise ImportError("PyPDF2 not installed. Run: pip install PyPDF2")
    
    try:
        import io
        pdf_file = io.BytesIO(file_content)
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text() + "\n"
        return text.strip()
    except Exception as e:
        raise ValueError(f"Failed to parse PDF: {str(e)}")


def parse_docx(file_content: bytes) -> str:
    """Extract text from DOCX file."""
    if not _HAS_DOCX:
        raise ImportError("python-docx not installed. Run: pip install python-docx")
    
    try:
        import io
        doc_file = io.BytesIO(file_content)
        doc = docx.Document(doc_file)
        text = "\n".join([para.text for para in doc.paragraphs])
        return text.strip()
    except Exception as e:
        raise ValueError(f"Failed to parse DOCX: {str(e)}")


def parse_cv(file_content: bytes, filename: str) -> str:
    """Parse CV file (PDF or DOCX) and extract text."""
    filename_lower = filename.lower()
    
    if filename_lower.endswith('.pdf'):
        return parse_pdf(file_content)
    elif filename_lower.endswith('.docx'):
        return parse_docx(file_content)
    else:
        raise ValueError("Unsupported file format. Only PDF and DOCX are supported.")


def _get_cached_skills() -> Dict[int, str]:
    """Get all skills from database with caching."""
    global _SKILLS_CACHE, _SKILLS_CACHE_TIME
    current_time = time.time()
    
    if current_time - _SKILLS_CACHE_TIME > SKILLS_CACHE_TTL or not _SKILLS_CACHE:
        try:
            _SKILLS_CACHE = db.fetch_skills_by_ids([])  # Fetch all
            _SKILLS_CACHE_TIME = current_time
        except Exception:
            _SKILLS_CACHE = {}
    
    return _SKILLS_CACHE


@lru_cache(maxsize=100)
def _get_common_skills() -> List[str]:
    """Get common skills list for text extraction."""
    skills_map = _get_cached_skills()
    return list(skills_map.values())


def extract_skills_from_text(text: str) -> List[str]:
    """Extract skills from CV text by matching against known skills."""
    text_lower = text.lower()
    common_skills = _get_common_skills()
    
    # Optimize: filter skills by simple substring first, then regex
    found_skills = set()
    for skill in common_skills:
        skill_lower = skill.lower()
        # Quick pre-filter
        if skill_lower in text_lower:
            # Precise check with word boundaries
            pattern = r'\b' + re.escape(skill_lower) + r'\b'
            if re.search(pattern, text_lower):
                found_skills.add(skill)
    
    return list(found_skills)


def extract_experience_years(text: str) -> int:
    """Extract years of experience from CV text."""
    # Look for patterns like "3 years", "5+ years", "2-3 years"
    patterns = [
        r'(\d+)\+?\s*(?:years?|năm)\s+(?:of\s+)?(?:experience|kinh nghiệm)',
        r'(?:experience|kinh nghiệm).*?(\d+)\+?\s*(?:years?|năm)',
        r'(\d+)\+?\s*(?:years?|năm)',
    ]
    
    years = []
    for pattern in patterns:
        matches = re.findall(pattern, text.lower())
        for match in matches:
            try:
                years.append(int(match))
            except (ValueError, TypeError):
                pass
    
    return max(years) if years else 0


def extract_education(text: str) -> str:
    """Extract education level from CV text."""
    text_lower = text.lower()
    
    education_keywords = {
        "phd": ["phd", "tiến sĩ", "doctorate"],
        "master": ["master", "thạc sĩ", "mba"],
        "bachelor": ["bachelor", "cử nhân", "đại học", "university degree"],
        "college": ["college", "cao đẳng"],
        "high_school": ["high school", "trung học"]
    }
    
    for level, keywords in education_keywords.items():
        for keyword in keywords:
            if keyword in text_lower:
                return level
    
    return "not_specified"


def analyze_cv(cv_text: str) -> Dict[str, Any]:
    """Analyze CV text and extract structured information."""
    return {
        "skills": extract_skills_from_text(cv_text),
        "experience_years": extract_experience_years(cv_text),
        "education": extract_education(cv_text),
        "full_text": cv_text[:1000]  # First 1000 chars for preview
    }


def analyze_cv_with_gemini(cv_text: str, job_post: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Analyze CV using Gemini AI with detailed insights.
    
    OPTIMIZED: Limits CV text length to reduce API response time
    
    Args:
        cv_text: Full CV text content
        job_post: Optional job post to compare against
    
    Returns:
        Dict with analysis results and improvement suggestions
    """
    model = _load_gemini_model()
    if model is None:
        return {
            "error": "Gemini AI not available. Please set GEMINI_API_KEY environment variable.",
            "basic_analysis": analyze_cv(cv_text)
        }
    
    # OPTIMIZATION: Limit CV text length to reduce API latency
    # Most CVs are 1-2 pages, ~2000-4000 characters
    max_cv_length = 5000
    cv_text_trimmed = cv_text[:max_cv_length] if len(cv_text) > max_cv_length else cv_text
    
    # Build prompt based on whether job_post is provided
    if job_post:
        # OPTIMIZATION: Trim job post content too
        job_desc = (job_post.get('description', 'N/A') or 'N/A')[:1000]
        job_req = (job_post.get('requirements', 'N/A') or 'N/A')[:1000]
        
        prompt = f"""Bạn là chuyên gia phân tích CV và tuyển dụng. Hãy phân tích CV này và so sánh với job post.

**CV Content:**
{cv_text_trimmed}

**Job Post:**
Title: {job_post.get('title', 'N/A')}
Description: {job_desc}
Requirements: {job_req}

Hãy trả về JSON với format sau:
{{
    "overall_score": <0-100>,
    "strengths": ["điểm mạnh 1", "điểm mạnh 2", ...],
    "weaknesses": ["điểm yếu 1", "điểm yếu 2", ...],
    "missing_skills": ["skill thiếu 1", "skill thiếu 2", ...],
    "matching_skills": ["skill phù hợp 1", "skill phù hợp 2", ...],
    "improvement_suggestions": [
        {{
            "area": "tên phần cần cải thiện",
            "current": "hiện tại như thế nào",
            "suggestion": "gợi ý cải thiện cụ thể",
            "priority": "high/medium/low"
        }}
    ],
    "fit_score": <0-100>,
    "summary": "Tóm tắt đánh giá tổng quan"
}}

Chỉ trả về JSON, không thêm text khác."""
    else:
        prompt = f"""Bạn là chuyên gia phân tích CV. Hãy phân tích CV này một cách chi tiết.

**CV Content:**
{cv_text_trimmed}

Hãy trả về JSON với format sau:
{{
    "overall_score": <0-100>,
    "strengths": ["điểm mạnh 1", "điểm mạnh 2", ...],
    "weaknesses": ["điểm yếu 1", "điểm yếu 2", ...],
    "detected_skills": ["skill 1", "skill 2", ...],
    "experience_summary": "Tóm tắt kinh nghiệm",
    "education_summary": "Tóm tắt học vấn",
    "improvement_suggestions": [
        {{
            "area": "tên phần cần cải thiện",
            "current": "hiện tại như thế nào",
            "suggestion": "gợi ý cải thiện cụ thể",
            "priority": "high/medium/low",
            "example": "ví dụ cụ thể nếu có"
        }}
    ],
    "formatting_tips": ["tip format 1", "tip format 2", ...],
    "content_tips": ["tip nội dung 1", "tip nội dung 2", ...],
    "summary": "Tóm tắt đánh giá tổng quan"
}}

Chỉ trả về JSON, không thêm text khác."""
    
    try:
        response = model.generate_content(prompt)
        response_text = response.text.strip()
        
        # Clean markdown code blocks if present
        if response_text.startswith('```'):
            response_text = re.sub(r'^```(?:json)?\n', '', response_text)
            response_text = re.sub(r'\n```$', '', response_text)
        
        # Parse JSON response
        analysis = json.loads(response_text)
        
        # Add basic extracted data
        basic = analyze_cv(cv_text)
        analysis["extracted_data"] = {
            "skills_count": len(basic["skills"]),
            "skills": basic["skills"],
            "experience_years": basic["experience_years"],
            "education": basic["education"]
        }
        
        return analysis
        
    except json.JSONDecodeError as e:
        return {
            "error": f"Failed to parse Gemini response: {str(e)}",
            "raw_response": response_text if 'response_text' in locals() else None,
            "basic_analysis": analyze_cv(cv_text)
        }
    except Exception as e:
        return {
            "error": f"Gemini analysis failed: {str(e)}",
            "basic_analysis": analyze_cv(cv_text)
        }


def improve_cv_section_with_gemini(cv_text: str, section: str, target_job: Optional[str] = None) -> Dict[str, Any]:
    """Get specific improvement suggestions for a CV section using Gemini.
    
    OPTIMIZED: Trims CV text to reduce latency
    
    Args:
        cv_text: Full CV text
        section: Section to improve (e.g., 'summary', 'experience', 'skills', 'education')
        target_job: Optional target job title/description
    
    Returns:
        Dict with before/after suggestions
    """
    model = _load_gemini_model()
    if model is None:
        return {"error": "Gemini AI not available"}
    
    # OPTIMIZATION: Limit text length
    cv_text_trimmed = cv_text[:5000] if len(cv_text) > 5000 else cv_text
    job_context = f"\nTarget Job: {target_job}" if target_job else ""
    
    prompt = f"""Bạn là chuyên gia viết CV chuyên nghiệp. Hãy cải thiện phần "{section}" của CV này.{job_context}

**Current CV:**
{cv_text_trimmed}

**Yêu cầu:**
1. Phân tích phần {section} hiện tại
2. Đưa ra phiên bản cải tiến cụ thể
3. Giải thích tại sao cải tiến này tốt hơn
4. Đưa ra 3-5 bullet points nếu phù hợp

Traả về JSON format:
{{
    "section": "{section}",
    "current_content": "Nội dung hiện tại đã extract",
    "improved_content": "Nội dung sau khi cải thiện",
    "improvements": [
        {{
            "aspect": "khía cạnh được cải thiện",
            "before": "trước",
            "after": "sau",
            "reason": "lý do"
        }}
    ],
    "tips": ["tip 1", "tip 2", ...],
    "keywords_added": ["keyword 1", "keyword 2", ...]
}}

Chỉ trả về JSON."""
    
    try:
        response = model.generate_content(prompt)
        response_text = response.text.strip()
        
        # Clean markdown
        if response_text.startswith('```'):
            response_text = re.sub(r'^```(?:json)?\n', '', response_text)
            response_text = re.sub(r'\n```$', '', response_text)
        
        result = json.loads(response_text)
        return result
        
    except Exception as e:
        return {"error": f"Failed to improve section: {str(e)}"}


def calculate_cv_job_match(
    cv_analysis: Dict[str, Any],
    job_post: Dict[str, Any],
    job_skills: List[int],
    skills_map: Dict[int, str] = None
) -> float:
    """Calculate matching score between CV and job post.
    
    Scoring breakdown:
    - 50% Skills match (Jaccard similarity)
    - 30% Semantic similarity (embeddings)
    - 20% Experience/Education match
    """
    cv_skills = set([s.lower() for s in cv_analysis.get("skills", [])])
    
    # Use provided skills_map to avoid repeated DB queries
    if skills_map is None:
        skills_map = _get_cached_skills()
    
    job_skill_names = set([skills_map.get(sid, "").lower() for sid in job_skills if sid in skills_map])
    
    # 1. Skills matching (50%)
    if cv_skills and job_skill_names:
        intersection = cv_skills & job_skill_names
        union = cv_skills | job_skill_names
        skills_score = len(intersection) / len(union) if union else 0.0
    else:
        skills_score = 0.0
    
    # 2. Semantic similarity (30%)
    semantic_score = 0.0
    if _HAS_ST:
        try:
            model = _load_model()
            if model is not None:
                cv_text = " ".join(cv_analysis.get("skills", [])) + " " + cv_analysis.get("full_text", "")
                job_text = (
                    (job_post.get("title") or "") + " " +
                    (job_post.get("description") or "") + " " +
                    (job_post.get("requirements") or "")
                )
                
                embeddings = model.encode([cv_text, job_text])
                semantic_score = _cosine_similarity(embeddings[0], embeddings[1])
        except Exception:
            pass
    
    # 3. Experience/Education match (20%)
    exp_edu_score = 0.0
    
    # Experience matching
    cv_exp = cv_analysis.get("experience_years", 0)
    job_exp_text = (job_post.get("requirements") or "").lower()
    required_exp = 0
    exp_match = re.search(r'(\d+)\+?\s*(?:years?|năm)', job_exp_text)
    if exp_match:
        required_exp = int(exp_match.group(1))
    
    if required_exp > 0:
        if cv_exp >= required_exp:
            exp_edu_score += 0.6  # 60% of 20%
        elif cv_exp >= required_exp * 0.7:
            exp_edu_score += 0.4  # Partial match
    else:
        exp_edu_score += 0.5  # No requirement specified
    
    # Education matching (simple heuristic)
    cv_edu = cv_analysis.get("education", "not_specified")
    if cv_edu in ["bachelor", "master", "phd"]:
        exp_edu_score += 0.4  # 40% of 20%
    elif cv_edu == "college":
        exp_edu_score += 0.3
    else:
        exp_edu_score += 0.2
    
    # Final weighted score
    final_score = (
        0.5 * skills_score +
        0.3 * semantic_score +
        0.2 * exp_edu_score
    )
    
    return round(final_score, 4)


def match_cv_with_jobs(
    cv_content: bytes,
    filename: str,
    top_n: int = 10
) -> Dict[str, Any]:
    """Main function: Parse CV and match with job posts.
    
    OPTIMIZED: Uses batch queries, caching, and pre-filtering
    
    Returns:
        {
            "cv_analysis": {...},
            "matched_jobs": [...],
            "total_jobs_scanned": int
        }
    """
    # 1. Parse CV
    try:
        cv_text = parse_cv(cv_content, filename)
    except Exception as e:
        raise ValueError(f"CV parsing failed: {str(e)}")
    
    # 2. Analyze CV
    cv_analysis = analyze_cv(cv_text)
    
    if not cv_analysis.get("skills"):
        raise ValueError("No skills detected in CV. Please ensure your CV contains recognizable skills.")
    
    # 3. Fetch all job posts
    try:
        job_posts = db.fetch_all_job_posts(limit=1000)
    except Exception as e:
        raise ValueError(f"Failed to fetch jobs: {str(e)}")
    
    if not job_posts:
        return {
            "cv_analysis": cv_analysis,
            "matched_jobs": [],
            "total_jobs_scanned": 0
        }
    
    # OPTIMIZATION: Batch fetch all job skills at once
    job_ids = [job.get("job_post_id") or job.get("id") for job in job_posts]
    try:
        job_skills_map = db.fetch_job_post_skills_batch(job_ids)
    except Exception:
        # Fallback to individual queries if batch method not available
        job_skills_map = {}
        for job_id in job_ids:
            try:
                skills_data = db.fetch_job_post_skills(job_id)
                job_skills_map[job_id] = [int(s.get("skill_id")) for s in skills_data]
            except Exception:
                job_skills_map[job_id] = []
    
    # OPTIMIZATION: Get cached skills map once
    skills_map = _get_cached_skills()
    
    # OPTIMIZATION: Pre-filter by skill overlap before expensive calculations
    cv_skill_set = set([s.lower() for s in cv_analysis.get("skills", [])])
    
    candidates = []
    for job in job_posts:
        job_id = job.get("job_post_id") or job.get("id")
        job_skill_ids = job_skills_map.get(job_id, [])
        
        if not job_skill_ids:
            continue  # Skip jobs with no skills
        
        # Quick pre-filter: check if there's any skill overlap
        job_skill_names = set([skills_map.get(sid, "").lower() for sid in job_skill_ids if sid in skills_map])
        
        if cv_skill_set & job_skill_names:  # Has overlap
            candidates.append((job, job_skill_ids))
        elif len(cv_skill_set) == 0 or len(job_skill_names) == 0:
            # Include if either has no skills (fallback to semantic)
            candidates.append((job, job_skill_ids))
    
    # 4. Calculate matching scores for candidates only
    matched_jobs = []
    
    for job, job_skill_ids in candidates:
        job_id = job.get("job_post_id") or job.get("id")
        
        # Calculate match score with cached skills_map
        try:
            score = calculate_cv_job_match(cv_analysis, job, job_skill_ids, skills_map)
        except Exception:
            score = 0.0
        
        if score > 0.05:  # Filter out very low matches
            matched_jobs.append({
                "job_post_id": job_id,
                "title": job.get("title"),
                "company_name": job.get("company_name", ""),
                "company_logo": job.get("company_logo", ""),
                "location": job.get("location", ""),
                "salary_range": job.get("salary_range", ""),
                "job_type": job.get("job_type", ""),
                "experience_level": job.get("experience_level", ""),
                "score": score,
                "description": (job.get("description") or "")[:300],
                "requirements": (job.get("requirements") or "")[:300],
            })
    
    # 5. Sort by score and return top N
    matched_jobs.sort(key=lambda x: x["score"], reverse=True)
    
    return {
        "cv_analysis": {
            "skills_found": cv_analysis["skills"],
            "skills_count": len(cv_analysis["skills"]),
            "experience_years": cv_analysis["experience_years"],
            "education_level": cv_analysis["education"],
        },
        "matched_jobs": matched_jobs[:top_n],
        "total_jobs_scanned": len(job_posts)
    }
