import pandas as pd
import numpy as np

def generate_cost_recommendations(df, kpis, anomalies, forecast):
    """
    Explainable AI: Generate cost optimization recommendations using feature-based analysis.
    Combines statistical thresholds with business logic for transparent decision-making.
    """
    recommendations = []
    
    # Feature-based analysis: Department cost concentration detection
    if kpis.get('department_cost'):
        dept_costs = kpis['department_cost']
        total_cost = sum(dept_costs.values())
        
        # Statistical threshold: 40% concentration rule
        for dept, cost in dept_costs.items():
            if cost / total_cost > 0.4:
                recommendations.append({
                    'recommendation': f"Review {dept} department spending and implement cost controls",
                    'reason': f"Department accounts for {cost/total_cost:.1%} of total costs (₹{cost:,.0f}), exceeding 40% threshold"
                })
    
    # Feature-based vendor risk analysis: Concentration detection
    if not df.empty:
        vendor_costs = df.groupby('vendor')['amount'].sum().sort_values(ascending=False)
        top_vendor = vendor_costs.index[0]
        top_cost = vendor_costs.iloc[0]
        total_cost = vendor_costs.sum()
        
        # Statistical threshold: 30% vendor concentration rule
        if top_cost / total_cost > 0.3:
            recommendations.append({
                'recommendation': f"Diversify vendor base to reduce dependency on {top_vendor}",
                'reason': f"Single vendor represents {top_cost/total_cost:.1%} of total spending (₹{top_cost:,.0f}), creating concentration risk"
            })
    
    # Anomaly-based recommendations: Statistical deviation analysis
    if anomalies:
        # High-risk threshold: Anomaly score < -0.2 indicates severe deviation
        high_anomalies = [a for a in anomalies if a.get('anomaly_score', 0) < -0.2]
        if high_anomalies:
            recommendations.append({
                'recommendation': f"Investigate {len(high_anomalies)} high-risk transactions for fraud or errors",
                'reason': f"Anomaly detection flagged {len(high_anomalies)} expenses with severe deviation from normal patterns"
            })
        
        # Volume-based threshold: >10 anomalies suggests systemic issues
        if len(anomalies) > 10:
            recommendations.append({
                'recommendation': "Strengthen expense approval process and controls",
                'reason': f"{len(anomalies)} unusual transactions detected, indicating potential process gaps"
            })
    
    # Trend-based analysis: Growth rate statistical thresholds
    if kpis.get('cost_growth_rate'):
        growth_rates = kpis['cost_growth_rate']
        # Statistical threshold: 20% growth rate indicates unsustainable trend
        high_growth = [(month, rate) for month, rate in growth_rates.items() if rate > 0.2]
        
        if high_growth:
            month, rate = high_growth[0]
            recommendations.append({
                'recommendation': "Implement immediate cost reduction measures",
                'reason': f"Cost trend shows {rate:.1%} increase in {month}, indicating unsustainable growth pattern"
            })
    
    # Predictive analysis: Forecast-based recommendations using historical baselines
    if forecast.get('forecasted', {}).get('amounts') and forecast.get('historical', {}).get('amounts'):
        historical_avg = np.mean(forecast['historical']['amounts'])
        forecasted_avg = np.mean(forecast['forecasted']['amounts'])
        
        # Statistical threshold: 15% forecast increase triggers budget alert
        if forecasted_avg > historical_avg * 1.15:
            recommendations.append({
                'recommendation': "Prepare budget adjustments for anticipated cost increases",
                'reason': f"Forecasted rise of {(forecasted_avg/historical_avg-1):.1%} in monthly expenses compared to historical baseline"
            })
    
    # Efficiency analysis: Department performance comparison using statistical deviation
    if not df.empty and len(df['department'].unique()) > 1:
        dept_avg_expense = df.groupby('department')['amount'].mean()
        overall_avg = df['amount'].mean()
        
        # Statistical threshold: 50% above average indicates inefficiency
        inefficient_depts = [(dept, avg) for dept, avg in dept_avg_expense.items() if avg > overall_avg * 1.5]
        if inefficient_depts:
            dept, avg_expense = inefficient_depts[0]
            recommendations.append({
                'recommendation': f"Optimize {dept} spending patterns and transaction sizes",
                'reason': f"Average transaction ₹{avg_expense:,.0f} vs company average ₹{overall_avg:,.0f}, indicating inefficient spending"
            })
    
    # Default case: No statistical anomalies detected
    if not recommendations:
        recommendations.append({
            'recommendation': "Continue monitoring expense patterns for optimization opportunities",
            'reason': "Current spending patterns appear normal with no immediate concerns identified"
        })
    
    return recommendations