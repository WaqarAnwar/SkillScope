from skillscope.mapreduce import count_skills, count_words

DOCS = [
    {"description": "python scrapy scrapy", "skills": ["python", "scrapy"]},
    {"description": "python pandas pandas", "skills": ["python", "pandas"]},
    {"description": "no skills field", "skills": []},
]


def test_count_skills_counts_across_documents():
    counts = count_skills(DOCS)
    assert counts == {"python": 2, "scrapy": 1, "pandas": 1}


def test_count_skills_parallel_matches_serial():
    serial = {}
    for doc in DOCS:
        for skill in doc["skills"]:
            serial[skill] = serial.get(skill, 0) + 1
    assert count_skills(DOCS) == serial


def test_count_words_is_non_empty():
    assert count_words(DOCS)["python"] == 2


def test_empty_input():
    assert count_skills([]) == {}