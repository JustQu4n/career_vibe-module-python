"""Job Data Service - Load and process job data from database and Excel."""
from __future__ import annotations

import os
import pandas as pd
from typing import List, Dict, Any
from ..db import fetch_all_job_posts, fetch_job_post_skills


def load_jobs_from_database(limit: int = 1000) -> List[Dict[str, Any]]:
    """Load job posts from PostgreSQL database."""
    jobs = fetch_all_job_posts(limit=limit)
    
    # Enrich each job with skills
    for job in jobs:
        job_id = job.get('job_post_id') or job.get('id')
        if job_id:
            skills = fetch_job_post_skills(str(job_id))
            # Extract skill names if available
            skill_names = [s.get('skill_name') or s.get('name') for s in skills if s.get('skill_name') or s.get('name')]
            job['skills'] = skill_names
        else:
            job['skills'] = []
    
    return jobs


def load_jobs_from_excel(filepath: str) -> List[Dict[str, Any]]:
    """Load job posts from Excel file."""
    if not os.path.exists(filepath):
        print(f"Excel file not found: {filepath}")
        return []
    
    try:
        df = pd.read_excel(filepath)
        jobs = df.to_dict('records')
        
        # Process skills if they exist as comma-separated strings
        for job in jobs:
            if 'skills' in job and isinstance(job['skills'], str):
                job['skills'] = [s.strip() for s in job['skills'].split(',') if s.strip()]
            elif 'skills' not in job:
                job['skills'] = []
        
        return jobs
    except Exception as e:
        print(f"Error loading Excel file: {e}")
        return []


def combine_job_data() -> List[Dict[str, Any]]:
    """Combine jobs from both database and Excel file."""
    # Load from database
    db_jobs = load_jobs_from_database()
    
    # Load from Excel
    excel_path = os.path.join(os.path.dirname(__file__), '../../job.xlsx')
    excel_jobs = load_jobs_from_excel(excel_path)
    
    # Combine and deduplicate by job_id
    all_jobs = db_jobs + excel_jobs
    
    # Deduplicate by job_post_id or id
    seen = set()
    unique_jobs = []
    for job in all_jobs:
        job_id = job.get('job_post_id') or job.get('id')
        if job_id and job_id not in seen:
            seen.add(job_id)
            unique_jobs.append(job)
        elif not job_id:
            # If no ID, keep it anyway
            unique_jobs.append(job)
    
    return unique_jobs


def format_job_for_embedding(job: Dict[str, Any]) -> str:
    """Format a job dictionary into a text representation for embedding."""
    parts = []
    
    # Title
    title = job.get('title') or job.get('job_title') or job.get('position') or 'Unknown'
    parts.append(f"Tiêu đề: {title}")
    
    # Company
    company = job.get('company_name') or job.get('company') or ''
    if company:
        parts.append(f"Công ty: {company}")
    
    # Location
    location = job.get('location') or job.get('city') or job.get('address') or ''
    if location:
        parts.append(f"Địa điểm: {location}")
    
    # Salary
    salary = job.get('salary') or job.get('salary_range') or ''
    if salary:
        parts.append(f"Mức lương: {salary}")
    
    # Skills
    skills = job.get('skills', [])
    if skills and isinstance(skills, list):
        parts.append(f"Kỹ năng yêu cầu: {', '.join(skills)}")
    elif skills and isinstance(skills, str):
        parts.append(f"Kỹ năng yêu cầu: {skills}")
    
    # Description
    description = job.get('description') or job.get('job_description') or ''
    if description:
        # Truncate long descriptions
        desc_short = description[:500] if len(description) > 500 else description
        parts.append(f"Mô tả: {desc_short}")
    
    # Requirements
    requirements = job.get('requirements') or job.get('job_requirements') or ''
    if requirements:
        req_short = requirements[:300] if len(requirements) > 300 else requirements
        parts.append(f"Yêu cầu: {req_short}")
    
    return '\n'.join(parts)


def get_job_metadata(job: Dict[str, Any]) -> Dict[str, Any]:
    """Extract metadata from job for vector store."""
    return {
        'job_id': str(job.get('job_post_id') or job.get('id') or ''),
        'title': job.get('title') or job.get('job_title') or job.get('position') or '',
        'company': job.get('company_name') or job.get('company') or '',
        'location': job.get('location') or job.get('city') or '',
        'salary': job.get('salary') or job.get('salary_range') or '',
        'skills': ','.join(job.get('skills', [])) if isinstance(job.get('skills'), list) else str(job.get('skills', '')),
    }
