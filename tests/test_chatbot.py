"""Test script for RAG Chatbot."""
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../src'))

from ai_project.services import chatbot, vector_store


def test_indexing():
    """Test indexing jobs into vector store."""
    print("=" * 60)
    print("TEST 1: Indexing Jobs")
    print("=" * 60)
    
    try:
        stats_before = vector_store.get_collection_stats()
        print(f"Stats before: {stats_before}")
        
        # Index jobs (will skip if already indexed)
        vector_store.index_jobs(force_reindex=False)
        
        stats_after = vector_store.get_collection_stats()
        print(f"\nStats after: {stats_after}")
        print(f"✓ Indexing test passed! Total jobs: {stats_after.get('total_jobs', 0)}")
        return True
    except Exception as e:
        print(f"✗ Indexing test failed: {e}")
        return False


def test_search():
    """Test semantic search."""
    print("\n" + "=" * 60)
    print("TEST 2: Semantic Search")
    print("=" * 60)
    
    test_queries = [
        "Công việc ở Đà Nẵng",
        "Python developer",
        "NodeJS ExpressJS"
    ]
    
    try:
        for query in test_queries:
            print(f"\nQuery: '{query}'")
            results = chatbot.quick_search_jobs(query, n_results=3)
            print(f"Found {len(results)} jobs")
            
            if results:
                print(f"Top result: {results[0]['metadata'].get('title', 'N/A')}")
                print(f"Distance: {results[0].get('distance', 'N/A')}")
        
        print("\n✓ Search test passed!")
        return True
    except Exception as e:
        print(f"✗ Search test failed: {e}")
        return False


def test_chat():
    """Test chatbot with Gemini."""
    print("\n" + "=" * 60)
    print("TEST 3: RAG Chatbot")
    print("=" * 60)
    
    test_questions = [
        "Tìm việc làm ở Đà Nẵng",
        "Công việc nào yêu cầu kỹ năng NodeJS?",
        "Đề xuất việc làm cho lập trình viên Python"
    ]
    
    try:
        for question in test_questions:
            print(f"\n{'─' * 60}")
            print(f"Question: {question}")
            print(f"{'─' * 60}")
            
            response = chatbot.chat(question, n_results=3)
            
            if response.get('status') == 'success':
                print(f"\nAnswer:\n{response['answer']}")
                print(f"\n✓ Found {response['num_jobs_found']} relevant jobs")
            else:
                print(f"✗ Error: {response.get('error', 'Unknown error')}")
                return False
        
        print("\n" + "=" * 60)
        print("✓ Chat test passed!")
        return True
    except Exception as e:
        print(f"✗ Chat test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_streaming():
    """Test streaming chat."""
    print("\n" + "=" * 60)
    print("TEST 4: Streaming Chat")
    print("=" * 60)
    
    question = "Tìm việc Python developer"
    print(f"Question: {question}")
    print(f"\nStreaming response:")
    print(f"{'─' * 60}")
    
    try:
        chunk_count = 0
        for chunk in chatbot.chat_stream(question, n_results=3):
            print(chunk, end='', flush=True)
            chunk_count += 1
        
        print(f"\n{'─' * 60}")
        print(f"✓ Streaming test passed! Received {chunk_count} chunks")
        return True
    except Exception as e:
        print(f"\n✗ Streaming test failed: {e}")
        return False


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("RAG CHATBOT TEST SUITE")
    print("=" * 60)
    
    results = {
        'Indexing': test_indexing(),
        'Search': test_search(),
        'Chat': test_chat(),
        'Streaming': test_streaming()
    }
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    for test_name, passed in results.items():
        status = "✓ PASSED" if passed else "✗ FAILED"
        print(f"{test_name:20} {status}")
    
    total = len(results)
    passed = sum(results.values())
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return 1


if __name__ == '__main__':
    sys.exit(main())
