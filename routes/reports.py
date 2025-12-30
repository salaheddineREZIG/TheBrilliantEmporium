from flask import Blueprint, render_template, jsonify, request, url_for
from flask_login import login_required, current_user
from datetime import datetime, date, timedelta
from sqlalchemy import func, extract, and_, or_
from extensions import db
from models import Transaction, Account, Category, Budget, TransactionType
import calendar

reports_bp = Blueprint('reports', __name__)

@reports_bp.route('/')
@login_required
def index():
    """Reports dashboard"""
    # Provide endpoint URLs to the client-side code so JS can build requests safely
    endpoints = {
        'spending_by_category': url_for('reports.spending_by_category'),
        'income_vs_expense': url_for('reports.income_vs_expense'),
        'account_balance_history': url_for('reports.account_balance_history'),
        'budget_vs_actual': url_for('reports.budget_vs_actual'),
        'export_full_report': url_for('reports.export_full_report')
    }
    return render_template('reports/index.html', endpoints=endpoints)

@reports_bp.route('/spending-by-category')
@login_required
def spending_by_category():
    """Spending by category report"""
    # Get date range
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    
    if date_from:
        date_from = datetime.strptime(date_from, '%Y-%m-%d').date()
    else:
        # Default to start of current year
        today = date.today()
        date_from = date(today.year, 1, 1)
    
    if date_to:
        date_to = datetime.strptime(date_to, '%Y-%m-%d').date()
    else:
        date_to = date.today()
    
    # Get spending by category
    spending = db.session.query(
        Category.name,
        Category.icon,
        Category.color,
        func.sum(Transaction.amount).label('total')
    ).join(
        Transaction, Transaction.category_id == Category.id
    ).filter(
        Transaction.user_id == current_user.id,
        Transaction.type == TransactionType.EXPENSE,
        Transaction.date >= date_from,
        Transaction.date <= date_to,
        Category.is_active == True
    ).group_by(Category.id, Category.name, Category.icon, Category.color).all()
    
    total_spent = sum(float(item.total) for item in spending)
    
    # Prepare data for chart
    chart_data = []
    for item in spending:
        percentage = (float(item.total) / total_spent * 100) if total_spent > 0 else 0
        chart_data.append({
            'name': item.name,
            'value': float(item.total),
            'percentage': round(percentage, 1),
            'icon': item.icon,
            'color': item.color
        })
    
    return jsonify({
        'date_from': date_from.isoformat(),
        'date_to': date_to.isoformat(),
        'total_spent': total_spent,
        'data': chart_data
    })

@reports_bp.route('/income-vs-expense')
@login_required
def income_vs_expense():
    """Income vs Expense trend report"""
    # Get date range (default last 12 months)
    months = request.args.get('months', 12, type=int)
    
    end_date = date.today()
    start_date = end_date - timedelta(days=30*months)
    
    # Generate all months in range
    months_data = []
    current = start_date.replace(day=1)
    while current <= end_date:
        months_data.append({
            'label': f"{current.year}-{current.month:02d}",
            'year': current.year,
            'month': current.month
        })
        
        # Next month
        if current.month == 12:
            current = date(current.year + 1, 1, 1)
        else:
            current = date(current.year, current.month + 1, 1)
    
    # Get income and expense for each month
    for month_data in months_data:
        month_start = date(month_data['year'], month_data['month'], 1)
        if month_data['month'] == 12:
            month_end = date(month_data['year'] + 1, 1, 1) - timedelta(days=1)
        else:
            month_end = date(month_data['year'], month_data['month'] + 1, 1) - timedelta(days=1)
        
        # Income
        income = db.session.query(
            func.coalesce(func.sum(Transaction.amount), 0)
        ).filter(
            Transaction.user_id == current_user.id,
            Transaction.type == TransactionType.INCOME,
            Transaction.date >= month_start,
            Transaction.date <= month_end
        ).scalar() or 0
        
        # Expense
        expense = db.session.query(
            func.coalesce(func.sum(Transaction.amount), 0)
        ).filter(
            Transaction.user_id == current_user.id,
            Transaction.type == TransactionType.EXPENSE,
            Transaction.date >= month_start,
            Transaction.date <= month_end
        ).scalar() or 0
        
        month_data['income'] = float(income)
        month_data['expense'] = float(expense)
        month_data['savings'] = float(income) - float(expense)
    
    return jsonify({
        'months': len(months_data),
        'data': months_data
    })

@reports_bp.route('/account-balance-history')
@login_required
def account_balance_history():
    """Account balance history report"""
    # Get date range (default last 30 days)
    days = request.args.get('days', 30, type=int)
    account_id = request.args.get('account_id')
    
    end_date = date.today()
    start_date = end_date - timedelta(days=days)
    
    # Get account
    if account_id:
        account = Account.query.filter_by(
            id=account_id,
            user_id=current_user.id
        ).first_or_404()
        accounts = [account]
    else:
        accounts = Account.query.filter_by(
            user_id=current_user.id,
            is_active=True
        ).all()
    
    # Generate daily data points
    result = []
    for i in range(days + 1):
        current_date = start_date + timedelta(days=i)
        
        day_data = {
            'date': current_date.isoformat(),
            'balances': {}
        }
        
        for account in accounts:
            # Get balance as of this date
            # This is simplified - in production, you'd track daily balances
            day_data['balances'][account.name] = float(account.current_balance)
        
        result.append(day_data)
    
    return jsonify({
        'days': days,
        'accounts': [{'id': acc.id, 'name': acc.name} for acc in accounts],
        'data': result
    })

@reports_bp.route('/budget-vs-actual')
@login_required
def budget_vs_actual():
    """Budget vs Actual spending report"""
    # Get month
    month = request.args.get('month')
    if month:
        year = int(month[:4])
        month_num = int(month[5:7])
    else:
        today = date.today()
        year = today.year
        month_num = today.month
    
    month_key = int(f"{year}{month_num:02d}")
    
    # Get budgets for this month
    budgets = Budget.query.filter_by(
        user_id=current_user.id,
        month=month_key
    ).all()
    
    # Calculate actual spending
    month_start = date(year, month_num, 1)
    if month_num == 12:
        month_end = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        month_end = date(year, month_num + 1, 1) - timedelta(days=1)
    
    report_data = []
    total_budget = 0
    total_actual = 0
    
    for budget in budgets:
        # Get actual spending for this category
        actual = db.session.query(
            func.coalesce(func.sum(Transaction.amount), 0)
        ).filter(
            Transaction.user_id == current_user.id,
            Transaction.category_id == budget.category_id,
            Transaction.type == TransactionType.EXPENSE,
            Transaction.date >= month_start,
            Transaction.date <= month_end
        ).scalar() or 0
        
        actual_amount = float(actual)
        budget_amount = float(budget.amount)
        
        report_data.append({
            'category': budget.category.name,
            'budget': budget_amount,
            'actual': actual_amount,
            'variance': budget_amount - actual_amount,
            'percentage': (actual_amount / budget_amount * 100) if budget_amount > 0 else 0
        })
        
        total_budget += budget_amount
        total_actual += actual_amount
    
    return jsonify({
        'month': f"{year}-{month_num:02d}",
        'total_budget': total_budget,
        'total_actual': total_actual,
        'total_variance': total_budget - total_actual,
        'data': report_data
    })

@reports_bp.route('/export/full-report')
@login_required
def export_full_report():
    """Export full financial report as PDF/Excel"""
    # This would generate a comprehensive report
    # For now, return JSON with summary data
    
    today = date.today()
    
    # Get data for last 12 months
    report_data = {
        'generated_at': datetime.utcnow().isoformat(),
        'user': current_user.name,
        'period': 'Last 12 Months',
        'summary': {}
    }
    
    return jsonify(report_data)