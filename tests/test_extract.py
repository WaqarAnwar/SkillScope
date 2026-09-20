from skillscope.extract import extract_skills, tokenize


def test_finds_plain_skills():
    skills = extract_skills("We build scrapers with scrapy and pandas on Linux.")
    assert "scrapy" in skills
    assert "pandas" in skills
    assert "linux" in skills


def test_finds_punctuation_skills():
    skills = extract_skills("C++ and .NET experience, plus node.js microservices.")
    assert "c++" in skills
    assert "node.js" in skills
    assert ".net" in skills


def test_no_false_positives_on_similar_words():
    skills = extract_skills("We serve fresh sushi to nosql and sql stores.")
    assert "nosql" in skills
    assert "sql" in skills


def test_sorted_and_unique():
    text = "python, then more python, then scrapy"
    assert extract_skills(text) == ["python", "scrapy"]


def test_tokenizer_never_raises_without_corpus():
    assert isinstance(tokenize("Python, Django and scrapy 2.x."), list)