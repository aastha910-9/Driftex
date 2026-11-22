"""One command for the whole project:  python run_all.py
Steps: customer-day activity -> drift -> labels -> features -> models -> segments -> value -> SHAP -> risk priority
       -> product-interest tables (for the optional HTML dashboard)."""
import subprocess, sys
from pathlib import Path
here = Path(__file__).resolve().parent
STEPS = [["-m", "src.drift.run_drift", "--build"], ["-m", "src.prediction.labels"], ["-m", "src.prediction.features"],
         ["-m", "src.prediction.train"], ["-m", "src.insights.segments"], ["-m", "src.insights.value_proxy"],
         ["-m", "src.insights.explain"], ["-m", "src.insights.risk_priority"],
         ["pipeline/01_build_metrics.py"], ["pipeline/02_train_models.py"]]
optional = {"src.insights.explain"}          # needs the shap package; the rest still runs without it
for s in STEPS:
    print(f"\n=== {' '.join(s)} ===", flush=True)
    rc = subprocess.call([sys.executable, *s], cwd=here)
    if rc != 0:
        if s[-1] in optional:
            print("!! step skipped (install shap to enable explanations)"); continue
        sys.exit("Stopped - see the error above.")
print("\nDone.\n  Streamlit dashboard (main):      streamlit run src/dashboard/app.py"
      "\n  Product-interest dashboard (HTML): python app/server.py   -> http://localhost:8000")
