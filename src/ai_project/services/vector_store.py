"""Vector Store Service - Manage embeddings and similarity search using FAISS."""
from __future__ import annotations

import os
import pickle
import numpy as np
from typing import List, Dict, Any
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv
from functools import lru_cache
import time

try:
    import faiss
    _HAS_FAISS = True
except ImportError:
    _HAS_FAISS = False

from .job_data import combine_job_data, format_job_for_embedding, get_job_metadata

load_dotenv()

# Global variables
_index = None
_documents = None
_metadatas = None
_ids = None
_embedding_model = None
_embedding_cache = {}
_embedding_cache_time = {}
EMBEDDING_CACHE_TTL = 300  # 5 minutes


@lru_cache(maxsize=1)
def get_embedding_model():
    """Get or initialize the embedding model.
    
    OPTIMIZED: Cache model with LRU cache
    """
    global _embedding_model
    if _embedding_model is None:
        model_name = os.getenv('MODEL_NAME', 'sentence-transformers/all-MiniLM-L6-v2')
        print(f"Loading embedding model: {model_name}")
        _embedding_model = SentenceTransformer(model_name)
    return _embedding_model


def get_cached_embedding(text: str) -> np.ndarray:
    """Get cached embedding or compute new one.
    
    OPTIMIZED: Cache embeddings for frequently searched queries
    """
    global _embedding_cache, _embedding_cache_time
    now = time.time()
    
    # Check cache
    if text in _embedding_cache:
        cache_time = _embedding_cache_time.get(text, 0)
        if (now - cache_time) < EMBEDDING_CACHE_TTL:
            return _embedding_cache[text]
    
    # Compute and cache
    model = get_embedding_model()
    embedding = model.encode([text])[0]
    _embedding_cache[text] = embedding
    _embedding_cache_time[text] = now
    
    # Cleanup old cache entries (keep only 100 most recent)
    if len(_embedding_cache) > 100:
        oldest_keys = sorted(_embedding_cache_time.keys(), key=lambda k: _embedding_cache_time[k])[:50]
        for key in oldest_keys:
            _embedding_cache.pop(key, None)
            _embedding_cache_time.pop(key, None)
    
    return embedding


def get_index_path():
    """Get path to the persisted index."""
    data_dir = os.path.join(os.path.dirname(__file__), '../../data/faiss')
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, 'jobs.index')


def get_metadata_path():
    """Get path to the persisted metadata."""
    data_dir = os.path.join(os.path.dirname(__file__), '../../data/faiss')
    return os.path.join(data_dir, 'jobs.metadata.pkl')


def load_index():
    """Load index and metadata from disk."""
    global _index, _documents, _metadatas, _ids
    
    index_path = get_index_path()
    metadata_path = get_metadata_path()
    
    if not os.path.exists(index_path) or not os.path.exists(metadata_path):
        return False
    
    try:
        if not _HAS_FAISS:
            print("Warning: FAISS not available, using simple search")
            with open(metadata_path, 'rb') as f:
                data = pickle.load(f)
                _documents = data['documents']
                _metadatas = data['metadatas']
                _ids = data['ids']
            return True
        
        _index = faiss.read_index(index_path)
        with open(metadata_path, 'rb') as f:
            data = pickle.load(f)
            _documents = data['documents']
            _metadatas = data['metadatas']
            _ids = data['ids']
        
        print(f"Loaded index with {len(_documents)} documents")
        return True
    except Exception as e:
        print(f"Error loading index: {e}")
        return False


def save_index():
    """Save index and metadata to disk."""
    global _index, _documents, _metadatas, _ids
    
    index_path = get_index_path()
    metadata_path = get_metadata_path()
    
    try:
        if _HAS_FAISS and _index is not None:
            faiss.write_index(_index, index_path)
        
        with open(metadata_path, 'wb') as f:
            pickle.dump({
                'documents': _documents,
                'metadatas': _metadatas,
                'ids': _ids
            }, f)
        
        print(f"Saved index with {len(_documents)} documents")
        return True
    except Exception as e:
        print(f"Error saving index: {e}")
        return False


def embed_text(text: str) -> np.ndarray:
    """Generate embedding for a text string."""
    model = get_embedding_model()
    embedding = model.encode(text, convert_to_numpy=True)
    return embedding


def index_jobs(force_reindex: bool = False):
    """Index all jobs into FAISS."""
    global _index, _documents, _metadatas, _ids
    
    # Check if already indexed
    if not force_reindex and load_index():
        print(f"Index already exists with {len(_documents)} documents. Skipping indexing.")
        print("Use force_reindex=True to rebuild the index.")
        return
    
    # Load all jobs
    print("Loading job data...")
    jobs = combine_job_data()
    print(f"Loaded {len(jobs)} jobs")
    
    if not jobs:
        print("No jobs to index!")
        return
    
    # Prepare data for indexing
    _documents = []
    _metadatas = []
    _ids = []
    embeddings = []
    
    print("Generating embeddings...")
    for i, job in enumerate(jobs):
        # Format job as text
        doc_text = format_job_for_embedding(job)
        _documents.append(doc_text)
        
        # Get metadata
        metadata = get_job_metadata(job)
        _metadatas.append(metadata)
        
        # Generate ID
        job_id = metadata.get('job_id')
        doc_id = job_id if job_id else f"job_{i}"
        _ids.append(doc_id)
        
        # Generate embedding
        embedding = embed_text(doc_text)
        embeddings.append(embedding)
        
        if (i + 1) % 50 == 0:
            print(f"Processed {i + 1}/{len(jobs)} jobs...")
    
    # Create FAISS index
    embeddings_matrix = np.array(embeddings).astype('float32')
    dimension = embeddings_matrix.shape[1]
    
    if _HAS_FAISS:
        print("Creating FAISS index...")
        _index = faiss.IndexFlatL2(dimension)  # L2 distance
        _index.add(embeddings_matrix)
        print(f"FAISS index created with {_index.ntotal} vectors")
    else:
        print("FAISS not available, using simple search mode")
        _index = embeddings_matrix  # Store embeddings directly
    
    # Save to disk
    save_index()
    print(f"Successfully indexed {len(jobs)} jobs!")


def search_jobs(query: str, n_results: int = 5) -> List[Dict[str, Any]]:
    """Search for relevant jobs based on query.
    
    OPTIMIZED: Uses cached embeddings for common queries
    """
    global _index, _documents, _metadatas, _ids
    
    # Load index if not in memory
    if _documents is None:
        if not load_index():
            print("Index not found. Indexing jobs...")
            index_jobs()
    
    if _documents is None or len(_documents) == 0:
        return []
    
    # Generate query embedding with caching
    query_embedding = get_cached_embedding(query)
    query_vector = np.array([query_embedding]).astype('float32')
    
    # Search
    n_results = min(n_results, len(_documents))
    
    if _HAS_FAISS and isinstance(_index, faiss.Index):
        # Use FAISS search
        distances, indices = _index.search(query_vector, n_results)
        distances = distances[0]
        indices = indices[0]
    else:
        # Fallback: simple cosine similarity
        embeddings_matrix = _index if isinstance(_index, np.ndarray) else np.array(_index).astype('float32')
        
        # Normalize vectors
        query_norm = query_vector / np.linalg.norm(query_vector)
        embeddings_norm = embeddings_matrix / np.linalg.norm(embeddings_matrix, axis=1, keepdims=True)
        
        # Compute cosine similarity
        similarities = np.dot(embeddings_norm, query_norm.T).flatten()
        
        # Get top N
        indices = np.argsort(-similarities)[:n_results]
        distances = 1 - similarities[indices]  # Convert to distance
    
    # Format results
    formatted_results = []
    for i, idx in enumerate(indices):
        if idx < len(_documents):
            formatted_results.append({
                'id': _ids[idx],
                'document': _documents[idx],
                'metadata': _metadatas[idx],
                'distance': float(distances[i])
            })
    
    return formatted_results


def get_collection_stats() -> Dict[str, Any]:
    """Get statistics about the vector store."""
    global _documents
    
    try:
        if _documents is None:
            load_index()
        
        return {
            'total_jobs': len(_documents) if _documents else 0,
            'collection_name': 'job_posts_faiss',
            'backend': 'FAISS' if _HAS_FAISS else 'Simple',
            'status': 'ready' if _documents else 'empty'
        }
    except Exception as e:
        return {
            'total_jobs': 0,
            'error': str(e),
            'status': 'error'
        }
