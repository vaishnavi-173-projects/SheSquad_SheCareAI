"""
train_model.py — Generates model.pkl for SheCare AI
Run once: python train_model.py
"""
import numpy as np
import joblib
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report

np.random.seed(42)
n = 800

# Simulate realistic PCOS data
# Features: cycle_length, pain_level, irregular_periods, weight_gain, acne, hair_growth, skin_darkening, fast_food
cycle_length    = np.random.randint(21, 55, n)
pain_level      = np.random.randint(1, 11, n)
irregular_periods = np.random.randint(0, 2, n)
weight_gain     = np.random.randint(0, 2, n)
acne            = np.random.randint(0, 2, n)
hair_growth     = np.random.randint(0, 2, n)
skin_darkening  = np.random.randint(0, 2, n)
fast_food       = np.random.randint(0, 2, n)

# Compute rule-based score for labeling
score = (
    (cycle_length > 35).astype(int) * 2 +
    (pain_level > 6).astype(int) * 2 +
    weight_gain * 1 +
    acne * 1 +
    hair_growth * 1 +
    skin_darkening * 0.5 +
    fast_food * 0.5 +
    irregular_periods * 1
)

# Map score to risk labels (0=low, 1=moderate, 2=high)
risk = np.where(score >= 5, 2, np.where(score >= 3, 1, 0))

X = np.column_stack([
    cycle_length, pain_level, irregular_periods,
    weight_gain, acne, hair_growth, skin_darkening, fast_food
])
y = risk

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

model = GradientBoostingClassifier(n_estimators=100, learning_rate=0.1, random_state=42)
model.fit(X_train, y_train)

print(classification_report(y_test, model.predict(X_test)))
joblib.dump(model, "model.pkl")
print("✅ model.pkl saved successfully.")
