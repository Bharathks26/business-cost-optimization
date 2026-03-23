from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file, abort
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import pandas as pd
from functools import wraps
from kpi_calculator import calculate_all_kpis
from models.analytics import detect_expense_anomalies
from models.forecasting import forecast_monthly_expenses
from models.recommendations import generate_cost_recommendations
from models.reports import generate_business_report

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('role') != 'admin':
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///business_optimization.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'your-secret-key'

db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), default='user')
    email = db.Column(db.String(120), nullable=True)
    company_name = db.Column(db.String(200), nullable=True)
    industry = db.Column(db.String(100), nullable=True)
    department = db.Column(db.String(100), nullable=True)
    budget_range = db.Column(db.String(50), nullable=True)
    cost_target = db.Column(db.Integer, nullable=True)
    last_login = db.Column(db.DateTime, nullable=True)

class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    department = db.Column(db.String(100), nullable=False)
    vendor = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)

def get_expense_data():
    """Get expense data - all data for admin, user-specific for regular users"""
    if session.get('role') == 'admin':
        expenses = Expense.query.all()
    else:
        expenses = Expense.query.filter_by(user_id=session.get('user_id')).all()
    return pd.DataFrame([{'department': exp.department, 'vendor': exp.vendor, 'amount': exp.amount, 'date': exp.date} for exp in expenses]) if expenses else pd.DataFrame()

def ensure_datetime_column(df, col_name):
    if not df.empty and not pd.api.types.is_datetime64_any_dtype(df[col_name]):
        df[col_name] = pd.to_datetime(df[col_name], errors="coerce")
    return df

@app.route('/', methods=['GET', 'POST'])
def home():
    user_role = session.get('role', 'guest')
    return render_template('home.html', user_role=user_role)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = generate_password_hash(request.form['password'])
        email = request.form.get('email')
        company_name = request.form.get('company_name')
        industry = request.form.get('industry')
        other_industry = request.form.get('other_industry')
        department = request.form.get('department')
        budget_range = request.form.get('budget_range')
        cost_target = request.form.get('cost_target')
        
        # Use other_industry if industry is 'other'
        if industry == 'other' and other_industry:
            industry = other_industry
        
        user = User(
            username=username, 
            password=password, 
            email=email,
            role='user',
            company_name=company_name,
            industry=industry,
            department=department,
            budget_range=budget_range,
            cost_target=int(cost_target) if cost_target else None
        )
        db.session.add(user)
        db.session.commit()
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        try:
            user = User.query.filter_by(username=username).first()
            if user and check_password_hash(user.password, password):
                user_role = getattr(user, 'role', 'user') or 'user'
                if user_role.strip() == '':
                    user_role = 'user'
                
                user.last_login = datetime.now()
                db.session.commit()
                
                session['user_id'] = user.id
                session['username'] = user.username
                session['role'] = user_role
                
                if user_role == 'admin':
                    return redirect(url_for('admin_dashboard'))
                else:
                    return redirect(url_for('home'))
            else:
                flash('Invalid username or password', 'error')
        except Exception as e:
            flash('Login error occurred', 'error')
    return render_template('login.html')

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        username = request.form['username']
        new_password = request.form['new_password']
        confirm_password = request.form['confirm_password']
        
        if new_password != confirm_password:
            flash('Passwords do not match', 'error')
            return render_template('forgot_password.html')
        
        user = User.query.filter_by(username=username).first()
        if user:
            user.password = generate_password_hash(new_password)
            db.session.commit()
            flash('Password reset successful! Please login.', 'success')
            return redirect(url_for('login'))
        else:
            flash('Username not found', 'error')
    return render_template('forgot_password.html')

@app.route('/logout', methods=['GET', 'POST'])
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/upload-expenses', methods=['GET', 'POST'])
def upload_expenses():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        file = request.files['file']
        if not file or not file.filename.endswith('.csv'):
            flash('Please select a valid CSV file', 'error')
            return render_template('upload_expenses.html')
        
        df = pd.read_csv(file)
        required_cols = ['department', 'vendor', 'amount', 'date']
        if not all(col in df.columns for col in required_cols):
            flash('CSV must contain columns: department, vendor, amount, date', 'error')
            return render_template('upload_expenses.html')
        
        df = df.dropna()
        if df.empty:
            flash('No valid records found in CSV', 'error')
            return render_template('upload_expenses.html')
        
        df['date'] = pd.to_datetime(df['date'], errors='coerce').dt.date
        
        for _, row in df.iterrows():
            expense = Expense(
                department=row['department'],
                vendor=row['vendor'],
                amount=float(row['amount']),
                date=row['date'],
                user_id=session['user_id']
            )
            db.session.add(expense)
        
        db.session.commit()
        flash(f'Successfully uploaded {len(df)} expense records', 'success')
        return redirect(url_for('dashboard'))
    
    return render_template('upload_expenses.html')

@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('dashboard.html', expenses=Expense.query.all())

@app.route('/kpi-analysis', methods=['GET', 'POST'])
def kpi_analysis():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    df = get_expense_data()
    kpis = calculate_all_kpis(ensure_datetime_column(df, 'date')) if not df.empty else {}
    return render_template('kpi_analysis.html', kpis=kpis)

@app.route('/anomaly-detection', methods=['GET', 'POST'])
def anomaly_detection():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    df = get_expense_data()
    anomaly_list = []
    if not df.empty:
        result_df = detect_expense_anomalies(df)
        anomaly_list = result_df[result_df['anomaly_flag'] == 1].to_dict('records')
    
    return render_template('anomaly_detection.html', anomalies=anomaly_list)

@app.route('/forecasting', methods=['GET', 'POST'])
def forecasting():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    df = get_expense_data()
    forecast_data = forecast_monthly_expenses(df[['date', 'amount']]) if not df.empty else {'historical': {'months': [], 'amounts': []}, 'forecasted': {'months': [], 'amounts': []}}
    return render_template('forecasting.html', forecast=forecast_data)

@app.route('/admin-dashboard', methods=['GET', 'POST'])
@admin_required
def admin_dashboard():
    return render_template('admin_dashboard.html')

@app.route('/admin/users', methods=['GET', 'POST'])
@admin_required
def admin_users():
    users = User.query.filter(User.role != 'admin').all()
    user_data = []
    for user in users:
        user_expenses = Expense.query.filter_by(user_id=user.id).all()
        expense_count = len(user_expenses)
        total_amount = sum(exp.amount for exp in user_expenses)
        user_data.append({
            'user': user,
            'expense_count': expense_count,
            'total_amount': total_amount
        })
    return render_template('admin_users.html', user_data=user_data)

@app.route('/admin/user/<int:user_id>', methods=['GET', 'POST'])
@admin_required
def admin_user_detail(user_id):
    user = User.query.get_or_404(user_id)
    expenses = Expense.query.filter_by(user_id=user_id).all()
    return render_template('admin_user_detail.html', user=user, expenses=expenses)

@app.route('/recommendations', methods=['GET', 'POST'])
def recommendations():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    df = get_expense_data()
    if df.empty:
        return render_template('recommendations.html', recommendations=["No expense data available"])
    
    df = ensure_datetime_column(df, 'date')
    kpis = calculate_all_kpis(df)
    anomalies = detect_expense_anomalies(df)
    forecast_data = forecast_monthly_expenses(df[['date', 'amount']])
    recommendations_list = generate_cost_recommendations(df, kpis, anomalies.to_dict('records'), forecast_data)
    
    return render_template('recommendations.html', recommendations=recommendations_list)

@app.route('/analytics-dashboard', methods=['GET', 'POST'])
def analytics_dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    df = get_expense_data()
    if df.empty:
        dashboard_data = {"kpis": {"totalCost": 0, "avgMonthly": 0, "anomalyCount": 0, "departmentCount": 0}, "monthly": {"labels": [], "data": []}, "departments": {"labels": [], "data": []}, "vendors": {"labels": [], "data": []}, "anomalies": [], "insights": {"anomaly_summary": "No data available for analysis.", "recommendation_summary": "Upload expense data to generate insights."}}
    else:
        df = ensure_datetime_column(df, 'date')
        kpis = calculate_all_kpis(df) or {}
        anomalies_df = detect_expense_anomalies(df)
        anomaly_count = len(anomalies_df[anomalies_df['anomaly_flag'] == 1]) if not anomalies_df.empty else 0
        
        # Generate explainable insights
        anomaly_insights = []
        recommendation_insights = []
        
        # Anomaly insights
        if anomaly_count > 0:
            anomalies_list = anomalies_df[anomalies_df['anomaly_flag'] == 1]
            high_anomalies = len(anomalies_list[anomalies_list['anomaly_score'] < -0.2])
            if high_anomalies > 0:
                anomaly_insights.append(f"{high_anomalies} high-risk transactions detected due to significant deviations from normal spending patterns")
            if anomaly_count > 5:
                anomaly_insights.append(f"Multiple unusual expenses ({anomaly_count} total) suggest potential process issues or data entry errors")
        else:
            anomaly_insights.append("No anomalies detected - all expenses follow expected patterns")
        
        # Recommendation insights
        if kpis.get('department_cost'):
            dept_costs = kpis['department_cost']
            total_cost = sum(dept_costs.values())
            high_cost_depts = [dept for dept, cost in dept_costs.items() if cost / total_cost > 0.4]
            if high_cost_depts:
                recommendation_insights.append(f"{high_cost_depts[0]} department dominates spending, suggesting need for cost controls")
        
        if not df.empty:
            vendor_costs = df.groupby('vendor')['amount'].sum()
            if len(vendor_costs) > 0:
                top_vendor_pct = vendor_costs.max() / vendor_costs.sum()
                if top_vendor_pct > 0.3:
                    recommendation_insights.append(f"High vendor concentration risk detected - single vendor accounts for {top_vendor_pct:.1%} of spending")
        
        if not recommendation_insights:
            recommendation_insights.append("Spending patterns appear balanced with no immediate optimization needs")
        
        # Generate vendor data for chart
        vendor_data = {"labels": [], "data": []}
        if not df.empty:
            vendor_totals = df.groupby('vendor')['amount'].sum().sort_values(ascending=False).head(5)
            vendor_data = {
                "labels": vendor_totals.index.tolist(),
                "data": vendor_totals.values.tolist()
            }
        
        dashboard_data = {
            "kpis": {"totalCost": sum(kpis.get('department_cost', {}).values()), "avgMonthly": sum(kpis.get('monthly_cost', {}).values()) / max(len(kpis.get('monthly_cost', {})), 1), "anomalyCount": anomaly_count, "departmentCount": df['department'].nunique()},
            "monthly": {"labels": list(map(str, kpis.get('monthly_cost', {}).keys())), "data": list(kpis.get('monthly_cost', {}).values())},
            "departments": {"labels": list(kpis.get('department_cost', {}).keys()), "data": list(kpis.get('department_cost', {}).values())},
            "vendors": vendor_data,
            "anomalies": [],
            "insights": {
                "anomaly_summary": " ".join(anomaly_insights),
                "recommendation_summary": " ".join(recommendation_insights)
            }
        }
    
    return render_template('analytics_dashboard.html', dashboard_data=dashboard_data)

@app.route('/download-report', methods=['GET'])
def download_report():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if session.get('role') == 'admin':
        users = User.query.filter(User.role != 'admin').all()
        return render_template('download_report.html', users=users, is_admin=True)
    else:
        return render_template('download_report.html', is_admin=False)

@app.route('/download-report-file', methods=['POST'])
def download_report_file():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if session.get('role') == 'admin':
        user_id = request.form.get('user_id')
        if user_id:
            user_expenses = Expense.query.filter_by(user_id=int(user_id)).all()
            user = User.query.get(int(user_id))
            username = user.username if user else 'user'
        else:
            user_expenses = Expense.query.all()
            username = 'all_users'
        df = pd.DataFrame([{'department': exp.department, 'vendor': exp.vendor, 'amount': exp.amount, 'date': exp.date} for exp in user_expenses]) if user_expenses else pd.DataFrame()
    else:
        user_expenses = Expense.query.filter_by(user_id=session['user_id']).all()
        df = pd.DataFrame([{'department': exp.department, 'vendor': exp.vendor, 'amount': exp.amount, 'date': exp.date} for exp in user_expenses]) if user_expenses else pd.DataFrame()
        username = session.get('username', 'user')
    
    if df.empty:
        flash('No data available for download', 'error')
        return redirect(url_for('download_report'))
    
    df = ensure_datetime_column(df, 'date')
    kpis = calculate_all_kpis(df) or {}
    anomalies_df = detect_expense_anomalies(df)
    forecast_data = forecast_monthly_expenses(df[['date', 'amount']])
    
    return send_file(generate_business_report(df, kpis, anomalies_df, forecast_data, username), as_attachment=True)

@app.route('/delete-data', methods=['POST'])
@admin_required
def delete_data():
    Expense.query.delete()
    db.session.commit()
    return {'success': True, 'message': 'All data deleted successfully'}

@app.route('/reset-database', methods=['POST'])
@admin_required 
def reset_database():
    db.drop_all()
    db.create_all()
    return {'success': True, 'message': 'Database reset successfully'}

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        flash('Thank you for your feedback! We will get back to you soon.', 'success')
        return redirect(url_for('contact'))
    return render_template('contact.html')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        
        # Add last_login column if it doesn't exist
        try:
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            columns = [col['name'] for col in inspector.get_columns('user')]
            if 'last_login' not in columns:
                with db.engine.connect() as conn:
                    conn.execute(db.text('ALTER TABLE user ADD COLUMN last_login DATETIME'))
                    conn.commit()
        except:
            pass
        
        # Only create admin if it doesn't exist
        if not User.query.filter_by(username='admin').first():
            admin = User(username='admin', password=generate_password_hash('admin123'), role='admin')
            db.session.add(admin)
            db.session.commit()
    app.run(debug=True, use_reloader=False)