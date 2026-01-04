"""Recommendation service: combine skill-based and semantic similarity.

Algorithm (improved):
- Skill-based score (75%): Jaccard similarity between job_seeker skill set and job_post skill set
  plus a weighted endorsement component: matched endorsement sum divided by total endorsement sum.
- Semantic similarity (25%): cosine similarity between embeddings of job_seeker text
  (skills names + bio) and job_post text (title + description + requirements) using
  `sentence-transformers` when available. If model loading fails, fall back to skill-only.
- Hard filtering: Jobs with no matching skills OR very low skill overlap are filtered out.
- Category matching: Skills are categorized and cross-category penalties are applied.

Endpoint should return top-N job posts with `job_post_id`, `title`, `score` and a
short snippet of description.
"""
from __future__ import annotations

import os
from typing import List, Dict, Any, Tuple
import math
from functools import lru_cache
import time

from .. import db

try:
    from sentence_transformers import SentenceTransformer
    import numpy as np
    _HAS_ST = True
except Exception:
    _HAS_ST = False


_MODEL = None
_SKILL_CACHE = {}  # Cache for skill names
_CACHE_TIMESTAMP = 0
CACHE_TTL = 300  # 5 minutes


def _load_model():
    global _MODEL
    if _MODEL is None:
        model_name = os.getenv("MODEL_NAME", "sentence-transformers/all-MiniLM-L6-v2")
        try:
            _MODEL = SentenceTransformer(model_name)
        except Exception:
            _MODEL = None
    return _MODEL


def _embed(texts: List[str]):
    model = _load_model()
    if model is None:
        return None
    return model.encode(texts, convert_to_numpy=True)


def _cosine(a, b):
    # handle zero vectors
    if a is None or b is None:
        return 0.0
    a = np.array(a)
    b = np.array(b)
    if np.linalg.norm(a) == 0 or np.linalg.norm(b) == 0:
        return 0.0
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


@lru_cache(maxsize=1000)
def _categorize_skill(skill_name: str) -> str:
    """Categorize skill into broad domains for better matching."""
    if not skill_name:
        return "other"
    
    skill_lower = skill_name.lower()
    
    # IT/Tech skills
    tech_keywords = [
        "python", "java", "javascript", "node", "react", "angular", "vue",
        "backend", "frontend", "fullstack", "developer", "programming",
        "software", "code", "api", "database", "sql", "nosql", "cloud",
        "aws", "azure", "devops", "docker", "kubernetes", "git",
        "html", "css", "typescript", "c++", "c#", "php", "ruby",
        "android", "ios", "mobile", "web", "ui", "ux", "design",
        "figma", "photoshop", "illustrator", "sketch"
    ]
    
    # Sales/Business skills
    sales_keywords = [
        "sales", "sale", "bán hàng", "kinh doanh", "tư vấn",
        "telesales", "telesale", "business", "account", "customer",
        "client", "negotiation", "crm", "b2b", "b2c", "retail"
    ]
    
    # Marketing/Content skills
    marketing_keywords = [
        "marketing", "seo", "sem", "social media", "content",
        "digital marketing", "brand", "advertising", "campaign",
        "facebook ads", "google ads", "email marketing", "copywriting",
        "analytics", "communication", "pr", "media", "quảng cáo"
    ]
    
    # Check categories
    for keyword in tech_keywords:
        if keyword in skill_lower:
            return "tech"
    
    for keyword in sales_keywords:
        if keyword in skill_lower:
            return "sales"
    
    for keyword in marketing_keywords:
        if keyword in skill_lower:
            return "marketing"
    
    return "other"


def _category_match_score(seeker_categories: set, post_categories: set) -> float:
    """Calculate category matching score. Returns 1.0 for perfect match, lower for mismatch."""
    if not seeker_categories or not post_categories:
        return 0.5  # neutral if no categories
    
    # Check for overlap
    overlap = seeker_categories & post_categories
    if overlap:
        # Good match - same category
        return 1.0
    
    # Check if categories are compatible
    compatible_pairs = {
        ("sales", "marketing"),
        ("marketing", "sales"),
    }
    
    for sc in seeker_categories:
        for pc in post_categories:
            if (sc, pc) in compatible_pairs:
                return 0.7  # partial match
    
    # Different categories - strong penalty
    if "tech" in seeker_categories and "tech" not in post_categories:
        return 0.1
    if "tech" not in seeker_categories and "tech" in post_categories:
        return 0.1
    
    return 0.3  # weak match


def _skill_scores(seeker_skills: List[Dict[str, Any]], post_skill_ids: List[int], 
                  skills_name_map: Dict[int, str]) -> Tuple[float, float, float]:
    """Return (jaccard_score, weighted_score, category_score) all in [0,1].

    seeker_skills: list of dicts with keys including 'skill_id' and 'endorsement_count'
    post_skill_ids: list of skill_id ints
    skills_name_map: mapping from skill_id to skill_name for categorization
    """
    seeker_ids = {int(s.get("skill_id")) for s in seeker_skills}
    post_ids = {int(x) for x in post_skill_ids}
    
    if not seeker_ids and not post_ids:
        return 0.0, 0.0, 0.0
    
    # If job requires skills but user has none, or vice versa - very low match
    if not seeker_ids or not post_ids:
        return 0.0, 0.0, 0.0
    
    inter = seeker_ids & post_ids
    union = seeker_ids | post_ids
    jaccard = len(inter) / len(union) if union else 0.0

    # weighted: sum endorsements of matched skills / sum endorsements of all seeker skills
    total_endorse = 0
    matched_endorse = 0
    for s in seeker_skills:
        e = int(s.get("endorsement_count") or 0)
        total_endorse += e
        if int(s.get("skill_id")) in inter:
            matched_endorse += e
    weighted = (matched_endorse / total_endorse) if total_endorse > 0 else (1.0 if matched_endorse > 0 else 0.0)
    
    # Category matching
    seeker_categories = set()
    for s in seeker_skills:
        skill_name = skills_name_map.get(int(s.get("skill_id")), "")
        cat = _categorize_skill(skill_name)
        if cat != "other":
            seeker_categories.add(cat)
    
    post_categories = set()
    for pid in post_skill_ids:
        skill_name = skills_name_map.get(int(pid), "")
        cat = _categorize_skill(skill_name)
        if cat != "other":
            post_categories.add(cat)
    
    category_score = _category_match_score(seeker_categories, post_categories)
    
    return jaccard, weighted, category_score


def _get_cached_skills():
    """Get cached skill names with TTL."""
    global _SKILL_CACHE, _CACHE_TIMESTAMP
    current_time = time.time()
    
    if current_time - _CACHE_TIMESTAMP > CACHE_TTL or not _SKILL_CACHE:
        # Refresh cache
        _SKILL_CACHE = db.fetch_skills_by_ids([])  # Fetch all skills
        _CACHE_TIMESTAMP = current_time
    
    return _SKILL_CACHE


def recommend(job_seeker_id: str, top_n: int = 5) -> List[Dict[str, Any]]:
    """Main entry: return top_n job posts with computed `score`.

    Structure of returned item: {job_post_id, title, score, snippet}
    """
    seeker = db.fetch_job_seeker_by_id(job_seeker_id)
    if seeker is None:
        return []

    seeker_skills = db.fetch_job_seeker_skills(job_seeker_id)
    if not seeker_skills:
        return []  # No skills = no recommendations

    # Fetch all job posts
    posts = db.fetch_all_job_posts(limit=1000)
    if not posts:
        return []

    # OPTIMIZATION 1: Batch fetch all job skills at once (avoid N+1 queries)
    post_ids = [p.get("job_post_id") or p.get("id") for p in posts]
    posts_skill_map = db.fetch_job_post_skills_batch(post_ids)  # New batch method
    
    # OPTIMIZATION 2: Use cached skill names
    skills_name_map = _get_cached_skills()

    # OPTIMIZATION 3: Pre-filter by skill-based score BEFORE embedding
    # This reduces embedding workload significantly
    seeker_skill_ids = {int(s.get("skill_id")) for s in seeker_skills}
    
    # Build seeker categories once
    seeker_categories = set()
    for s in seeker_skills:
        skill_name = skills_name_map.get(int(s.get("skill_id")), "")
        cat = _categorize_skill(skill_name)
        if cat != "other":
            seeker_categories.add(cat)
    
    # First pass: filter by skills only (fast)
    candidates = []
    for p in posts:
        pid = p.get("job_post_id") or p.get("id")
        post_skill_ids = posts_skill_map.get(pid, [])
        
        # Quick category check
        post_categories = set()
        for psid in post_skill_ids:
            skill_name = skills_name_map.get(int(psid), "")
            cat = _categorize_skill(skill_name)
            if cat != "other":
                post_categories.add(cat)
        
        category_score = _category_match_score(seeker_categories, post_categories)
        
        # Hard filter
        if category_score < 0.15:
            continue
        
        # Calculate basic skill scores
        jaccard, weighted, _ = _skill_scores(seeker_skills, post_skill_ids, skills_name_map)
        
        if jaccard == 0.0 and category_score < 0.5:
            continue
        
        skill_score = 0.4 * jaccard + 0.2 * weighted + 0.4 * category_score
        
        candidates.append({
            "post": p,
            "skill_score": skill_score,
            "jaccard": jaccard,
            "category_score": category_score,
            "post_skill_ids": post_skill_ids
        })
    
    # Sort by skill score and take top candidates for embedding
    candidates.sort(key=lambda x: x["skill_score"], reverse=True)
    top_candidates = candidates[:min(50, len(candidates))]  # Only embed top 50
    
    # OPTIMIZATION 4: Only embed top candidates (not all 1000 posts)
    use_semantic = _HAS_ST and len(top_candidates) > 0
    seeker_emb = None
    candidate_embs = {}
    
    if use_semantic:
        try:
            _load_model()
            if _MODEL is not None:
                seeker_skill_names = [skills_name_map.get(int(s.get("skill_id")), "") for s in seeker_skills]
                seeker_text = " ".join([str(seeker.get("bio") or "")] + seeker_skill_names)
                
                # Build texts only for top candidates
                texts_to_embed = [seeker_text]
                candidate_order = []
                for c in top_candidates:
                    p = c["post"]
                    pid = p.get("job_post_id") or p.get("id")
                    title = p.get("title") or ""
                    desc = p.get("description") or ""
                    req = p.get("requirements") or ""
                    skill_names = [skills_name_map.get(sid, "") for sid in c["post_skill_ids"]]
                    txt = " ".join([title, desc, req] + skill_names)
                    texts_to_embed.append(txt)
                    candidate_order.append(pid)
                
                embeds = _embed(texts_to_embed)
                if embeds is not None:
                    seeker_emb = embeds[0]
                    for idx, pid in enumerate(candidate_order):
                        candidate_embs[pid] = embeds[idx + 1]
                else:
                    use_semantic = False
            else:
                use_semantic = False
        except Exception:
            use_semantic = False

    # Second pass: compute final scores
    results = []
    for c in top_candidates:
        p = c["post"]
        pid = p.get("job_post_id") or p.get("id")
        skill_score = c["skill_score"]
        jaccard = c["jaccard"]
        
        semantic_score = 0.0
        if use_semantic and pid in candidate_embs:
            try:
                semantic_score = _cosine(seeker_emb, candidate_embs[pid])
            except Exception:
                semantic_score = 0.0

        # Final score: 75% skill (with category), 25% semantic
        if use_semantic:
            final = 0.75 * skill_score + 0.25 * semantic_score
        else:
            final = skill_score
        
        # Additional penalty for very low skill overlap
        if jaccard < 0.05:
            final *= 0.5

        results.append({
            "job_post_id": pid,
            "title": p.get("title"),
            "company_name": p.get("company_name", ""),
            "company_logo": p.get("company_logo", ""),
            "location": p.get("location", ""),
            "salary_range": p.get("salary_range", ""),
            "job_type": p.get("job_type", ""),
            "experience_level": p.get("experience_level", ""),
            "posted_date": p.get("posted_date", ""),
            "application_deadline": p.get("application_deadline", ""),
            "score": round(float(final), 4),
            "snippet": (p.get("description") or "")[:300],
            "description": p.get("description", ""),
            "requirements": p.get("requirements", ""),
            "benefits": p.get("benefits", ""),
        })

    # sort desc and pick top_n
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_n]
