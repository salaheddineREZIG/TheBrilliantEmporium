from flask import Blueprint, render_template, jsonify
from flask_login import login_required, current_user
from datetime import date, timedelta
from sqlalchemy import func
from extensions import db
from models import Account, Transaction, Category, Budget,TransactionType, AccountType

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/dashboard')
@login_required
def index():
    """Main dashboard view"""
    # Get current month/year for dashboard
    today = date.today()
    current_month = today.month
    current_year = today.year
    month_key = int(f"{current_year}{current_month:02d}")
    
    # Get accounts summary
    accounts = Account.query.filter_by(
        user_id=current_user.id, 
        is_active=True
    ).all()
    
    # Calculate total balance
    total_balance = sum(float(acc.current_balance) for acc in accounts)
    
    # Get recent transactions (last 10)
    recent_transactions = Transaction.query.filter_by(
        user_id=current_user.id
    ).order_by(Transaction.date.desc(), Transaction.created_at.desc()).limit(10).all()
    
    # Get monthly income/expense
    month_start = date(current_year, current_month, 1)
    if current_month == 12:
        month_end = date(current_year + 1, 1, 1) - timedelta(days=1)
    else:
        month_end = date(current_year, current_month + 1, 1) - timedelta(days=1)
    
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
    
    # Get budget summary
    budgets = Budget.query.filter_by(
        user_id=current_user.id,
        month=month_key
    ).all()
    
    # Get expense by category for current month
    expense_by_category = db.session.query(
        Category.name,
        func.sum(Transaction.amount).label('total')
    ).join(
        Transaction, Transaction.category_id == Category.id
    ).filter(
        Transaction.user_id == current_user.id,
        Transaction.type == TransactionType.EXPENSE,
        Transaction.date >= month_start,
        Transaction.date <= month_end
    ).group_by(Category.name).all()
    
    return render_template('dashboard/index.html',
                         accounts=accounts,
                         total_balance=float(total_balance),
                         recent_transactions=recent_transactions,
                         monthly_income=float(monthly_income),
                         monthly_expense=float(monthly_expense),
                         monthly_savings=float(monthly_income - monthly_expense),
                         budgets=budgets,
                         expense_by_category=expense_by_category,
                         current_month=f"{current_year}-{current_month:02d}")

@dashboard_bp.route('/api/stats')
@login_required
def get_stats():
    """API endpoint for dashboard statistics"""
    today = date.today()
    thirty_days_ago = today - timedelta(days=30)
    
    # Income/Expense trends for last 30 days
    daily_data = db.session.query(
        Transaction.date,
        Transaction.type,
        func.sum(Transaction.amount).label('amount')
    ).filter(
        Transaction.user_id == current_user.id,
        Transaction.date >= thirty_days_ago
    ).group_by(Transaction.date, Transaction.type).order_by(Transaction.date).all()
    
    # Process daily data
    income_data = {}
    expense_data = {}
    for entry in daily_data:
        day_str = entry.date.isoformat()
        if entry.type == TransactionType.INCOME:
            income_data[day_str] = float(entry.amount)
        else:
            expense_data[day_str] = float(entry.amount)
    
    # Account balances
    accounts = Account.query.filter_by(
        user_id=current_user.id, 
        is_active=True
    ).all()
    
    account_data = [{
        'name': acc.name,
        'balance': float(acc.current_balance),
        'type': acc.type.value
    } for acc in accounts]
    
    return jsonify({
        'daily_income': income_data,
        'daily_expense': expense_data,
        'accounts': account_data,
        'total_balance': sum(float(acc.current_balance) for acc in accounts)
    })