import numpy as np
import pandas as pd
from src.prediction.train import build_pipeline, FEATURE_SETS


def test_shap_values_generated():
    try:
        import shap  # noqa: F401
    except ImportError:
        print("SKIP: shap not installed"); return
    from src.insights.explain import shap_matrix
    rng = np.random.default_rng(0); cols = FEATURE_SETS["drift_enhanced"]
    X = pd.DataFrame(rng.normal(size=(300, len(cols))), columns=cols); y = (X[cols[0]] > 0).astype(int)
    for name in ["Logistic Regression", "Random Forest"]:
        sv, Z = shap_matrix(build_pipeline(name, cols, 1.0).fit(X, y), X.head(50))
        assert sv.shape == (50, len(cols))
