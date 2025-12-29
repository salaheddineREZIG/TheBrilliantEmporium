from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from datetime import datetime
from extensions import db
from models import Account, Transaction, AccountType, TransactionType
from forms.main import AccountForm
from datetime import date, timedelta
from sqlalchemy import func

accounts_bp = Blueprint('accounts', __name__)

@accounts_bp.route('/')
@login_required
def index():
    """List all accounts"""
    accounts = Account.query.filter_by(
        user_id=current_user.id
    ).order_by(Account.created_at.desc()).all()
    
    # Calculate total balance
    total_balance = sum(float(acc.current_balance) for acc in accounts)
    
    return render_template('accounts/index.html',
                         accounts=accounts,
                         total_balance=total_balance)

@accounts_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    """Create new account"""
    form = AccountForm()
    
    if form.validate_on_submit():
        account = Account(
            name=form.name.data,
            type=AccountType(form.type.data),
            initial_balance=form.initial_balance.data,
            current_balance=form.initial_balance.data,
            currency=form.currency.data,
            user_id=current_user.id,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        db.session.add(account)
        db.session.commit()
        
        flash('Account created successfully!', 'success')
        return redirect(url_for('accounts.index'))
    
    return render_template('accounts/create.html', form=form)

@accounts_bp.route('/<int:account_id>')
@login_required
def view(account_id):
    """View account details and transactions"""
    account = Account.query.filter_by(
        id=account_id,
        user_id=current_user.id
    ).first_or_404()
    
    # Get transactions for this account
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    transactions = Transaction.query.filter_by(
        account_id=account_id,
        user_id=current_user.id
    ).order_by(Transaction.date.desc(), Transaction.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    # Get monthly summary
    current_month = datetime.now().month
    current_year = datetime.now().year
    month_start = date(current_year, current_month, 1)
    
    if current_month == 12:
        month_end = date(current_year + 1, 1, 1) - timedelta(days=1)
    else:
        month_end = date(current_year, current_month + 1, 1) - timedelta(days=1)
    
    monthly_summary = db.session.query(
        Transaction.type,
        func.sum(Transaction.amount).label('total')
    ).filter(
        Transaction.account_id == account_id,
        Transaction.user_id == current_user.id,
        Transaction.date >= month_start,
        Transaction.date <= month_end
    ).group_by(Transaction.type).all()
    
    monthly_income = 0
    monthly_expense = 0
    for summary in monthly_summary:
        if summary.type == TransactionType.INCOME:
            monthly_income = float(summary.total) if summary.total else 0
        else:
            monthly_expense = float(summary.total) if summary.total else 0
    
    return render_template('accounts/view.html',
                         account=account,
                         transactions=transactions,
                         monthly_income=monthly_income,
                         monthly_expense=monthly_expense)

@accounts_bp.route('/<int:account_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(account_id):
    """Edit account"""
    account = Account.query.filter_by(
        id=account_id,
        user_id=current_user.id
    ).first_or_404()
    
    form = AccountForm(obj=account)
    
    if form.validate_on_submit():
        # Store old balance for adjustment
        old_balance = account.current_balance
        
        account.name = form.name.data
        account.type = AccountType(form.type.data)
        
        # Adjust current balance if initial balance changed
        if form.initial_balance.data != float(account.initial_balance):
            balance_diff = form.initial_balance.data - float(account.initial_balance)
            account.current_balance = float(account.current_balance) + balance_diff
            account.initial_balance = form.initial_balance.data
        
        account.currency = form.currency.data
        account.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        flash('Account updated successfully!', 'success')
        return redirect(url_for('accounts.view', account_id=account_id))
    
    return render_template('accounts/edit.html', form=form, account=account)

@accounts_bp.route('/<int:account_id>/delete', methods=['POST'])
@login_required
def delete(account_id):
    """Delete account (soft delete)"""
    account = Account.query.filter_by(
        id=account_id,
        user_id=current_user.id
    ).first_or_404()
    
    # Check if account has transactions
    transaction_count = Transaction.query.filter_by(
        account_id=account_id,
        user_id=current_user.id
    ).count()
    
    if transaction_count > 0:
        flash('Cannot delete account with transactions. Archive it instead.', 'danger')
        return redirect(url_for('accounts.view', account_id=account_id))
    
    # Soft delete (archive)
    account.is_active = False
    account.updated_at = datetime.utcnow()
    
    db.session.commit()
    
    flash('Account archived successfully!', 'success')
    return redirect(url_for('accounts.index'))

@accounts_bp.route('/<int:account_id>/restore', methods=['POST'])
@login_required
def restore(account_id):
    """Restore archived account"""
    account = Account.query.filter_by(
        id=account_id,
        user_id=current_user.id
    ).first_or_404()
    
    account.is_active = True
    account.updated_at = datetime.utcnow()
    
    db.session.commit()
    
    flash('Account restored successfully!', 'success')
    return redirect(url_for('accounts.view', account_id=account_id))

@accounts_bp.route('/api/account-types')
@login_required
def get_account_types():
    """Get account types for API"""
    account_types = [
        {'value': atype.value, 'label': atype.value.replace('_', ' ').title()}
        for atype in AccountType
    ]
    return jsonify(account_types)

@accounts_bp.route('/api/balance/<int:account_id>')
@login_required
def get_balance(account_id):
    """Get account balance API"""
    account = Account.query.filter_by(
        id=account_id,
        user_id=current_user.id
    ).first_or_404()
    
    return jsonify({
        'balance': float(account.current_balance),
        'currency': account.currency
    })