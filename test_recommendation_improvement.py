"""Test script để demo cải thiện recommendation algorithm"""

import sys
sys.path.insert(0, 'src')

from ai_project.services.recommendation import _categorize_skill, _category_match_score

# Test skill categorization
print("=== SKILL CATEGORIZATION TEST ===\n")

# Marketing/Sales skills
marketing_sales_skills = [
    "Marketing", "Content", "Sale", "Telesale", "SEO", 
    "Social Media", "Kinh doanh", "Tư vấn bán hàng"
]

print("Marketing/Sales Skills:")
for skill in marketing_sales_skills:
    category = _categorize_skill(skill)
    print(f"  '{skill}' -> {category}")

print("\n")

# Tech/IT skills
tech_skills = [
    "Node.js", "Python", "React", "Backend Developer",
    "UI/UX Designer", "JavaScript", "Frontend"
]

print("Tech/IT Skills:")
for skill in tech_skills:
    category = _categorize_skill(skill)
    print(f"  '{skill}' -> {category}")

print("\n" + "="*50 + "\n")

# Test category matching
print("=== CATEGORY MATCHING TEST ===\n")

test_cases = [
    ({"marketing", "sales"}, {"marketing", "sales"}, "User: Marketing/Sales vs Job: Marketing/Sales"),
    ({"marketing", "sales"}, {"tech"}, "User: Marketing/Sales vs Job: Tech"),
    ({"tech"}, {"marketing", "sales"}, "User: Tech vs Job: Marketing/Sales"),
    ({"marketing"}, {"sales"}, "User: Marketing vs Job: Sales"),
    ({"sales"}, {"marketing"}, "User: Sales vs Job: Marketing"),
]

for user_cats, job_cats, description in test_cases:
    score = _category_match_score(user_cats, job_cats)
    print(f"{description}")
    print(f"  Score: {score:.2f}")
    if score >= 0.7:
        print(f"  Result: ✓ GOOD MATCH")
    elif score >= 0.5:
        print(f"  Result: ~ PARTIAL MATCH")
    else:
        print(f"  Result: ✗ POOR MATCH (will be filtered out)")
    print()

print("="*50)
print("\n🎯 SUMMARY:")
print("- Jobs with category_score < 0.15 will be FILTERED OUT")
print("- Jobs with jaccard=0 AND category_score < 0.5 will be FILTERED OUT")
print("- Skill score = 40% jaccard + 20% weighted + 40% category")
print("- Final score = 75% skill_score + 25% semantic_score")
print("\nThis ensures Marketing/Sales users won't see Tech jobs!")
