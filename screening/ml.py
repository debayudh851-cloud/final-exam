"""Persisted demo models. Labels are historical outcomes; predictions never update records."""
import json
from functools import lru_cache
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from django.conf import settings
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score

NUMERIC = ['experience_months', 'notice_period_days', 'expected_salary', 'skill_count']
CATEGORICAL = ['applied_role']
FEATURES = NUMERIC + CATEGORICAL
ARTIFACTS = settings.BASE_DIR / 'artifacts'


class ModelUnavailable(RuntimeError):
    pass


def prepare_training(path):
    frame = pd.read_csv(path).drop_duplicates(subset=['email']).copy()
    frame = frame[frame['historical_selection_status'].isin(['SELECTED', 'REJECTED'])].copy()
    frame['skill_count'] = frame['skills'].fillna('').map(lambda s: len({v.strip().lower() for v in s.split(',') if v.strip()}))
    for col in NUMERIC:
        frame[col] = pd.to_numeric(frame[col], errors='coerce')
        frame.loc[frame[col] < 0, col] = np.nan
    y = (frame['historical_selection_status'] == 'SELECTED').astype(int)
    if len(frame) < 20 or y.value_counts().min() < 4:
        raise ValueError('Training requires at least 20 labeled rows and four examples per class.')
    X = frame[FEATURES].copy()  # Removes identifiers, resume text, and target/leakage fields.
    X[CATEGORICAL] = X[CATEGORICAL].fillna('unknown')
    return train_test_split(X, y, test_size=0.25, stratify=y, random_state=42)


def preprocessor():
    return ColumnTransformer([
        ('numeric', Pipeline([('impute', SimpleImputer(strategy='median')), ('scale', StandardScaler())]), NUMERIC),
        ('categorical', Pipeline([('impute', SimpleImputer(strategy='most_frequent')),
                                  ('encode', OneHotEncoder(handle_unknown='ignore', sparse_output=False))]), CATEGORICAL),
    ], sparse_threshold=0)


def train_models(path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    X_train, X_test, y_train, y_test = prepare_training(path)
    # Learn 1st/99th percentile caps on the training split only, preventing test leakage.
    bounds = {col: [float(X_train[col].quantile(.01)), float(X_train[col].quantile(.99))] for col in NUMERIC}
    for col, (low, high) in bounds.items():
        X_train[col] = X_train[col].clip(low, high)
        X_test[col] = X_test[col].clip(low, high)
    candidates = {'logistic_regression': LogisticRegression(max_iter=1000, random_state=42),
                  'random_forest': RandomForestClassifier(n_estimators=100, max_depth=6, random_state=42)}
    metrics, trained = {}, {}
    for name, estimator in candidates.items():
        model = Pipeline([('preprocess', preprocessor()), ('classifier', estimator)])
        model.fit(X_train, y_train)
        pred, probability = model.predict(X_test), model.predict_proba(X_test)[:, 1]
        metrics[name] = {'accuracy': accuracy_score(y_test, pred), 'precision': precision_score(y_test, pred, zero_division=0),
                         'recall': recall_score(y_test, pred, zero_division=0), 'f1': f1_score(y_test, pred, zero_division=0),
                         'roc_auc': roc_auc_score(y_test, probability)}
        trained[name] = model
    chosen = max(metrics, key=lambda name: (metrics[name]['f1'], metrics[name]['roc_auc']))
    ARTIFACTS.mkdir(exist_ok=True)
    joblib.dump({'model': trained[chosen], 'bounds': bounds, 'version': chosen + '-demo-v1'}, ARTIFACTS / 'shortlist.joblib')
    report = {'dataset': str(Path(path).name), 'train_rows': len(X_train), 'test_rows': len(X_test),
              'features': FEATURES, 'metrics': metrics, 'chosen': chosen, 'limitation': 'Synthetic demonstration data; not real hiring accuracy.'}
    (ARTIFACTS / 'ml_metrics.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar(metrics.keys(), [m['f1'] for m in metrics.values()], color=['#2563eb', '#0d9488'])
    ax.set(ylabel='Test F1', ylim=(0, 1.1), title='Synthetic data — model mechanics comparison')
    fig.tight_layout()
    fig.savefig(ARTIFACTS / 'model_comparison.png')
    plt.close(fig)
    load_model.cache_clear()
    return report


@lru_cache(maxsize=1)
def load_model():
    path = ARTIFACTS / 'shortlist.joblib'
    if not path.exists():
        raise ModelUnavailable('Run python manage.py train_ml first.')
    return joblib.load(path)  # Only load the locally generated, trusted artifact.


def predict(features):
    artifact = load_model()
    row = {col: features[col] for col in FEATURES if col != 'skill_count'}
    row['skill_count'] = len({s.strip().lower() for s in features.get('skills', '').split(',') if s.strip()})
    for col, (low, high) in artifact['bounds'].items():
        row[col] = float(np.clip(float(row[col]), low, high))
    probability = float(artifact['model'].predict_proba(pd.DataFrame([row], columns=FEATURES))[0, 1])
    return {'shortlisted': probability >= .5, 'probability': round(probability, 6), 'model_version': artifact['version'],
            'limitation': 'Demonstration score trained on synthetic data; requires HR review.'}
