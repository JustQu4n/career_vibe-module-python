"""Database helper using psycopg2 to fetch JobPost data.

Usage:
  - Set `DATABASE_URL` env var (e.g. postgresql://user:pass@host:5432/dbname)
  - Run: `python -m src.ai_project.db` or `python src/ai_project/db.py`

This module provides convenience functions:
  - `fetch_all_job_posts(limit)`
  - `fetch_job_post_by_id(job_post_id)`
  - `fetch_job_post_skills(job_post_id)`
"""
from __future__ import annotations

import os
import time
from dotenv import load_dotenv
import argparse
from typing import List, Dict, Any, Optional
from functools import lru_cache

import psycopg2
import psycopg2.extras
from psycopg2 import pool

# Global connection pool
_connection_pool = None
_pool_lock = False


def get_database_dsn() -> str:
    """Return DSN from `DATABASE_URL` or a sensible default used in repo docker-compose."""
    # Load .env file if present so DATABASE_URL inside it is picked up
    load_dotenv()
    return os.getenv("DATABASE_URL", "postgresql://jobuser:jobpass@localhost:5432/jobdb")


def _init_connection_pool():
    """Initialize connection pool for better performance."""
    global _connection_pool, _pool_lock
    if _connection_pool is None and not _pool_lock:
        _pool_lock = True
        try:
            dsn = get_database_dsn()
            _connection_pool = pool.ThreadedConnectionPool(
                minconn=2,
                maxconn=10,
                dsn=dsn
            )
        except Exception as e:
            print(f"Warning: Could not create connection pool: {e}")
            _connection_pool = None
        finally:
            _pool_lock = False
    return _connection_pool


def get_conn():
    """Get connection from pool or create new one."""
    pool_instance = _init_connection_pool()
    if pool_instance:
        try:
            return pool_instance.getconn()
        except Exception:
            pass
    # Fallback to direct connection
    dsn = get_database_dsn()
    return psycopg2.connect(dsn)


def release_conn(conn):
    """Release connection back to pool."""
    if _connection_pool:
        try:
            _connection_pool.putconn(conn)
            return
        except Exception:
            pass
    # Fallback: close connection
    if conn:
        conn.close()


def fetch_all_job_posts(limit: int = 100) -> List[Dict[str, Any]]:
    """Fetch up to `limit` job posts from `job_posts` table with company info.
    
    OPTIMIZED: Uses connection pooling and caching
    """
    sql = """
        SELECT 
            jp.*,
            c.name as company_name,
            c.logo_url as company_logo,
            c.website as company_website,
            c.description as company_description
        FROM job_posts jp
        LEFT JOIN companies c ON jp.company_id = c.company_id
        LIMIT %s
    """
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            try:
                cur.execute(sql, (limit,))
                rows = cur.fetchall()
                return [dict(r) for r in rows]
            except Exception:
                # Fallback if companies table doesn't exist or join fails
                cur.execute("SELECT * FROM job_posts LIMIT %s", (limit,))
                rows = cur.fetchall()
                return [dict(r) for r in rows]
    finally:
        release_conn(conn)


def fetch_job_post_by_id(job_post_id: str) -> Optional[Dict[str, Any]]:
    """Fetch a single job post with company information.
    
    OPTIMIZED: Uses connection pooling
    """
    sql = """
        SELECT 
            jp.*,
            c.name as company_name,
            c.logo_url as company_logo,
            c.website as company_website,
            c.description as company_description
        FROM job_posts jp
        LEFT JOIN companies c ON jp.company_id = c.company_id
        WHERE jp.job_post_id = %s
        LIMIT 1
    """
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            try:
                cur.execute(sql, (job_post_id,))
                row = cur.fetchone()
                return dict(row) if row is not None else None
            except Exception:
                cur.execute("SELECT * FROM job_posts WHERE job_post_id = %s LIMIT 1", (job_post_id,))
                row = cur.fetchone()
                return dict(row) if row is not None else None
    finally:
        release_conn(conn)


def fetch_job_post_skills(job_post_id: str) -> List[Dict[str, Any]]:
    """Fetch skills for a job post.
    
    OPTIMIZED: Uses connection pooling
    """
    sql = "SELECT * FROM job_post_skills WHERE job_post_id = %s"
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (job_post_id,))
            rows = cur.fetchall()
            return [dict(r) for r in rows]
    finally:
        release_conn(conn)


def fetch_job_post_skills_batch(job_post_ids: List[str]) -> Dict[str, List[int]]:
    """Batch fetch skills for multiple job posts.
    
    OPTIMIZED: Single query with connection pooling
    """
    if not job_post_ids:
        return {}
    
    sql = "SELECT job_post_id, skill_id FROM job_post_skills WHERE job_post_id = ANY(%s)"
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            try:
                cur.execute(sql, (job_post_ids,))
                rows = cur.fetchall()
                
                result = {}
                for job_post_id, skill_id in rows:
                    if job_post_id not in result:
                        result[job_post_id] = []
                    result[job_post_id].append(int(skill_id))
                
                for jpid in job_post_ids:
                    if jpid not in result:
                        result[jpid] = []
                
                return result
            except Exception:
                return {jpid: [] for jpid in job_post_ids}
    finally:
        release_conn(conn)


def fetch_job_seeker_by_id(job_seeker_id: str) -> Optional[Dict[str, Any]]:
    """Fetch job seeker profile.
    
    OPTIMIZED: Uses connection pooling
    """
    sql = "SELECT * FROM job_seekers WHERE job_seeker_id = %s LIMIT 1"
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (job_seeker_id,))
            row = cur.fetchone()
            return dict(row) if row is not None else None
    finally:
        release_conn(conn)


def fetch_job_seeker_skills(job_seeker_id: str) -> List[Dict[str, Any]]:
    """Fetch job seeker skills.
    
    OPTIMIZED: Uses connection pooling
    """
    sql = "SELECT * FROM user_skills WHERE job_seeker_id = %s"
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (job_seeker_id,))
            rows = cur.fetchall()
            return [dict(r) for r in rows]
    finally:
        release_conn(conn)


def fetch_skills_by_ids(skill_ids: List[int]) -> Dict[int, str]:
    """Fetch skills mapping.
    
    OPTIMIZED: Uses connection pooling. Empty list = fetch all for caching.
    """
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            try:
                if not skill_ids:
                    sql = "SELECT id, name FROM skills"
                    cur.execute(sql)
                else:
                    sql = "SELECT id, name FROM skills WHERE id = ANY(%s)"
                    cur.execute(sql, (skill_ids,))
                rows = cur.fetchall()
                return {int(r[0]): r[1] for r in rows}
            except Exception:
                return {}
    finally:
        release_conn(conn)


def _main():
    parser = argparse.ArgumentParser(description="Fetch JobPost data from PostgreSQL")
    parser.add_argument("--id", dest="job_post_id", help="job_post_id to fetch (optional)")
    parser.add_argument("--limit", dest="limit", type=int, default=50, help="max rows to fetch when --id omitted")
    args = parser.parse_args()

    print("Using DSN:", get_database_dsn())
    if args.job_post_id:
        jp = fetch_job_post_by_id(args.job_post_id)
        if not jp:
            print(f"No job post found for id={args.job_post_id}")
            return
        print("JobPost:")
        for k, v in jp.items():
            print(f"  {k}: {v}")
        print("\nSkills:")
        skills = fetch_job_post_skills(args.job_post_id)
        for s in skills:
            print(s)
    else:
        rows = fetch_all_job_posts(limit=args.limit)
        print(f"Fetched {len(rows)} job posts (limit={args.limit})")
        for r in rows[:20]:
            # print a compact representation
            jp_id = r.get("job_post_id") or r.get("id")
            title = r.get("title") or r.get("job_title") or r.get("position")
            print(f"- id={jp_id} title={title}")


if __name__ == "__main__":
    _main()
