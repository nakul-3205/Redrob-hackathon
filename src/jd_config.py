# jd_config.py — JD-derived constants. All scoring rules live here, not buried in logic files.

MUST_HAVE_SKILLS = {
    "faiss":                            1.0,
    "pinecone":                         1.0,
    "weaviate":                         1.0,
    "qdrant":                           1.0,
    "milvus":                           1.0,
    "opensearch":                       1.0,
    "elasticsearch":                    1.0,
    "sentence-transformers":            1.0,
    "sentence transformers":            1.0,
    "bge":                              0.9,
    "e5":                               0.9,
    "dense retrieval":                  0.9,
    "vector search":                    1.0,
    "hybrid search":                    1.0,
    "embeddings":                       0.9,
    "text embeddings":                  0.9,
    "semantic search":                  0.9,
    "information retrieval":            1.0,
    "retrieval":                        0.8,
    "rag":                              0.9,
    "retrieval augmented generation":   0.9,
    "reranking":                        0.9,
    "bm25":                             0.8,
    "ndcg":                             1.0,
    "mrr":                              1.0,
    "map":                              0.9,
    "learning to rank":                 1.0,
    "lambdamart":                       0.9,
    "ranknet":                          0.8,
    "listwise ranking":                 0.8,
    "python":                           0.9,
}

NICE_TO_HAVE_SKILLS = {
    "lora":                     0.8,
    "qlora":                    0.8,
    "peft":                     0.7,
    "fine-tuning":              0.7,
    "fine tuning":              0.7,
    "llm fine-tuning":          0.8,
    "xgboost":                  0.6,
    "lightgbm":                 0.6,
    "pytorch":                  0.6,
    "tensorflow":               0.5,
    "distributed systems":      0.6,
    "large-scale inference":    0.7,
    "kafka":                    0.5,
    "redis":                    0.5,
    "a/b testing":              0.6,
    "ab testing":               0.6,
    "mlflow":                   0.5,
    "airflow":                  0.5,
    "open-source":              0.4,
}

# Always irrelevant — penalty regardless of other skills
NEGATIVE_SKILLS = {
    "react":                0.05,
    "angular":              0.05,
    "vue.js":               0.05,
    "tailwind":             0.05,
    "css":                  0.03,
    "html":                 0.03,
    "figma":                0.05,
    "photoshop":            0.05,
    "ui design":            0.05,
    "ux":                   0.05,
    "seo":                  0.1,
    "content writing":      0.1,
    "accounting":           0.1,
    "excel":                0.03,
    "sales":                0.1,
    "cold calling":         0.1,
    "erp":                  0.05,
    "autocad":              0.1,
    "solidworks":           0.1,
    "structural analysis":  0.1,
    # off-domain AI — penalized below only if candidate has no NLP/IR depth
    "computer vision":      0.15,
    "opencv":               0.10,
    "yolo":                 0.10,
    "image classification": 0.10,
    "object detection":     0.10,
    "speech recognition":   0.10,
    "text-to-speech":       0.10,
    "tts":                  0.05,
    "asr":                  0.05,
    "robotics":             0.10,
}

# Subset of NEGATIVE_SKILLS that are only penalized when the candidate
# has no NLP/IR signal. A CV engineer who also does RAG is fine; a pure
# CV engineer applying for a search role is not.
DOMAIN_MISMATCH_SKILL_KEYS = {
    "computer vision", "opencv", "yolo", "image classification",
    "object detection", "speech recognition", "text-to-speech",
    "tts", "asr", "robotics",
}

# Orchestration wrappers — not real AI skills. Penalized if the candidate
# has these but none of the MUST_HAVE_SKILLS above.
LANGCHAIN_WRAPPER_SKILLS = {
    "langchain", "llamaindex", "llama index", "llama_index",
}


TITLE_TIERS = [
    (["ml engineer", "machine learning engineer"],              1.00),
    (["ai engineer", "ai/ml engineer", "ai ml engineer"],      1.00),
    (["search engineer", "search relevance"],                   1.00),
    (["nlp engineer", "nlp scientist"],                         1.00),
    (["ranking engineer", "ranking scientist"],                 1.00),
    (["applied scientist", "applied ml"],                       0.92),
    (["research engineer"],                                     0.88),
    (["data scientist"],                                        0.75),
    (["senior engineer", "staff engineer", "principal engineer"], 0.65),
    (["software engineer", "sde", "software developer"],       0.50),
    (["backend engineer", "backend developer"],                 0.45),
    (["platform engineer", "infrastructure engineer"],          0.40),
    (["data engineer"],                                         0.38),
    (["mlops", "ml platform"],                                  0.60),
    (["full stack", "fullstack"],                               0.20),
    (["frontend engineer", "frontend developer"],               0.15),
    (["devops", "sre", "site reliability"],                     0.15),
    (["mobile developer", "ios developer", "android developer"], 0.10),
    (["tech lead", "engineering manager", "em"],               0.30),
    (["product manager", "pm"],                                 0.10),
    (["project manager"],                                       0.10),
    (["business analyst", "ba"],                                0.10),
    (["qa engineer", "quality assurance", "test engineer"],     0.10),
    (["hr manager", "hr executive", "human resources"],         0.00),
    (["marketing manager", "marketing executive"],              0.00),
    (["content writer", "copywriter", "content creator"],       0.00),
    (["accountant", "accounting", "finance manager"],           0.00),
    (["civil engineer"],                                        0.00),
    (["mechanical engineer", "structural engineer"],            0.00),
    (["customer support", "customer success"],                  0.00),
    (["graphic designer", "visual designer"],                   0.00),
    (["sales executive", "sales manager", "business development"], 0.00),
    (["operations manager", "operations executive"],            0.00),
    (["supply chain", "logistics"],                             0.00),
    (["lawyer", "legal"],                                       0.00),
]

CONSULTING_COMPANIES = {
    "tcs", "tata consultancy", "infosys", "wipro", "accenture",
    "cognizant", "capgemini", "hcl", "hcl technologies",
    "tech mahindra", "mphasis", "hexaware", "mindtree",
    "l&t infotech", "ltimindtree", "mastech", "niit technologies",
    "igate", "patni", "cyient", "zensar",
}

TECH_INDUSTRIES = {
    "software", "technology", "saas", "fintech", "edtech",
    "healthtech", "ai", "machine learning", "artificial intelligence",
    "information technology", "internet", "e-commerce", "marketplace",
    "data analytics", "cloud computing", "cybersecurity",
}

PRODUCT_COMPANY_SIZES = {"51-200", "201-500", "501-1000", "1001-5000"}

YOE_SCORES = [
    (lambda y: 5.0 <= y <= 9.0,   1.00),
    (lambda y: 4.0 <= y < 5.0,    0.82),
    (lambda y: 9.0 < y <= 12.0,   0.85),
    (lambda y: 3.0 <= y < 4.0,    0.60),
    (lambda y: 12.0 < y <= 15.0,  0.70),
    (lambda y: y > 15.0,           0.50),
    (lambda y: 2.0 <= y < 3.0,    0.30),
    (lambda y: True,               0.15),
]

TARGET_CITIES = {
    "pune", "noida", "delhi", "new delhi", "delhi ncr",
    "mumbai", "hyderabad", "bangalore", "bengaluru",
    "gurgaon", "gurugram", "ncr",
}

WEIGHTS = {
    "skill":   0.40,
    "career":  0.35,
    "signal":  0.25,
}

CAREER_WEIGHTS = {
    "title":   0.50,
    "yoe":     0.30,
    "company": 0.20,
}

SIGNAL_WEIGHTS = {
    "recency":        0.30,
    "responsiveness": 0.25,
    "notice":         0.20,
    "location":       0.15,
    "extras":         0.10,
}
