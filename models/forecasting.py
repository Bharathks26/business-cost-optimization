import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

def ensure_datetime_column(df, col_name):
    df = df.copy()
    if not pd.api.types.is_datetime64_any_dtype(df[col_name]):
        df[col_name] = pd.to_datetime(df[col_name], errors="coerce")
    return df

def forecast_monthly_expenses(df, months_ahead=3):
    """
    Forecast monthly business expenses using Linear Regression.
    
    Args:
        df: DataFrame with columns [date, amount]
        months_ahead: Number of months to forecast (default 3)
    
    Returns:
        Dictionary with historical and forecasted monthly totals
    """
    # Convert date to datetime
    df = ensure_datetime_column(df, 'date')
    
    # Group by month and sum expenses
    df['month'] = df['date'].dt.to_period('M')
    monthly_totals = df.groupby('month')['amount'].sum().reset_index()
    monthly_totals['month_num'] = range(len(monthly_totals))
    
    # Prepare data for Linear Regression
    X = monthly_totals[['month_num']]
    y = monthly_totals['amount']
    
    # Train Linear Regression model
    model = LinearRegression()
    model.fit(X, y)
    
    # Generate future month numbers
    last_month_num = monthly_totals['month_num'].max()
    future_months = range(last_month_num + 1, last_month_num + months_ahead + 1)
    
    # Predict future expenses
    future_X = pd.DataFrame({'month_num': future_months})
    forecasted_amounts = model.predict(future_X)
    
    # Ensure predictions are realistic (non-negative and reasonable)
    min_historical = monthly_totals['amount'].min()
    forecasted_amounts = np.maximum(forecasted_amounts, min_historical * 0.5)
    
    # Generate future month periods
    last_period = monthly_totals['month'].iloc[-1]
    future_periods = [last_period + i for i in range(1, months_ahead + 1)]
    
    # Prepare results
    historical = {
        'months': [str(month) for month in monthly_totals['month']],
        'amounts': monthly_totals['amount'].tolist()
    }
    
    forecasted = {
        'months': [str(month) for month in future_periods],
        'amounts': forecasted_amounts.tolist()
    }
    
    return {
        'historical': historical,
        'forecasted': forecasted
    }