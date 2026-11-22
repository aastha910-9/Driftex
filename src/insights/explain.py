"""SHAP global explanation + one local customer example (Aastha). SHAP explains MODEL OUTPUT, not causality."""
import json
import numpy as np
import pandas as pd
import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from src.common import C
from src.prediction.train import FEATURE_SETS, load_dataset


def shap_matrix(pipe, X):
    import shap
    Z = pipe.named_steps["pre"].transform(X)
    clf = pipe.named_steps["clf"]
    if hasattr(clf, "feature_importances_"):
        sv = shap.TreeExplainer(clf).shap_values(Z)
    else:
        sv = shap.LinearExplainer(clf, Z).shap_values(Z)
    sv = np.array(sv[1]) if isinstance(sv, list) else np.array(sv)
    if sv.ndim == 3:
        sv = sv[:, :, 1]
    return sv, Z


def main():
    try:
        import shap  # noqa: F401
    except ImportError:
        raise SystemExit("shap is not installed: pip install shap")
    info = json.loads((C.TABLES / "experiment_summary.json").read_text())
    best = info["best_drift_enhanced_model"]
    pipe = joblib.load(C.MODELS / f"{best.replace(' ', '_')}__drift_enhanced.joblib")
    cols = FEATURE_SETS["drift_enhanced"]
    full, labels = load_dataset()
    data = full.merge(labels, on=["customer_id", "observation_date"])
    test = data[data["observation_date"] >= pd.Timestamp(info["test_start"])]
    samp = test.sample(min(2000, len(test)), random_state=C.RANDOM_STATE).reset_index(drop=True)
    sv, Z = shap_matrix(pipe, samp[cols])
    imp = pd.DataFrame({"feature": cols, "mean_abs_shap": np.abs(sv).mean(0)}).sort_values("mean_abs_shap", ascending=False)
    imp.to_csv(C.TABLES / "shap_global.csv", index=False)
    import shap
    plt.figure(); shap.summary_plot(sv, Z, feature_names=cols, show=False)
    plt.title(f"SHAP global explanation - {best} (drift-enhanced)"); plt.tight_layout()
    plt.savefig(C.FIGS / "shap_global.png", dpi=140); plt.close()
    # local example: customer with the highest predicted inactivity risk in the sample
    i = int(np.argmax(pipe.predict_proba(samp[cols])[:, 1]))
    loc = pd.DataFrame({"feature": cols, "value": samp.loc[i, cols].values, "shap_contribution": sv[i]}).sort_values("shap_contribution", key=abs, ascending=False)
    loc.to_csv(C.TABLES / "shap_local.csv", index=False)
    top = loc.head(10).iloc[::-1]
    plt.figure(figsize=(7, 4.5)); plt.barh(top["feature"], top["shap_contribution"], color=np.where(top["shap_contribution"] > 0, "#d1343c", "#14915b"))
    plt.axvline(0, color="grey", lw=.8)
    plt.title(f"Local explanation - customer {int(samp.loc[i, 'customer_id'])} on {samp.loc[i, 'observation_date'].date()}\n(red pushes towards 'inactive', green away)")
    plt.tight_layout(); plt.savefig(C.FIGS / "shap_local.png", dpi=140); plt.close()
    print("SHAP saved. top global features:", imp.head(5)["feature"].tolist())


if __name__ == "__main__":
    main()
