"""
Tự động phân loại từ vựng vào chủ đề IELTS dựa trên nghĩa (definition).
Sử dụng keyword matching — không cần API bên ngoài.
"""

# Từ khóa liên quan đến từng chủ đề IELTS
TOPIC_KEYWORDS = {
    "environment": [
        "environment", "ecology", "pollution", "climate", "carbon", "emission",
        "recycle", "waste", "deforestation", "biodiversity", "ecosystem", "sustain",
        "renewable", "fossil", "greenhouse", "conservation", "wildlife", "habitat",
        "endangered", "species", "ozone", "drought", "flood", "natural", "organic",
        "soil", "ocean", "marine", "forest", "tree", "plant", "green", "earth",
        "weather", "temperature", "global warming", "sea level", "atmosphere",
        "toxic", "contaminate", "preserve", "protect nature", "solar", "wind energy"
    ],
    "technology": [
        "technology", "computer", "software", "hardware", "internet", "digital",
        "artificial intelligence", "robot", "automat", "machine", "data", "algorithm",
        "program", "code", "cyber", "online", "virtual", "network", "device",
        "innovat", "electronic", "smartphone", "app", "social media", "platform",
        "cloud", "server", "database", "encrypt", "hack", "tech", "gadget",
        "wireless", "bluetooth", "satellite", "gps", "sensor", "battery",
        "biotech", "nanotech", "quantum", "process", "download", "upload"
    ],
    "health": [
        "health", "medical", "doctor", "hospital", "disease", "illness", "patient",
        "treatment", "medicine", "drug", "symptom", "diagnos", "surgery", "mental",
        "physical", "exercise", "diet", "nutrition", "obesity", "stress", "anxiety",
        "therapy", "vaccine", "immune", "infect", "virus", "bacteria", "hygiene",
        "well-being", "wellness", "chronic", "acute", "disorder", "syndrome",
        "organ", "blood", "heart", "lung", "brain", "sleep", "insomnia",
        "depression", "addiction", "rehabilitation", "fitness", "muscle", "bone",
        "cancer", "diabetes", "allergy", "pain", "wound", "heal", "cure",
        "pharmaceutical", "clinic", "nurse", "dentist", "psychology", "psychiatr"
    ],
    "education": [
        "education", "school", "university", "college", "student", "teacher",
        "learn", "study", "knowledge", "academic", "curriculum", "exam",
        "degree", "diploma", "scholarship", "lecture", "classroom", "tutor",
        "literacy", "illiterac", "skill", "training", "graduate", "undergraduate",
        "research", "thesis", "homework", "assignment", "grade", "score",
        "intellect", "cognitive", "pedagog", "mentor", "pupil", "campus",
        "library", "textbook", "syllabus", "semester", "course", "workshop",
        "enroll", "matriculat", "discipline", "primary", "secondary", "tertiary"
    ],
    "crime": [
        "crime", "criminal", "law", "legal", "illegal", "prison", "jail",
        "punish", "penalty", "offense", "offend", "victim", "witness",
        "court", "judge", "jury", "convict", "sentence", "arrest", "police",
        "detective", "murder", "theft", "steal", "rob", "fraud", "corrupt",
        "violence", "assault", "abuse", "bully", "harass", "vandal",
        "juvenile", "delinquen", "rehabilitat", "probation", "parole",
        "surveillance", "forensic", "evidence", "suspect", "guilty", "innocent",
        "prosecut", "defend", "attorney", "lawyer", "justice", "injustice"
    ],
    "society": [
        "society", "social", "community", "citizen", "population", "demographic",
        "poverty", "wealth", "inequality", "discriminat", "prejudice", "racism",
        "gender", "feminism", "rights", "freedom", "democracy", "welfare",
        "homeless", "refugee", "immigra", "emigra", "migrat", "diversity",
        "inclusion", "exclusion", "class", "status", "privilege", "marginal",
        "volunteer", "charity", "nonprofit", "activism", "protest", "movement",
        "tradition", "custom", "norm", "value", "moral", "ethic", "behavior",
        "attitude", "opinion", "belief", "ideology", "generation", "elderly",
        "youth", "minority", "majority", "urban", "rural", "suburb"
    ],
    "economy": [
        "economy", "economic", "finance", "financial", "money", "currency",
        "bank", "invest", "stock", "market", "trade", "commerce", "business",
        "profit", "loss", "revenue", "income", "wage", "salary", "tax",
        "budget", "debt", "loan", "interest", "inflation", "deflation",
        "recession", "depression", "growth", "gdp", "export", "import",
        "tariff", "subsid", "entrepreneur", "startup", "corporation",
        "manufacture", "industry", "productiv", "consumer", "demand", "supply",
        "competit", "monopol", "capital", "asset", "liability", "dividend",
        "bankruptcy", "insolvenc", "commodity", "resource", "scarcity"
    ],
    "culture": [
        "culture", "cultural", "tradition", "heritage", "festival", "ceremony",
        "ritual", "custom", "folklore", "mythology", "legend", "religion",
        "spiritual", "sacred", "worship", "temple", "church", "mosque",
        "language", "dialect", "linguist", "literature", "poetry", "novel",
        "music", "dance", "theatre", "theater", "drama", "perform",
        "museum", "gallery", "exhibit", "artifact", "archaeolog", "history",
        "historical", "ancient", "modern", "contemporary", "identity",
        "multicultural", "cross-cultural", "indigenous", "ethnic", "tribe"
    ],
    "science": [
        "science", "scientific", "research", "experiment", "hypothesis",
        "theory", "discover", "invent", "laboratory", "microscope", "telescope",
        "physics", "chemistry", "biology", "geology", "astronomy", "math",
        "formula", "equation", "molecule", "atom", "cell", "gene", "dna",
        "evolution", "mutation", "fossil", "dinosaur", "gravity", "force",
        "energy", "matter", "particle", "wave", "spectrum", "radiation",
        "element", "compound", "reaction", "catalyst", "photosynthesis",
        "nucleus", "electron", "proton", "neutron", "orbit", "planet"
    ],
    "media": [
        "media", "news", "journal", "press", "broadcast", "television",
        "radio", "newspaper", "magazine", "advertis", "propaganda",
        "censor", "freedom of speech", "publish", "editor", "reporter",
        "interview", "headline", "article", "column", "blog", "podcast",
        "stream", "viral", "trend", "influencer", "celebrity", "fame",
        "entertainment", "film", "movie", "cinema", "documentary",
        "photograph", "camera", "video", "content", "audience", "viewer",
        "subscriber", "click", "engagement", "sensation", "tabloid"
    ],
    "transport": [
        "transport", "traffic", "vehicle", "car", "bus", "train", "airplane",
        "bicycle", "motorcycle", "ship", "boat", "ferry", "subway", "metro",
        "highway", "road", "bridge", "tunnel", "fuel", "petrol", "diesel",
        "electric car", "commut", "passenger", "driver", "pilot", "congestion",
        "infrastructure", "railway", "airport", "port", "terminal", "route",
        "journey", "destination", "freight", "cargo", "logistic", "delivery",
        "parking", "speed", "accelerat", "brake", "emission", "autonomous",
        "self-driving", "ride-sharing", "uber", "taxi", "navigation"
    ],
    "food": [
        "food", "nutrition", "diet", "meal", "cook", "recipe", "ingredient",
        "cuisine", "restaurant", "chef", "taste", "flavor", "delicious",
        "appetite", "hunger", "starv", "malnutrition", "vitamin", "mineral",
        "protein", "carbohydrate", "fat", "calorie", "organic", "gmo",
        "pesticide", "fertiliz", "agriculture", "farm", "crop", "harvest",
        "livestock", "meat", "vegetable", "fruit", "grain", "dairy",
        "vegan", "vegetarian", "allergy", "intolerance", "preservative",
        "additive", "process food", "fast food", "junk food", "beverage"
    ],
    "travel": [
        "travel", "tourism", "tourist", "vacation", "holiday", "trip",
        "journey", "adventure", "explore", "discover", "destination",
        "sightseeing", "landmark", "monument", "attraction", "resort",
        "hotel", "hostel", "accommodation", "booking", "reservation",
        "passport", "visa", "customs", "border", "abroad", "overseas",
        "backpack", "luggage", "souvenir", "guide", "itinerary", "excursion",
        "cruise", "safari", "trek", "hike", "camp", "beach", "island",
        "mountain", "landscape", "scenery", "panoram", "heritage site"
    ],
    "work": [
        "work", "job", "career", "profession", "occupation", "employ",
        "unemploy", "recruit", "hire", "fire", "resign", "retire",
        "colleague", "boss", "manager", "leader", "team", "office",
        "workplace", "remote", "freelance", "contract", "full-time",
        "part-time", "overtime", "shift", "deadline", "project", "task",
        "meeting", "presentation", "promotion", "demot", "performance",
        "productivity", "efficiency", "skill", "qualification", "experience",
        "resume", "interview", "applicant", "candidate", "intern",
        "apprentice", "entrepreneur", "ambition", "motivation", "burnout",
        "work-life balance", "satisfaction", "commute", "corporate"
    ],
    "family": [
        "family", "parent", "child", "children", "mother", "father",
        "sibling", "brother", "sister", "husband", "wife", "spouse",
        "marriage", "divorce", "wedding", "relation", "generation",
        "grandparent", "ancestor", "descend", "adopt", "foster",
        "upbringing", "nurture", "raise", "domestic", "household",
        "responsibility", "bond", "attachment", "affection", "love",
        "support", "care", "conflict", "harmony", "tradition",
        "single parent", "extended family", "nuclear family", "guardian",
        "custody", "inherit", "heredit", "relative", "kin", "offspring"
    ],
    "government": [
        "government", "politic", "policy", "legislation", "parliament",
        "congress", "senate", "president", "minister", "mayor", "governor",
        "election", "vote", "ballot", "campaign", "party", "democrat",
        "republic", "constitution", "amendment", "regulation", "bureaucra",
        "diplomat", "embassy", "sanction", "treaty", "alliance", "coalition",
        "authorit", "power", "sovereignty", "citizen", "nation", "state",
        "federal", "municipal", "local government", "public sector",
        "civil servant", "corruption", "transparency", "accountability"
    ],
    "communication": [
        "communicat", "language", "speak", "speech", "convers",
        "discuss", "debate", "argument", "negotiat", "persuad",
        "present", "express", "articulate", "eloquent", "fluent",
        "interpret", "translat", "gesture", "body language", "tone",
        "listen", "comprehend", "understand", "misunderstand",
        "feedback", "respond", "interact", "dialogue", "monologue",
        "literate", "verbal", "non-verbal", "written", "oral"
    ],
    "sports": [
        "sport", "athlet", "competition", "champion", "tournament",
        "match", "game", "play", "team", "coach", "referee", "score",
        "goal", "win", "lose", "draw", "medal", "trophy", "record",
        "olympic", "marathon", "sprint", "swim", "football", "soccer",
        "basketball", "tennis", "cricket", "boxing", "wrestling",
        "gymnasium", "stadium", "arena", "fitness", "train", "stamina",
        "endurance", "strength", "doping", "fair play", "sportsmanship"
    ],
    "art": [
        "art", "artist", "paint", "draw", "sculpt", "sketch", "canvas",
        "gallery", "exhibit", "museum", "creative", "creativity",
        "imagination", "inspire", "aesthetic", "beauty", "design",
        "architect", "photograph", "illustrat", "masterpiece", "portrait",
        "landscape", "abstract", "contemporary", "classical", "baroque",
        "renaissance", "impressionism", "expressionism", "surrealism",
        "composition", "technique", "medium", "color", "form", "texture"
    ],
    "housing": [
        "house", "home", "housing", "apartment", "flat", "building",
        "construct", "architect", "design", "room", "rent", "lease",
        "mortgage", "property", "real estate", "landlord", "tenant",
        "neighbor", "neighbourhood", "community", "suburb", "urban",
        "rural", "downtown", "residential", "commercial", "renovation",
        "furnish", "decor", "infrastructure", "facility", "amenity",
        "homeless", "shelter", "affordable", "luxury", "skyscraper"
    ]
}


def classify_topic(word: str, definition: str) -> str:
    """
    Phân loại từ vào chủ đề IELTS dựa trên từ và nghĩa.
    Trả về topic phù hợp nhất hoặc 'general' nếu không xác định được.
    """
    if not definition:
        return "general"

    # Combine word + definition for better matching
    text = f"{word} {definition}".lower()

    # Score each topic
    scores = {}
    for topic, keywords in TOPIC_KEYWORDS.items():
        score = 0
        for kw in keywords:
            if kw in text:
                # Longer keywords get higher scores (more specific)
                score += len(kw)
        if score > 0:
            scores[topic] = score

    if not scores:
        return "general"

    # Return the topic with the highest score
    best_topic = max(scores, key=scores.get)

    # Require a minimum score to avoid weak matches
    if scores[best_topic] < 4:
        return "general"

    return best_topic


def classify_topic_with_confidence(word: str, definition: str) -> tuple[str, float]:
    """
    Phân loại từ và trả về (topic, confidence).
    Confidence từ 0.0 đến 1.0.
    """
    if not definition:
        return "general", 0.0

    text = f"{word} {definition}".lower()

    scores = {}
    for topic, keywords in TOPIC_KEYWORDS.items():
        score = 0
        for kw in keywords:
            if kw in text:
                score += len(kw)
        if score > 0:
            scores[topic] = score

    if not scores:
        return "general", 0.0

    best_topic = max(scores, key=scores.get)
    total_score = sum(scores.values())
    confidence = scores[best_topic] / total_score if total_score > 0 else 0.0

    if scores[best_topic] < 4:
        return "general", 0.0

    return best_topic, round(confidence, 2)
