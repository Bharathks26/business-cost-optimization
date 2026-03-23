import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import LabelEncoder, StandardScaler

def generate_anomaly_explanation(row, stats):
    """
    Explainable AI: Generate human-readable explanation using statistical deviation analysis.
    Compares expense features (amount, department, vendor) against historical baselines.
    """
    amount = row['amount']
    department = row['department']
    vendor = row['vendor']
    
    # Feature-based analysis: Compare against department and overall averages
    dept_avg = stats['dept_averages'].get(department, amount)
    overall_avg = stats['overall_mean']
    vendor_count = stats['vendor_counts'].get(vendor, 1)
    
    # Statistical deviation calculation: Percentage difference from baselines
    dept_diff = ((amount - dept_avg) / dept_avg) * 100 if dept_avg > 0 else 0
    overall_diff = ((amount - overall_avg) / overall_avg) * 100 if overall_avg > 0 else 0
    
    reasons = []
    
    # Explainable thresholds: Clear business rules for anomaly classification
    if abs(dept_diff) > 50:  # 50% deviation threshold
        direction = "above" if dept_diff > 0 else "below"
        reasons.append(f"{abs(dept_diff):.0f}% {direction} {department} average")
    
    if abs(overall_diff) > 100:  # 100% deviation threshold
        direction = "above" if overall_diff > 0 else "below"
        reasons.append(f"{abs(overall_diff):.0f}% {direction} overall average")
    
    # Feature-based rarity detection: Vendor frequency analysis
    if vendor_count <= 2:
        reasons.append(f"rare vendor ({vendor_count} occurrence{'s' if vendor_count > 1 else ''})")
    
    # Human-readable explanation combining statistical insights
    if reasons:
        return f"₹{amount:,.0f}: " + "; ".join(reasons)
    else:
        return f"₹{amount:,.0f}: unusual spending pattern detected"

def detect_expense_anomalies(df, contamination=0.1):
    """
    Explainable AI anomaly detection using Isolation Forest with statistical explanations.
    Combines ML detection with feature-based reasoning for transparency.
    """
    result_df = df.copy()
    
    # Statistical baseline calculation for explainable comparisons
    stats = {
        'dept_averages': df.groupby('department')['amount'].mean().to_dict(),
        'overall_mean': df['amount'].mean(),
        'vendor_counts': df['vendor'].value_counts().to_dict()
    }
    
    # Feature encoding for ML model (department, vendor, amount)
    le_dept = LabelEncoder()
    le_vendor = LabelEncoder()
    
    result_df['dept_encoded'] = le_dept.fit_transform(df['department'])
    result_df['vendor_encoded'] = le_vendor.fit_transform(df['vendor'])
    
    # Feature scaling for consistent ML input
    scaler = StandardScaler()
    result_df['amount_scaled'] = scaler.fit_transform(df[['amount']])
    
    # ML-based anomaly detection using multi-dimensional feature space
    features = result_df[['dept_encoded', 'vendor_encoded', 'amount_scaled']]
    
    iso_forest = IsolationForest(contamination=contamination, random_state=42)
    predictions = iso_forest.fit_predict(features)
    anomaly_scores = iso_forest.decision_function(features)
    
    # Binary classification: Convert ML output to business-friendly flags
    result_df['anomaly_flag'] = (predictions == -1).astype(int)
    result_df['anomaly_score'] = anomaly_scores
    
    # Explainable AI: Generate statistical explanations for each detected anomaly
    explanations = []
    for idx, row in result_df.iterrows():
        if row['anomaly_flag'] == 1:
            explanation = generate_anomaly_explanation(row, stats)
            explanations.append(explanation)
        else:
            explanations.append("")
    
    result_df['explanation'] = explanations
    
    # Clean output: Remove temporary ML features
    result_df = result_df.drop(['dept_encoded', 'vendor_encoded', 'amount_scaled'], axis=1)
    
    return result_df