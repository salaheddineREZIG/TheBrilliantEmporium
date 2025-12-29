from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from datetime import datetime, date, timedelta
from sqlalchemy import extract, and_
from extensions import db
from models import Budget, Category, Transaction, TransactionType
from forms.main import BudgetForm
import calendar
from sqlalchemy import func

budgets_bp = Blueprint('budgets', __name__)

@budgets_bp.route('/')
@login_required
def index():
    """List all budgets"""
    # Get selected month (default current month)
    selected_month = request.args.get('month')
    if selected_month:
        try:
            year = int(selected_month[:4])
            month = int(selected_month[5:7])
        except:
            today = date.today()
            year = today.year
            month = today.month
    else:
        today = date.today()
        year = today.year
        month = today.month
    
    month_key = int(f"{year}{month:02d}")
    
    # Get budgets for selected month
    budgets = Budget.query.filter_by(
        user_id=current_user.id,
        month=month_key
    ).all()
    
    # Calculate spent amounts
    month_start = date(year, month, 1)
    if month == 12:
        month_end = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        month_end = date(year, month + 1, 1) - timedelta(days=1)
    
    for budget in budgets:
        spent = db.session.query(
            func.coalesce(func.sum(Transaction.amount), 0)
        ).filter(
            Transaction.user_id == current_user.id,
            Transaction.category_id == budget.category_id,
            Transaction.type == TransactionType.EXPENSE,
            Transaction.date >= month_start,
            Transaction.date <= month_end
        ).scalar()
        
        budget.spent_amount = float(spent) if spent else 0
    
    # Get available categories for budgeting
    categories = Category.query.filter_by(
        user_id=current_user.id,
        type=TransactionType.EXPENSE,
        is_active=True
    ).all()
    
    # Calculate month summary
    total_budget = sum(float(b.amount) for b in budgets)
    total_spent = sum(b.spent_amount for b in budgets)
    
    # Get previous and next months for navigation
    prev_month = month - 1 if month > 1 else 12
    prev_year = year if month > 1 else year - 1
    next_month = month + 1 if month < 12 else 1
    next_year = year if month < 12 else year + 1
    
    return render_template('budgets/index.html',
                         budgets=budgets,
                         categories=categories,
                         month_key=month_key,
                         month_name=f"{calendar.month_name[month]} {year}",
                         total_budget=total_budget,
                         total_spent=total_spent,
                         prev_month=f"{prev_year}-{prev_month:02d}",
                         next_month=f"{next_year}-{next_month:02d}",
                         current_month=f"{year}-{month:02d}")

@budgets_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    """Create new budget"""
    form = BudgetForm()
    
    # Populate category choices
    form.category_id.choices = [(cat.id, f"{cat.icon} {cat.name}") 
                               for cat in Category.query.filter_by(
                                   user_id=current_user.id,
                                   type=TransactionType.EXPENSE,
                                   is_active=True
                               ).all()]
    
    if form.validate_on_submit():
        # Check if budget already exists for this category/month
        existing = Budget.query.filter_by(
            user_id=current_user.id,
            category_id=form.category_id.data,
            month=form.month.data
        ).first()
        
        if existing:
            flash('Budget already exists for this category and month.', 'danger')
            return redirect(url_for('budgets.create'))
        
        budget = Budget(
            amount=form.amount.data,
            month=form.month.data,
            user_id=current_user.id,
            category_id=form.category_id.data,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        db.session.add(budget)
        db.session.commit()
        
        flash('Budget created successfully!', 'success')
        return redirect(url_for('budgets.index'))
    
    return render_template('budgets/create.html', form=form)

@budgets_bp.route('/<int:budget_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(budget_id):
    """Edit budget"""
    budget = Budget.query.filter_by(
        id=budget_id,
        user_id=current_user.id
    ).first_or_404()
    
    form = BudgetForm(obj=budget)
    
    # Populate category choices
    form.category_id.choices = [(cat.id, f"{cat.icon} {cat.name}") 
                               for cat in Category.query.filter_by(
                                   user_id=current_user.id,
                                   type=TransactionType.EXPENSE,
                                   is_active=True
                               ).all()]
    
    if form.validate_on_submit():
        # Check if budget already exists for this category/month (different ID)
        existing = Budget.query.filter(
            Budget.user_id == current_user.id,
            Budget.category_id == form.category_id.data,
            Budget.month == form.month.data,
            Budget.id != budget_id
        ).first()
        
        if existing:
            flash('Budget already exists for this category and month.', 'danger')
            return render_template('budgets/edit.html', form=form, budget=budget)
        
        budget.amount = form.amount.data
        budget.month = form.month.data
        budget.category_id = form.category_id.data
        budget.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        flash('Budget updated successfully!', 'success')
        return redirect(url_for('budgets.index'))
    
    return render_template('budgets/edit.html', form=form, budget=budget)

@budgets_bp.route('/<int:budget_id>/delete', methods=['POST'])
@login_required
def delete(budget_id):
    """Delete budget"""
    budget = Budget.query.filter_by(
        id=budget_id,
        user_id=current_user.id
    ).first_or_404()
    
    db.session.delete(budget)
    db.session.commit()
    
    flash('Budget deleted successfully!', 'success')
    return redirect(url_for('budgets.index'))

@budgets_bp.route('/api/budget-progress')
@login_required
def budget_progress():
    """Get budget progress data for charts"""
    today = date.today()
    month_key = int(f"{today.year}{today.month:02d}")
    
    budgets = Budget.query.filter_by(
        user_id=current_user.id,
        month=month_key
    ).all()
    
    data = []
    for budget in budgets:
        # Calculate spent amount for this category this month
        month_start = date(today.year, today.month, 1)
        if today.month == 12:
            month_end = date(today.year + 1, 1, 1) - timedelta(days=1)
        else:
            month_end = date(today.year, today.month + 1, 1) - timedelta(days=1)
        
        spent = db.session.query(
            func.coalesce(func.sum(Transaction.amount), 0)
        ).filter(
            Transaction.user_id == current_user.id,
            Transaction.category_id == budget.category_id,
            Transaction.type == TransactionType.EXPENSE,
            Transaction.date >= month_start,
            Transaction.date <= month_end
        ).scalar() or 0
        
        data.append({
            'category': budget.category.name,
            'budget': float(budget.amount),
            'spent': float(spent),
            'remaining': float(budget.amount) - float(spent),
            'percentage': (float(spent) / float(budget.amount)) * 100 if float(budget.amount) > 0 else 0
        })
    
    return jsonify(data)

@budgets_bp.route('/quick-setup', methods=['POST'])
@login_required
def quick_setup():
    """Quick budget setup based on previous month spending"""
    data = request.get_json()
    month = data.get('month')
    
    if not month:
        return jsonify({'error': 'Month required'}), 400
    
    # Parse month
    year = int(month[:4])
    month_num = int(month[4:6])
    
    # Get previous month
    if month_num == 1:
        prev_month = 12
        prev_year = year - 1
    else:
        prev_month = month_num - 1
        prev_year = year
    
    prev_month_start = date(prev_year, prev_month, 1)
    if prev_month == 12:
        prev_month_end = date(prev_year + 1, 1, 1) - timedelta(days=1)
    else:
        prev_month_end = date(prev_year, prev_month + 1, 1) - timedelta(days=1)
    
    # Get spending by category from previous month
    spending = db.session.query(
        Category.id,
        Category.name,
        func.coalesce(func.sum(Transaction.amount), 0).label('spent')
    ).join(
        Transaction, Transaction.category_id == Category.id
    ).filter(
        Transaction.user_id == current_user.id,
        Transaction.type == TransactionType.EXPENSE,
        Transaction.date >= prev_month_start,
        Transaction.date <= prev_month_end,
        Category.is_active == True
    ).group_by(Category.id, Category.name).all()
    
    # Create budgets based on previous spending (with 10% reduction for savings goal)
    budgets_created = 0
    for item in spending:
        if item.spent > 0:
            budget_amount = float(item.spent) * 0.9  # 10% reduction
            
            # Check if budget already exists
            existing = Budget.query.filter_by(
                user_id=current_user.id,
                category_id=item.id,
                month=int(month)
            ).first()
            
            if not existing:
                budget = Budget(
                    amount=budget_amount,
                    month=int(month),
                    user_id=current_user.id,
                    category_id=item.id,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                db.session.add(budget)
                budgets_created += 1
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': f'{budgets_created} budgets created based on previous month spending'
    })