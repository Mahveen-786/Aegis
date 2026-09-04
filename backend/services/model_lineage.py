"""
model_lineage.py - Persist trained models and record what produced them.

Previously nothing recorded what produced a given metric: models retrained
from scratch (fixed seed, in-memory only) on every server start, so a
metrics screen was only ever "trust me" -- restarting the server proved
nothing about reproducibility from a saved artifact, only that the same
code+seed happens to regenerate similar numbers.

This module (a) hashes the training data so a lineage record can prove
*which* data produced a model, (b) persists the fitted model + a JSON
sidecar with joblib, and (c) returns a lineage record meant to be logged
into audit_store.py's model_lineage table so /dashboard/metrics can say
"these numbers came from model v3, trained on data hash a1b2c3, at
<timestamp>" instead of implicitly "whatever's currently in memory."
"""
import hashlib
import json
import os
import sklearn
from datetime import datetime, timezone

import joblib
import pandas as pd

MODEL_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "artifacts")


def hash_dataframe(df: pd.DataFrame) -> str:
    """Deterministic content hash of a dataframe's values, so a lineage
    record can prove which exact dataset produced a given model rather than
    just asserting it."""
    h = hashlib.sha256()
    h.update(pd.util.hash_pandas_object(df, index=True).values.tobytes())
    h.update(str(sorted(df.columns.tolist())).encode())
    return h.hexdigest()[:16]


def save_model(model_obj, persona: str, module_name: str, model_version: str,
               training_data_hash: str, seed: int, metrics: dict) -> dict:
    """Persists the fitted model object with joblib, keyed by a lineage
    record. Returns the lineage record (also meant to be written to
    audit_store's model_lineage table)."""
    os.makedirs(MODEL_DIR, exist_ok=True)
    filename = f"{persona}__{module_name}__{model_version}.joblib"
    path = os.path.join(MODEL_DIR, filename)
    joblib.dump(model_obj, path)

    lineage = {
        "persona": persona,
        "module_name": module_name,
        "model_version": model_version,
        "artifact_path": path,
        "training_data_hash": training_data_hash,
        "sklearn_version": sklearn.__version__,
        "seed": seed,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "metrics_snapshot": metrics,
    }
    sidecar_path = os.path.join(MODEL_DIR, f"{persona}__{module_name}__{model_version}.json")
    with open(sidecar_path, "w") as f:
        json.dump(lineage, f, indent=2, default=str)

    return lineage


def load_model(persona: str, module_name: str, model_version: str):
    path = os.path.join(MODEL_DIR, f"{persona}__{module_name}__{model_version}.joblib")
    if not os.path.exists(path):
        return None
    return joblib.load(path)


def make_model_version(training_data_hash: str, seed: int) -> str:
    """Short, stable version id derived from what actually produced the
    model -- same data hash + same seed always yields the same version id,
    so it's a reproducibility fingerprint, not just an incrementing counter."""
    basis = f"{training_data_hash}:{seed}:{sklearn.__version__}"
    return "v" + hashlib.sha256(basis.encode()).hexdigest()[:10]
