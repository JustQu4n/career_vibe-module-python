# 📋 Hướng Dẫn Test Tính Năng CV Analysis & Matching

## 🚀 Setup

### 1. Đảm bảo server đang chạy:
```bash
# Terminal 1: Start server
cd D:\graduation-project\ai
$env:PYTHONPATH = 'src'
D:/graduation-project/ai/.venv/Scripts/python.exe -m uvicorn ai_project.app:app --reload --host 127.0.0.1 --port 8000
```

### 2. Kiểm tra API Documentation:
```
Mở browser: http://127.0.0.1:8000/docs
```

---

## 📝 API Endpoints

### 1️⃣ Upload CV và Match với Jobs
**Endpoint:** `POST /cv/upload-and-match`

**Mô tả:** Upload CV (PDF/DOCX) và nhận danh sách job phù hợp theo thứ hạng

**Test với PowerShell:**
```powershell
# Chuẩn bị file CV
$cvPath = "path/to/your/cv.pdf"  # Hoặc .docx

# Upload và match
$response = Invoke-WebRequest -Uri "http://127.0.0.1:8000/cv/upload-and-match?top_n=10" `
    -Method POST `
    -InFile $cvPath `
    -ContentType "multipart/form-data"

$response.Content | ConvertFrom-Json | ConvertTo-Json -Depth 10
```

**Test với cURL:**
```bash
curl -X POST "http://127.0.0.1:8000/cv/upload-and-match?top_n=10" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@/path/to/cv.pdf"
```

**Test với Python:**
```python
import requests

url = "http://127.0.0.1:8000/cv/upload-and-match"
cv_file = "path/to/your/cv.pdf"

with open(cv_file, 'rb') as f:
    files = {'file': f}
    params = {'top_n': 10}
    response = requests.post(url, files=files, params=params)

result = response.json()
print(f"Skills found: {result['cv_analysis']['skills_count']}")
print(f"Top matched jobs: {len(result['matched_jobs'])}")

for job in result['matched_jobs'][:3]:
    print(f"\n{job['title']} - Score: {job['score']}")
```

**Expected Response:**
```json
{
  "cv_analysis": {
    "skills_found": ["Python", "JavaScript", "React", "Node.js"],
    "skills_count": 4,
    "experience_years": 3,
    "education_level": "bachelor"
  },
  "matched_jobs": [
    {
      "job_post_id": "uuid-here",
      "title": "Senior Python Developer",
      "company_name": "Tech Corp",
      "score": 0.7845,
      "location": "Hanoi",
      "salary_range": "$2000-$3000",
      "description": "..."
    }
  ],
  "total_jobs_scanned": 145
}
```

---

### 2️⃣ Phân Tích CV (Không Match Jobs)
**Endpoint:** `POST /cv/analyze`

**Mô tả:** Chỉ phân tích CV và extract thông tin cơ bản

**Test với PowerShell:**
```powershell
$cvPath = "path/to/your/cv.pdf"

$response = Invoke-WebRequest -Uri "http://127.0.0.1:8000/cv/analyze" `
    -Method POST `
    -InFile $cvPath `
    -ContentType "multipart/form-data"

$response.Content | ConvertFrom-Json | ConvertTo-Json -Depth 5
```

**Test với Python:**
```python
import requests

url = "http://127.0.0.1:8000/cv/analyze"
cv_file = "path/to/your/cv.pdf"

with open(cv_file, 'rb') as f:
    files = {'file': f}
    response = requests.post(url, files=files)

result = response.json()
print(f"Filename: {result['filename']}")
print(f"Skills: {', '.join(result['skills_found'])}")
print(f"Experience: {result['experience_years']} years")
print(f"Education: {result['education_level']}")
print(f"\nPreview:\n{result['preview']}")
```

**Expected Response:**
```json
{
  "filename": "my_cv.pdf",
  "skills_found": ["Python", "Django", "PostgreSQL", "Docker"],
  "skills_count": 4,
  "experience_years": 5,
  "education_level": "master",
  "preview": "JOHN DOE\nSoftware Engineer\n\nEXPERIENCE\n..."
}
```

---

### 3️⃣ Phân Tích CV với Gemini AI 🤖
**Endpoint:** `POST /cv/analyze-with-ai`

**Mô tả:** Phân tích CV sâu bằng Gemini AI - Nhận insights chi tiết, điểm mạnh/yếu, gợi ý cải thiện

**⚠️ Yêu cầu:** Phải có `GEMINI_API_KEY` trong file `.env`

**Test với PowerShell:**
```powershell
# Phân tích CV đơn thuần
$cvPath = "path/to/your/cv.pdf"

$response = Invoke-WebRequest -Uri "http://127.0.0.1:8000/cv/analyze-with-ai" `
    -Method POST `
    -InFile $cvPath `
    -ContentType "multipart/form-data"

$result = $response.Content | ConvertFrom-Json
$result.analysis | ConvertTo-Json -Depth 10

# Phân tích CV so với một job cụ thể
$jobId = "112bc32b-ef96-4ebd-be6b-83ea244b6ecd"

$response = Invoke-WebRequest -Uri "http://127.0.0.1:8000/cv/analyze-with-ai?job_post_id=$jobId" `
    -Method POST `
    -InFile $cvPath `
    -ContentType "multipart/form-data"

$result = $response.Content | ConvertFrom-Json
Write-Host "Overall Score: $($result.analysis.overall_score)/100"
Write-Host "Fit Score: $($result.analysis.fit_score)/100"
```

**Test với Python:**
```python
import requests

url = "http://127.0.0.1:8000/cv/analyze-with-ai"
cv_file = "path/to/your/cv.pdf"

# Test 1: Phân tích CV độc lập
with open(cv_file, 'rb') as f:
    files = {'file': f}
    response = requests.post(url, files=files)

analysis = response.json()['analysis']

print("=== GEMINI AI ANALYSIS ===\n")
print(f"Overall Score: {analysis['overall_score']}/100")
print(f"\n✅ STRENGTHS:")
for strength in analysis['strengths']:
    print(f"  • {strength}")

print(f"\n⚠️ WEAKNESSES:")
for weakness in analysis['weaknesses']:
    print(f"  • {weakness}")

print(f"\n💡 IMPROVEMENT SUGGESTIONS:")
for suggestion in analysis['improvement_suggestions']:
    priority_emoji = "🔴" if suggestion['priority'] == 'high' else "🟡" if suggestion['priority'] == 'medium' else "🟢"
    print(f"\n  {priority_emoji} {suggestion['area']}")
    print(f"     Current: {suggestion['current']}")
    print(f"     Suggest: {suggestion['suggestion']}")

# Test 2: So sánh với job post
job_id = "112bc32b-ef96-4ebd-be6b-83ea244b6ecd"

with open(cv_file, 'rb') as f:
    files = {'file': f}
    params = {'job_post_id': job_id}
    response = requests.post(url, files=files, params=params)

analysis = response.json()['analysis']

print(f"\n=== JOB FIT ANALYSIS ===")
print(f"Fit Score: {analysis['fit_score']}/100")
print(f"\n✅ Matching Skills:")
for skill in analysis.get('matching_skills', []):
    print(f"  • {skill}")

print(f"\n❌ Missing Skills:")
for skill in analysis.get('missing_skills', []):
    print(f"  • {skill}")
```

**Expected Response (Without Job):**
```json
{
  "filename": "my_cv.pdf",
  "analysis": {
    "overall_score": 75,
    "strengths": [
      "Có kinh nghiệm thực tế với các dự án lớn",
      "Skills đa dạng về backend và frontend",
      "Có chứng chỉ chuyên môn liên quan"
    ],
    "weaknesses": [
      "Thiếu số liệu cụ thể về thành tích",
      "Mô tả công việc chưa nổi bật",
      "Không có portfolio hoặc GitHub link"
    ],
    "detected_skills": ["Python", "JavaScript", "Docker", "AWS"],
    "experience_summary": "3 năm kinh nghiệm với vai trò Backend Developer",
    "education_summary": "Cử nhân Khoa học Máy tính - ĐH Bách Khoa",
    "improvement_suggestions": [
      {
        "area": "Experience Section",
        "current": "Mô tả công việc chung chung",
        "suggestion": "Thêm số liệu cụ thể: 'Tối ưu API giảm response time 40%'",
        "priority": "high",
        "example": "Developed RESTful API serving 10K+ requests/day, reducing latency by 35%"
      },
      {
        "area": "Skills Section",
        "current": "List skills đơn giản",
        "suggestion": "Phân loại skills theo technical/soft skills, thêm proficiency level",
        "priority": "medium",
        "example": "Python (Advanced), Docker (Intermediate)"
      }
    ],
    "formatting_tips": [
      "Sử dụng bullet points thay vì đoạn văn dài",
      "Thêm section Summary/Objective ở đầu CV",
      "Đảm bảo font chữ nhất quán"
    ],
    "content_tips": [
      "Thêm portfolio/GitHub links",
      "Highlight achievements với số liệu",
      "Customize CV cho từng vị trí apply"
    ],
    "summary": "CV có nền tảng tốt nhưng cần thêm chi tiết cụ thể về thành tích và impact. Nên thêm portfolio để tăng sức thuyết phục."
  },
  "job_comparison": false
}
```

**Expected Response (With Job Comparison):**
```json
{
  "filename": "my_cv.pdf",
  "analysis": {
    "overall_score": 78,
    "fit_score": 82,
    "strengths": [
      "Có đầy đủ skills chính mà job yêu cầu",
      "Experience level phù hợp với yêu cầu",
      "Background về e-commerce matching với job"
    ],
    "weaknesses": [
      "Thiếu một số technical skills mà job prefer",
      "Chưa có kinh nghiệm cụ thể về microservices"
    ],
    "matching_skills": ["Python", "PostgreSQL", "Docker", "REST API"],
    "missing_skills": ["Kubernetes", "GraphQL", "Redis"],
    "improvement_suggestions": [
      {
        "area": "Technical Skills",
        "current": "Không mention Kubernetes và Redis",
        "suggestion": "Nếu có kinh nghiệm với container orchestration hoặc caching, hãy highlight",
        "priority": "high"
      }
    ],
    "summary": "Candidate phù hợp 82% với yêu cầu job. Nên bổ sung một số skills về cloud infrastructure để tăng competitive."
  },
  "job_comparison": true
}
```

---

### 4️⃣ Cải Thiện Từng Section của CV 🔧
**Endpoint:** `POST /cv/improve-section`

**Mô tả:** Nhận gợi ý cải thiện cụ thể cho từng phần của CV (summary, experience, skills, education)

**Test với PowerShell:**
```powershell
$cvPath = "path/to/your/cv.pdf"
$section = "experience"  # summary, experience, skills, education, all
$targetJob = "Senior Backend Developer"

$uri = "http://127.0.0.1:8000/cv/improve-section?section=$section&target_job=$([uri]::EscapeDataString($targetJob))"

$response = Invoke-WebRequest -Uri $uri `
    -Method POST `
    -InFile $cvPath `
    -ContentType "multipart/form-data"

$result = $response.Content | ConvertFrom-Json
$result.improvements | ConvertTo-Json -Depth 10
```

**Test với Python:**
```python
import requests

url = "http://127.0.0.1:8000/cv/improve-section"
cv_file = "path/to/your/cv.pdf"

sections = ["summary", "experience", "skills", "education"]

for section in sections:
    print(f"\n{'='*60}")
    print(f"Improving: {section.upper()}")
    print('='*60)
    
    with open(cv_file, 'rb') as f:
        files = {'file': f}
        params = {
            'section': section,
            'target_job': 'Full Stack Developer'  # Optional
        }
        response = requests.post(url, files=files, params=params)
    
    result = response.json()['improvements']
    
    print(f"\n📄 Current Content:")
    print(result.get('current_content', 'N/A')[:200] + "...")
    
    print(f"\n✨ Improved Content:")
    print(result.get('improved_content', 'N/A')[:300] + "...")
    
    print(f"\n🔍 Specific Improvements:")
    for imp in result.get('improvements', []):
        print(f"\n  Aspect: {imp['aspect']}")
        print(f"  ❌ Before: {imp['before']}")
        print(f"  ✅ After: {imp['after']}")
        print(f"  💡 Reason: {imp['reason']}")
    
    print(f"\n💡 Tips:")
    for tip in result.get('tips', []):
        print(f"  • {tip}")
    
    if 'keywords_added' in result:
        print(f"\n🏷️ Keywords Added: {', '.join(result['keywords_added'])}")
```

**Expected Response:**
```json
{
  "filename": "my_cv.pdf",
  "section": "experience",
  "target_job": "Senior Backend Developer",
  "improvements": {
    "section": "experience",
    "current_content": "Backend Developer at ABC Company\n- Developed APIs\n- Fixed bugs\n- Worked with team",
    "improved_content": "Senior Backend Developer | ABC Company | Jan 2020 - Present\n• Architected and deployed microservices handling 100K+ daily requests using Python/FastAPI, reducing response time by 40%\n• Led team of 3 developers implementing CI/CD pipeline with Docker & Jenkins, accelerating deployment by 60%\n• Optimized PostgreSQL queries and implemented Redis caching, improving database performance by 50%\n• Collaborated with frontend team to design RESTful APIs consumed by 50K+ users",
    "improvements": [
      {
        "aspect": "Quantifiable Achievements",
        "before": "Developed APIs",
        "after": "Architected microservices handling 100K+ daily requests, reducing response time by 40%",
        "reason": "Số liệu cụ thể làm nổi bật impact và scale của công việc"
      },
      {
        "aspect": "Action Verbs",
        "before": "Worked with team",
        "after": "Led team of 3 developers implementing CI/CD pipeline",
        "reason": "Action verbs mạnh (Led, Architected) thể hiện ownership và leadership"
      },
      {
        "aspect": "Technical Details",
        "before": "Fixed bugs",
        "after": "Optimized PostgreSQL queries and implemented Redis caching",
        "reason": "Cụ thể về technology stack và technical solution"
      }
    ],
    "tips": [
      "Bắt đầu mỗi bullet với action verb mạnh (Led, Architected, Optimized)",
      "Thêm metrics: users, requests, performance improvement",
      "Highlight technical stack relevant với target job",
      "Sắp xếp theo impact - achievement quan trọng nhất lên đầu"
    ],
    "keywords_added": [
      "microservices",
      "FastAPI",
      "CI/CD",
      "Docker",
      "Redis",
      "PostgreSQL",
      "RESTful API"
    ]
  }
}
```

---

## 🧪 Test Cases

### Test Case 1: Upload PDF CV
```python
# test_cv_pdf.py
import requests

def test_upload_pdf_cv():
    url = "http://127.0.0.1:8000/cv/upload-and-match"
    cv_file = "sample_cv.pdf"
    
    with open(cv_file, 'rb') as f:
        files = {'file': f}
        params = {'top_n': 5}
        response = requests.post(url, files=files, params=params)
    
    assert response.status_code == 200
    result = response.json()
    
    assert 'cv_analysis' in result
    assert 'matched_jobs' in result
    assert result['cv_analysis']['skills_count'] > 0
    assert len(result['matched_jobs']) <= 5
    
    print("✅ Test PDF upload passed!")

if __name__ == "__main__":
    test_upload_pdf_cv()
```

### Test Case 2: Upload DOCX CV
```python
# test_cv_docx.py
import requests

def test_upload_docx_cv():
    url = "http://127.0.0.1:8000/cv/upload-and-match"
    cv_file = "sample_cv.docx"
    
    with open(cv_file, 'rb') as f:
        files = {'file': f}
        response = requests.post(url, files=files)
    
    assert response.status_code == 200
    result = response.json()
    assert result['cv_analysis']['skills_count'] > 0
    
    print("✅ Test DOCX upload passed!")

if __name__ == "__main__":
    test_upload_docx_cv()
```

### Test Case 3: Invalid File Format
```python
# test_invalid_format.py
import requests

def test_invalid_format():
    url = "http://127.0.0.1:8000/cv/upload-and-match"
    
    # Try to upload a text file
    with open("test.txt", 'w') as f:
        f.write("This is not a CV")
    
    with open("test.txt", 'rb') as f:
        files = {'file': ('test.txt', f)}
        response = requests.post(url, files=files)
    
    assert response.status_code == 400
    assert "Invalid file format" in response.json()['detail']
    
    print("✅ Test invalid format passed!")

if __name__ == "__main__":
    test_invalid_format()
```

### Test Case 4: Gemini AI Analysis
```python
# test_gemini_analysis.py
import requests
import os

def test_gemini_analysis():
    # Check if GEMINI_API_KEY is set
    if not os.getenv('GEMINI_API_KEY'):
        print("⚠️ GEMINI_API_KEY not set, skipping test")
        return
    
    url = "http://127.0.0.1:8000/cv/analyze-with-ai"
    cv_file = "sample_cv.pdf"
    
    with open(cv_file, 'rb') as f:
        files = {'file': f}
        response = requests.post(url, files=files)
    
    assert response.status_code == 200
    result = response.json()
    analysis = result['analysis']
    
    # Check required fields
    assert 'overall_score' in analysis
    assert 'strengths' in analysis
    assert 'weaknesses' in analysis
    assert 'improvement_suggestions' in analysis
    
    assert analysis['overall_score'] >= 0
    assert analysis['overall_score'] <= 100
    assert len(analysis['strengths']) > 0
    
    print("✅ Test Gemini AI analysis passed!")
    print(f"   Overall Score: {analysis['overall_score']}/100")

if __name__ == "__main__":
    test_gemini_analysis()
```

### Test Case 5: Section Improvement
```python
# test_section_improvement.py
import requests

def test_section_improvement():
    url = "http://127.0.0.1:8000/cv/improve-section"
    cv_file = "sample_cv.pdf"
    
    sections = ["summary", "experience", "skills"]
    
    for section in sections:
        with open(cv_file, 'rb') as f:
            files = {'file': f}
            params = {'section': section, 'target_job': 'Software Engineer'}
            response = requests.post(url, files=files, params=params)
        
        assert response.status_code == 200
        result = response.json()
        
        assert 'improvements' in result
        improvements = result['improvements']
        assert 'improved_content' in improvements
        assert 'tips' in improvements
        
        print(f"✅ Test {section} improvement passed!")

if __name__ == "__main__":
    test_section_improvement()
```

---

## 🔍 Debugging Tips

### 1. Check Server Logs
```powershell
# Server terminal sẽ show logs real-time
# Xem request/response và errors
```

### 2. Test với Swagger UI
```
http://127.0.0.1:8000/docs

- Interactive testing interface
- Try all endpoints directly
- See request/response schemas
```

### 3. Check Environment Variables
```powershell
# In terminal
$env:GEMINI_API_KEY
$env:DATABASE_URL
$env:PYTHONPATH

# Should output the values
```

### 4. Common Errors

**Error: "Gemini AI not available"**
```
Solution: Check .env file has GEMINI_API_KEY
```

**Error: "Failed to parse PDF"**
```
Solution: 
- Ensure file is valid PDF
- Check file not corrupted
- Try converting to PDF again
```

**Error: "No skills detected"**
```
Solution:
- CV might not contain recognizable skills
- Add common tech keywords to CV
- Check skills database has entries
```

---

## 📊 Performance Testing

```python
# test_performance.py
import requests
import time

def test_performance():
    url = "http://127.0.0.1:8000/cv/upload-and-match"
    cv_file = "sample_cv.pdf"
    
    times = []
    for i in range(5):
        start = time.time()
        
        with open(cv_file, 'rb') as f:
            files = {'file': f}
            response = requests.post(url, files=files)
        
        elapsed = time.time() - start
        times.append(elapsed)
        print(f"Request {i+1}: {elapsed:.2f}s")
    
    avg_time = sum(times) / len(times)
    print(f"\n📊 Average response time: {avg_time:.2f}s")
    
    assert avg_time < 10, "Response time too slow!"
    print("✅ Performance test passed!")

if __name__ == "__main__":
    test_performance()
```

---

## ✅ Success Criteria

- [x] Upload PDF/DOCX CVs successfully
- [x] Extract skills, experience, education correctly
- [x] Match with jobs and return ranked results
- [x] Gemini AI analysis provides detailed insights
- [x] Section improvements give specific suggestions
- [x] Response time < 10 seconds for standard CVs
- [x] Handle errors gracefully with clear messages

---

## 📚 Additional Resources

- API Documentation: http://127.0.0.1:8000/docs
- Gemini AI: https://ai.google.dev/
- FastAPI: https://fastapi.tiangolo.com/

---

**Happy Testing! 🎉**
