"""RAG Chatbot Service - Use Gemini API with retrieval for job-related questions."""
from __future__ import annotations

import os
import google.generativeai as genai
from typing import List, Dict, Any
from dotenv import load_dotenv
from functools import lru_cache
import time

from .vector_store import search_jobs
import unicodedata

load_dotenv()

# Configure Gemini API
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# Cache Gemini model initialization
_gemini_model_cache = None
_gemini_model_cache_time = 0
GEMINI_MODEL_CACHE_TTL = 3600  # 1 hour


@lru_cache(maxsize=1)
def get_gemini_model(model_name: str = "gemini-2.5-flash"):
    """Initialize Gemini model with caching.
    
    OPTIMIZED: Cache model initialization
    """
    global _gemini_model_cache, _gemini_model_cache_time
    now = time.time()
    
    # Return cached model if still valid
    if _gemini_model_cache and (now - _gemini_model_cache_time) < GEMINI_MODEL_CACHE_TTL:
        return _gemini_model_cache
    
    try:
        # Try the latest model first
        model = genai.GenerativeModel(model_name)
        _gemini_model_cache = model
        _gemini_model_cache_time = now
        return model
    except Exception:
        # Fallback to a stable model
        model = genai.GenerativeModel('gemini-pro')
        _gemini_model_cache = model
        _gemini_model_cache_time = now
        return model


def create_prompt_with_context(question: str, relevant_jobs: List[Dict[str, Any]]) -> str:
    """Create a prompt with retrieved job context."""
    
    # System instruction
    system_prompt = """Bạn là trợ lý AI chuyên về tuyển dụng và tìm việc làm tại Việt Nam. 
Nhiệm vụ của bạn là giúp người dùng tìm kiếm và tư vấn về các cơ hội việc làm phù hợp.

Khi trả lời:
1. Trả lời bằng tiếng Việt một cách thân thiện và chuyên nghiệp
2. Dựa trên thông tin công việc được cung cấp để đưa ra câu trả lời chính xác
3. Nếu không có công việc phù hợp, hãy thông báo lịch sự và đề xuất mở rộng tiêu chí tìm kiếm
4. Nếu có nhiều công việc phù hợp, hãy trình bày ngắn gọn từng công việc
5. Làm nổi bật các thông tin quan trọng như: vị trí, công ty, địa điểm, mức lương, kỹ năng yêu cầu
6. Nếu người dùng hỏi về kỹ năng cụ thể, hãy đề xuất các công việc liên quan đến kỹ năng đó
"""
    
    # Add retrieved jobs as context
    context = "\n\n=== THÔNG TIN CÔNG VIỆC LIÊN QUAN ===\n"
    
    if not relevant_jobs:
        context += "Không tìm thấy công việc phù hợp trong cơ sở dữ liệu.\n"
    else:
        for i, job in enumerate(relevant_jobs, 1):
            context += f"\n--- Công việc {i} ---\n"
            context += job['document'] + "\n"
            
            # Add metadata if available
            metadata = job.get('metadata', {})
            if metadata.get('job_id'):
                context += f"ID: {metadata['job_id']}\n"
    
    # Combine everything
    full_prompt = f"""{system_prompt}

{context}

=== CÂU HỎI CỦA NGƯỜI DÙNG ===
{question}

=== TRẢ LỜI ===
"""
    
    return full_prompt


def chat(question: str, n_results: int = 5) -> Dict[str, Any]:
    """
    Answer a question about jobs using RAG approach.
    
    Args:
        question: User's question about jobs
        n_results: Number of relevant jobs to retrieve
    
    Returns:
        Dict containing answer, retrieved jobs, and metadata
    """
    
    if not GEMINI_API_KEY:
        return {
            'answer': 'Lỗi: GEMINI_API_KEY chưa được cấu hình. Vui lòng thêm API key vào file .env',
            'relevant_jobs': [],
            'error': 'Missing API key'
        }
    
    try:
        # Detect explicit location in query and try to prioritize matches
        loc = extract_location_from_text(question)
        search_pool = n_results
        if loc:
            # Query a larger candidate pool to allow filtering by location
            search_pool = max(n_results * 5, n_results + 5)

        # Step 1: Retrieve relevant jobs
        print(f"Searching for relevant jobs: {question} (pool={search_pool})")
        candidates = search_jobs(question, n_results=search_pool)
        print(f"Found {len(candidates)} candidate jobs")

        # If location extracted, filter candidates by metadata.location (case-insensitive)
        if loc:
            filtered = [j for j in candidates if metadata_location_matches(j.get('metadata', {}), loc)]
            if filtered:
                # Trim to requested n_results
                relevant_jobs = filtered[:n_results]
            else:
                # If no exact location match, fall back to candidates but keep them ranked
                relevant_jobs = candidates[:n_results]
        else:
            relevant_jobs = candidates[:n_results]
        print(f"Selected {len(relevant_jobs)} relevant jobs after filtering")
        
        # Step 2: Create prompt with context
        prompt = create_prompt_with_context(question, relevant_jobs)
        
        # Step 3: Generate answer using Gemini
        print("Generating answer with Gemini...")
        model = get_gemini_model()
        response = model.generate_content(prompt)
        
        answer = response.text
        
        # Step 4: Return structured response
        return {
            'answer': answer,
            'relevant_jobs': relevant_jobs,
            'num_jobs_found': len(relevant_jobs),
            'status': 'success'
        }
        
    except Exception as e:
        error_msg = f"Lỗi khi xử lý câu hỏi: {str(e)}"
        print(error_msg)
        return {
            'answer': error_msg,
            'relevant_jobs': [],
            'error': str(e),
            'status': 'error'
        }


def chat_stream(question: str, n_results: int = 5):
    """
    Stream answer for real-time response (generator function).
    
    Args:
        question: User's question about jobs
        n_results: Number of relevant jobs to retrieve
    
    Yields:
        Chunks of the answer as they are generated
    """
    
    if not GEMINI_API_KEY:
        yield "Lỗi: GEMINI_API_KEY chưa được cấu hình."
        return
    
    try:
        # Detect location and expand search pool similarly to chat()
        loc = extract_location_from_text(question)
        search_pool = n_results
        if loc:
            search_pool = max(n_results * 5, n_results + 5)

        candidates = search_jobs(question, n_results=search_pool)
        if loc:
            filtered = [j for j in candidates if metadata_location_matches(j.get('metadata', {}), loc)]
            relevant_jobs = filtered[:n_results] if filtered else candidates[:n_results]
        else:
            relevant_jobs = candidates[:n_results]

        # Create prompt
        prompt = create_prompt_with_context(question, relevant_jobs)

        # Generate answer with streaming
        model = get_gemini_model()
        response = model.generate_content(prompt, stream=True)

        for chunk in response:
            if chunk.text:
                yield chunk.text

    except Exception as e:
        yield f"Lỗi: {str(e)}"


def strip_accents(text: str) -> str:
    """Remove diacritics for simpler comparisons."""
    if not text:
        return ""
    nfkd = unicodedata.normalize('NFKD', text)
    return ''.join([c for c in nfkd if not unicodedata.combining(c)])


def extract_location_from_text(text: str) -> str | None:
    """Try to extract a simple location name from the user's query.

    This is a lightweight detector using a small list of common Vietnamese cities
    and common English variants. Returns normalized location string or None.
    """
    if not text:
        return None
    t = strip_accents(text).lower()
    # Common city variants
    cities = [
        ('ha noi', ['ha noi', 'hanoi', 'ha_noi']),
        ('da nang', ['da nang', 'danang']),
        ('ho chi minh', ['ho chi minh', 'hcm', 'saigon', 'ho_chi_minh']),
        ('hai phong', ['hai phong', 'haiphong']),
        ('can tho', ['can tho', 'cantho']),
    ]
    for canonical, variants in cities:
        for v in variants:
            if v in t:
                return canonical
    return None


def metadata_location_matches(metadata: Dict[str, Any], loc: str) -> bool:
    """Return True if metadata 'location' matches extracted loc.

    Comparison is done on normalized, accent-stripped, lowercased strings and
    checks for substring containment.
    """
    location = metadata.get('location') or metadata.get('city') or ''
    if not location:
        return False
    loc_norm = strip_accents(loc).lower()
    meta_norm = strip_accents(str(location)).lower()
    return loc_norm in meta_norm or meta_norm in loc_norm


def quick_search_jobs(query: str, n_results: int = 5) -> List[Dict[str, Any]]:
    """
    Quick search for jobs without LLM generation.
    Useful for autocomplete or quick filtering.
    """
    return search_jobs(query, n_results=n_results)
