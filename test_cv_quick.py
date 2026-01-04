"""
Quick Test Script for CV Features
Run this to test all CV endpoints quickly
"""
import requests
import json
import time
from pathlib import Path

BASE_URL = "http://127.0.0.1:8000"

def print_header(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)

def test_basic_analyze(cv_path):
    """Test 1: Basic CV Analysis"""
    print_header("TEST 1: Basic CV Analysis")
    
    url = f"{BASE_URL}/cv/analyze"
    
    try:
        with open(cv_path, 'rb') as f:
            files = {'file': f}
            start_time = time.time()
            response = requests.post(url, files=files)
            elapsed = time.time() - start_time
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Status: SUCCESS ({elapsed:.2f}s)")
            print(f"   Filename: {result['filename']}")
            print(f"   Skills Found: {result['skills_count']}")
            print(f"   Skills: {', '.join(result['skills_found'][:5])}")
            print(f"   Experience: {result['experience_years']} years")
            print(f"   Education: {result['education_level']}")
            return True
        else:
            print(f"❌ Status: FAILED ({response.status_code})")
            print(f"   Error: {response.json().get('detail', 'Unknown error')}")
            return False
    except Exception as e:
        print(f"❌ Exception: {str(e)}")
        return False

def test_match_jobs(cv_path, top_n=5):
    """Test 2: CV Matching with Jobs"""
    print_header("TEST 2: CV Matching with Jobs")
    
    url = f"{BASE_URL}/cv/upload-and-match"
    
    try:
        with open(cv_path, 'rb') as f:
            files = {'file': f}
            params = {'top_n': top_n}
            start_time = time.time()
            response = requests.post(url, files=files, params=params)
            elapsed = time.time() - start_time
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Status: SUCCESS ({elapsed:.2f}s)")
            print(f"   Jobs Scanned: {result['total_jobs_scanned']}")
            print(f"   Matched Jobs: {len(result['matched_jobs'])}")
            
            print(f"\n   Top 3 Matches:")
            for i, job in enumerate(result['matched_jobs'][:3], 1):
                print(f"   {i}. {job['title']}")
                print(f"      Company: {job['company_name']}")
                print(f"      Score: {job['score']:.2%}")
                print(f"      Location: {job['location']}")
            return True
        else:
            print(f"❌ Status: FAILED ({response.status_code})")
            print(f"   Error: {response.json().get('detail', 'Unknown error')}")
            return False
    except Exception as e:
        print(f"❌ Exception: {str(e)}")
        return False

def test_ai_analysis(cv_path):
    """Test 3: Gemini AI Analysis"""
    print_header("TEST 3: Gemini AI Analysis")
    
    url = f"{BASE_URL}/cv/analyze-with-ai"
    
    try:
        with open(cv_path, 'rb') as f:
            files = {'file': f}
            start_time = time.time()
            response = requests.post(url, files=files)
            elapsed = time.time() - start_time
        
        if response.status_code == 200:
            result = response.json()
            analysis = result['analysis']
            
            if 'error' in analysis:
                print(f"⚠️  Status: Gemini not available")
                print(f"   {analysis['error']}")
                return None
            
            print(f"✅ Status: SUCCESS ({elapsed:.2f}s)")
            print(f"   Overall Score: {analysis.get('overall_score', 'N/A')}/100")
            
            if 'strengths' in analysis:
                print(f"\n   💪 Strengths ({len(analysis['strengths'])}):")
                for strength in analysis['strengths'][:3]:
                    print(f"      • {strength}")
            
            if 'weaknesses' in analysis:
                print(f"\n   ⚠️  Weaknesses ({len(analysis['weaknesses'])}):")
                for weakness in analysis['weaknesses'][:3]:
                    print(f"      • {weakness}")
            
            if 'improvement_suggestions' in analysis:
                print(f"\n   💡 Improvement Suggestions ({len(analysis['improvement_suggestions'])}):")
                for sugg in analysis['improvement_suggestions'][:2]:
                    print(f"      [{sugg.get('priority', 'N/A')}] {sugg.get('area', 'N/A')}")
                    print(f"      → {sugg.get('suggestion', 'N/A')[:80]}...")
            
            return True
        else:
            print(f"❌ Status: FAILED ({response.status_code})")
            print(f"   Error: {response.json().get('detail', 'Unknown error')}")
            return False
    except Exception as e:
        print(f"❌ Exception: {str(e)}")
        return False

def test_section_improvement(cv_path, section="experience"):
    """Test 4: Section Improvement"""
    print_header(f"TEST 4: Section Improvement ({section})")
    
    url = f"{BASE_URL}/cv/improve-section"
    
    try:
        with open(cv_path, 'rb') as f:
            files = {'file': f}
            params = {
                'section': section,
                'target_job': 'Software Engineer'
            }
            start_time = time.time()
            response = requests.post(url, files=files, params=params)
            elapsed = time.time() - start_time
        
        if response.status_code == 200:
            result = response.json()
            improvements = result['improvements']
            
            if 'error' in improvements:
                print(f"⚠️  Status: Gemini not available")
                print(f"   {improvements['error']}")
                return None
            
            print(f"✅ Status: SUCCESS ({elapsed:.2f}s)")
            print(f"   Section: {improvements.get('section', section)}")
            
            if 'current_content' in improvements:
                print(f"\n   📄 Current: {improvements['current_content'][:100]}...")
            
            if 'improved_content' in improvements:
                print(f"\n   ✨ Improved: {improvements['improved_content'][:100]}...")
            
            if 'tips' in improvements:
                print(f"\n   💡 Tips ({len(improvements['tips'])}):")
                for tip in improvements['tips'][:3]:
                    print(f"      • {tip}")
            
            if 'keywords_added' in improvements:
                keywords = improvements['keywords_added']
                if keywords:
                    print(f"\n   🏷️  Keywords Added: {', '.join(keywords[:5])}")
            
            return True
        else:
            print(f"❌ Status: FAILED ({response.status_code})")
            print(f"   Error: {response.json().get('detail', 'Unknown error')}")
            return False
    except Exception as e:
        print(f"❌ Exception: {str(e)}")
        return False

def test_server_health():
    """Test 0: Server Health Check"""
    print_header("TEST 0: Server Health Check")
    
    try:
        response = requests.get(f"{BASE_URL}/")
        if response.status_code == 200:
            print("✅ Server is running")
            print(f"   {response.json()}")
            return True
        else:
            print(f"❌ Server returned {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Cannot connect to server: {str(e)}")
        print(f"   Make sure server is running at {BASE_URL}")
        return False

def main():
    print("""
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║           CV ANALYSIS & MATCHING - QUICK TEST                ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    # Check server
    if not test_server_health():
        print("\n⚠️  Server is not running. Please start the server first:")
        print("   python -m uvicorn ai_project.app:app --reload")
        return
    
    # Get CV file path
    cv_path = input("\n📄 Enter path to CV file (PDF or DOCX): ").strip()
    
    if not cv_path:
        print("❌ No file path provided. Using default: sample_cv.pdf")
        cv_path = "sample_cv.pdf"
    
    cv_path = Path(cv_path)
    if not cv_path.exists():
        print(f"❌ File not found: {cv_path}")
        return
    
    # Run tests
    results = {
        'Basic Analysis': test_basic_analyze(str(cv_path)),
        'Job Matching': test_match_jobs(str(cv_path)),
        'AI Analysis': test_ai_analysis(str(cv_path)),
        'Section Improvement': test_section_improvement(str(cv_path))
    }
    
    # Summary
    print_header("TEST SUMMARY")
    
    passed = sum(1 for v in results.values() if v is True)
    skipped = sum(1 for v in results.values() if v is None)
    failed = sum(1 for v in results.values() if v is False)
    
    for test_name, result in results.items():
        status = "✅ PASSED" if result is True else "⚠️  SKIPPED" if result is None else "❌ FAILED"
        print(f"   {test_name}: {status}")
    
    print(f"\n   Total: {len(results)} tests")
    print(f"   Passed: {passed}")
    print(f"   Skipped: {skipped}")
    print(f"   Failed: {failed}")
    
    if failed == 0:
        print("\n🎉 All tests passed successfully!")
    else:
        print(f"\n⚠️  {failed} test(s) failed. Check logs above.")

if __name__ == "__main__":
    main()
