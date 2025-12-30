from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required, current_user
from datetime import date, timedelta, datetime
from sqlalchemy import func, extract, and_, or_
from extensions import db
from models import Account, Transaction, Category, Budget, Transfer, TransactionType, AccountType, UserSettings
import calendar
from collections import defaultdict

dashboard_bp = Blueprint('dashboard', __name__)

def get_user_settings():
    """Get or create user settings"""
    settings = UserSettings.query.filter_by(user_id=current_user.id).first()
    if not settings:
        settings = UserSettings(user_id=current_user.id)
        db.session.add(settings)
        db.session.commit()
    return settings

@dashboard_bp.route('/dashboard')
@login_required
def index():
    """Main dashboard view"""
    settings = get_user_settings()
    today = date.today()
    
    # Get current month/year
    current_month = today.month
    current_year = today.year
    month_key = int(f"{current_year}{current_month:02d}")
    
    # Calculate date ranges
    month_start = date(current_year, current_month, 1)
    if current_month == 12:
        month_end = date(current_year + 1, 1, 1) - timedelta(days=1)
    else:
        month_end = date(current_year, current_month + 1, 1) - timedelta(days=1)
    
    # Last 30 days
    thirty_days_ago = today - timedelta(days=30)
    
    # Get accounts
    accounts = Account.query.filter_by(
        user_id=current_user.id, 
        is_active=True
    ).order_by(Account.current_balance.desc()).all()
    
    # Calculate total balance
    total_balance = sum(float(acc.current_balance) for acc in accounts)
    
    # Get monthly income/expense
    monthly_income = db.session.query(
        func.coalesce(func.sum(Transaction.amount), 0)
    ).filter(
        Transaction.user_id == current_user.id,
        Transaction.type == TransactionType.INCOME,
        Transaction.date >= month_start,
        Transaction.date <= month_end
    ).scalar() or 0
    
    monthly_expense = db.session.query(
        func.coalesce(func.sum(Transaction.amount), 0)
    ).filter(
        Transaction.user_id == current_user.id,
        Transaction.type == TransactionType.EXPENSE,
        Transaction.date >= month_start,
        Transaction.date <= month_end
    ).scalar() or 0
    
    monthly_savings = float(monthly_income) - float(monthly_expense)
    
    # Get recent transactions (last 10)
    recent_transactions = Transaction.query.filter_by(
        user_id=current_user.id
    ).order_by(Transaction.date.desc(), Transaction.created_at.desc()).limit(10).all()
    
    # Get budget summary
    budgets = Budget.query.filter_by(
        user_id=current_user.id,
        month=month_key
    ).all()
    
    # Calculate budget progress
    budget_data = []
    total_budget = 0
    total_spent = 0
    
    for budget in budgets:
        # Calculate spent amount for this budget category in the month
        spent = db.session.query(
            func.coalesce(func.sum(Transaction.amount), 0)
        ).filter(
            Transaction.user_id == current_user.id,
            Transaction.category_id == budget.category_id,
            Transaction.type == TransactionType.EXPENSE,
            extract('year', Transaction.date) == current_year,
            extract('month', Transaction.date) == current_month
        ).scalar() or 0
        
        budget.spent_amount = float(spent)
        progress = (float(spent) / float(budget.amount)) * 100 if float(budget.amount) > 0 else 0
        
        budget_data.append({
            'id': budget.id,
            'name': budget.category.name,
            'amount': float(budget.amount),
            'spent': float(spent),
            'remaining': float(budget.amount) - float(spent),
            'progress': min(progress, 100),
            'is_over': progress > 100,
            'icon': budget.category.icon,
            'color': budget.category.color
        })
        
        total_budget += float(budget.amount)
        total_spent += float(spent)
    
    # Get expense by category for charts
    expense_by_category = db.session.query(
        Category.name,
        Category.icon,
        Category.color,
        func.sum(Transaction.amount).label('total')
    ).join(
        Transaction, Transaction.category_id == Category.id
    ).filter(
        Transaction.user_id == current_user.id,
        Transaction.type == TransactionType.EXPENSE,
        Transaction.date >= month_start,
        Transaction.date <= month_end
    ).group_by(Category.id).order_by(func.sum(Transaction.amount).desc()).limit(8).all()
    
    # Get income vs expense trend for last 6 months
    six_months_ago = today - timedelta(days=180)
    trend_data = []
    
    for i in range(6):
        month = today.month - i
        year = today.year
        if month <= 0:
            month += 12
            year -= 1
        
        month_start_i = date(year, month, 1)
        if month == 12:
            month_end_i = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            month_end_i = date(year, month + 1, 1) - timedelta(days=1)
        
        income = db.session.query(
            func.coalesce(func.sum(Transaction.amount), 0)
        ).filter(
            Transaction.user_id == current_user.id,
            Transaction.type == TransactionType.INCOME,
            Transaction.date >= month_start_i,
            Transaction.date <= month_end_i
        ).scalar() or 0
        
        expense = db.session.query(
            func.coalesce(func.sum(Transaction.amount), 0)
        ).filter(
            Transaction.user_id == current_user.id,
            Transaction.type == TransactionType.EXPENSE,
            Transaction.date >= month_start_i,
            Transaction.date <= month_end_i
        ).scalar() or 0
        
        trend_data.insert(0, {
            'month': f"{month:02d}/{year}",
            'income': float(income),
            'expense': float(expense),
            'savings': float(income) - float(expense)
        })
    
    # Get upcoming bills (expenses in next 7 days)
    next_week = today + timedelta(days=7)
    upcoming_bills = Transaction.query.filter(
        Transaction.user_id == current_user.id,
        Transaction.type == TransactionType.EXPENSE,
        Transaction.date >= today,
        Transaction.date <= next_week
    ).order_by(Transaction.date).limit(5).all()
    
    # Get account type distribution
    account_types = {}
    for account in accounts:
        acc_type = account.type.value
        account_types[acc_type] = account_types.get(acc_type, 0) + float(account.current_balance)
    
    # Get quick stats
    stats = {
        'total_accounts': len(accounts),
        'total_transactions': Transaction.query.filter_by(user_id=current_user.id).count(),
        'total_categories': Category.query.filter_by(user_id=current_user.id, is_active=True).count(),
        'total_budgets': Budget.query.filter_by(user_id=current_user.id).count(),
        'average_expense': float(monthly_expense) / 30 if monthly_expense else 0,
        'largest_income': db.session.query(
            func.max(Transaction.amount)
        ).filter(
            Transaction.user_id == current_user.id,
            Transaction.type == TransactionType.INCOME,
            Transaction.date >= month_start
        ).scalar() or 0,
        'largest_expense': db.session.query(
            func.max(Transaction.amount)
        ).filter(
            Transaction.user_id == current_user.id,
            Transaction.type == TransactionType.EXPENSE,
            Transaction.date >= month_start
        ).scalar() or 0
    }
    
    return render_template('dashboard/index.html',
                         accounts=accounts,
                         total_balance=float(total_balance),
                         recent_transactions=recent_transactions,
                         monthly_income=float(monthly_income),
                         monthly_expense=float(monthly_expense),
                         monthly_savings=monthly_savings,
                         budgets=budget_data,
                         total_budget=total_budget,
                         total_spent=total_spent,
                         expense_by_category=expense_by_category,
                         trend_data=trend_data,
                         upcoming_bills=upcoming_bills,
                         account_types=account_types,
                         stats=stats,
                         current_month=f"{calendar.month_name[current_month]} {current_year}",
                         today=today,
                         settings=settings)

@dashboard_bp.route('/api/dashboard-data')
@login_required
def dashboard_data():
    """API endpoint for dashboard data updates"""
    period = request.args.get('period', 'month')  # month, quarter, year
    
    today = date.today()
    if period == 'month':
        days = 30
    elif period == 'quarter':
        days = 90
    else:  # year
        days = 365
    
    start_date = today - timedelta(days=days)
    
    # Daily transaction data for charts
    daily_data = db.session.query(
        Transaction.date,
        Transaction.type,
        func.sum(Transaction.amount).label('amount')
    ).filter(
        Transaction.user_id == current_user.id,
        Transaction.date >= start_date
    ).group_by(Transaction.date, Transaction.type).order_by(Transaction.date).all()
    
    # Process for chart.js
    dates = []
    income_by_date = {}
    expense_by_date = {}
    
    current_date = start_date
    while current_date <= today:
        date_str = current_date.strftime('%Y-%m-%d')
        dates.append(date_str)
        income_by_date[date_str] = 0
        expense_by_date[date_str] = 0
        current_date += timedelta(days=1)
    
    for entry in daily_data:
        date_str = entry.date.strftime('%Y-%m-%d')
        if entry.type == TransactionType.INCOME:
            income_by_date[date_str] = float(entry.amount)
        else:
            expense_by_date[date_str] = float(entry.amount)
    
    return jsonify({
        'success': True,
        'dates': dates,
        'income': [income_by_date[d] for d in dates],
        'expense': [expense_by_date[d] for d in dates],
        'period': period
    })

@dashboard_bp.route('/api/quick-stats')
@login_required
def quick_stats():
    """API for quick dashboard stats"""
    today = date.today()
    month_start = date(today.year, today.month, 1)
    
    # Today's transactions
    todays_income = db.session.query(
        func.coalesce(func.sum(Transaction.amount), 0)
    ).filter(
        Transaction.user_id == current_user.id,
        Transaction.type == TransactionType.INCOME,
        Transaction.date == today
    ).scalar() or 0
    
    todays_expense = db.session.query(
        func.coalesce(func.sum(Transaction.amount), 0)
    ).filter(
        Transaction.user_id == current_user.id,
        Transaction.type == TransactionType.EXPENSE,
        Transaction.date == today
    ).scalar() or 0
    
    # Weekly summary
    week_start = today - timedelta(days=today.weekday())
    weekly_income = db.session.query(
        func.coalesce(func.sum(Transaction.amount), 0)
    ).filter(
        Transaction.user_id == current_user.id,
        Transaction.type == TransactionType.INCOME,
        Transaction.date >= week_start
    ).scalar() or 0
    
    weekly_expense = db.session.query(
        func.coalesce(func.sum(Transaction.amount), 0)
    ).filter(
        Transaction.user_id == current_user.id,
        Transaction.type == TransactionType.EXPENSE,
        Transaction.date >= week_start
    ).scalar() or 0
    
    # Account balances
    accounts = Account.query.filter_by(user_id=current_user.id, is_active=True).all()
    account_balances = {acc.name: float(acc.current_balance) for acc in accounts}
    
    return jsonify({
        'success': True,
        'today': {
            'income': float(todays_income),
            'expense': float(todays_expense),
            'net': float(todays_income - todays_expense)
        },
        'week': {
            'income': float(weekly_income),
            'expense': float(weekly_expense),
            'net': float(weekly_income - weekly_expense)
        },
        'accounts': account_balances,
        'last_updated': datetime.utcnow().isoformat()
    })