import pandas as pd
import numpy as np

def ensure_datetime_column(df, col_name):
    df = df.copy()
    if not pd.api.types.is_datetime64_any_dtype(df[col_name]):
        df[col_name] = pd.to_datetime(df[col_name], errors="coerce")
    return df

def calculate_monthly_cost(df):
    """Calculate total monthly cost."""
    df = ensure_datetime_column(df, 'date')
    df['month'] = df['date'].dt.to_period('M')
    monthly_cost = df.groupby('month')['amount'].sum().to_dict()
    return {str(k): v for k, v in monthly_cost.items()}

def calculate_department_cost(df):
    """Calculate department-wise cost."""
    dept_cost = df.groupby('department')['amount'].sum().to_dict()
    return dept_cost

def calculate_cost_growth_rate(df):
    """Calculate month-over-month cost growth rate."""
    df = ensure_datetime_column(df, 'date')
    df['month'] = df['date'].dt.to_period('M')
    monthly_cost = df.groupby('month')['amount'].sum()
    growth_rate = monthly_cost.pct_change().fillna(0).to_dict()
    return {str(k): v for k, v in growth_rate.items()}

def calculate_budget_variance(df, budget_dict):
    """Calculate budget variance by department."""
    dept_cost = df.groupby('department')['amount'].sum()
    variance = {}
    for dept in dept_cost.index:
        actual = dept_cost[dept]
        budget = budget_dict.get(dept, actual)
        variance[dept] = (actual - budget) / budget if budget > 0 else 0
    return variance

def calculate_vendor_concentration(df):
    """Calculate vendor concentration ratio (top 3 vendors' share)."""
    vendor_cost = df.groupby('vendor')['amount'].sum().sort_values(ascending=False)
    total_cost = vendor_cost.sum()
    top3_share = vendor_cost.head(3).sum() / total_cost if total_cost > 0 else 0
    return {'concentration_ratio': top3_share, 'vendor_costs': vendor_cost.to_dict()}

def calculate_all_kpis(df, budget_dict=None):
    """Calculate all KPIs and return in dictionary format."""
    if budget_dict is None:
        budget_dict = {}
    
    return {
        'monthly_cost': calculate_monthly_cost(df),
        'department_cost': calculate_department_cost(df),
        'cost_growth_rate': calculate_cost_growth_rate(df),
        'budget_variance': calculate_budget_variance(df, budget_dict),
        'vendor_concentration': calculate_vendor_concentration(df)
    }