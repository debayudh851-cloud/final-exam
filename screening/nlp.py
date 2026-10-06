import re
import nltk
from django.conf import settings
from nltk.tokenize import wordpunct_tokenize
from sklearn.feature_extraction.text import TfidfVectorizer

nltk.data.path.insert(0, str(settings.BASE_DIR / 'artifacts' / 'nltk_data'))


class NLPResourcesMissing(RuntimeError):
    pass


def analyze_resume(text, required_skills, include_pos=True):
    text = (text or '').strip()
    if not text:
        return {'tokens': [], 'pos_tags': [], 'matched_skills': [], 'keyword_score': 0.0, 'vector': {}}
    tokens = wordpunct_tokenize(text.lower())
    skills = sorted({str(s).strip().lower() for s in required_skills if str(s).strip()})
    matched = [skill for skill in skills if re.search(r'(?<!\w)' + re.escape(skill) + r'(?!\w)', text.lower())]
    tags = []
    if include_pos:
        try:
            tags = nltk.pos_tag(tokens[:500])
        except LookupError as exc:
            raise NLPResourcesMissing('Run python manage.py setup_nlp to install the NLTK POS resource.') from exc
    numerical = {}
    if re.search(r'\w', text):
        vectorizer = TfidfVectorizer(token_pattern=r'(?u)\b\w+\b', max_features=100)
        vector = vectorizer.fit_transform([text.lower()])
        numerical = dict(zip(vectorizer.get_feature_names_out().tolist(), vector.toarray()[0].tolist()))
    return {'tokens': tokens[:500], 'pos_tags': tags, 'matched_skills': matched,
            'keyword_score': round(100 * len(matched) / len(skills), 2) if skills else 0.0,
            'vector': numerical}
