from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from datetime import datetime, date, timedelta
from sqlalchemy import or_
from extensions import db
from models import Transaction, Account, Category, TransactionType, SyncStatus
from forms.main import TransactionForm, TransactionFilterForm
import json

transactions_bp = Blueprint('transactions', __name__)

@transactions_bp.route('/')
@login_required
def index():
    """List all transactions with filtering"""
    form = TransactionFilterForm()
    
    # Base query
    query = Transaction.query.filter_by(user_id=current_user.id)
    
    # Apply filters
    if request.args.get('date_from'):
        date_from = datetime.strptime(request.args['date_from'], '%Y-%m-%d').date()
        query = query.filter(Transaction.date >= date_from)
    
    if request.args.get('date_to'):
        date_to = datetime.strptime(request.args['date_to'], '%Y-%m-%d').date()
        query = query.filter(Transaction.date <= date_to)
    
    if request.args.get('account_id') and request.args['account_id'] != 'all':
        query = query.filter(Transaction.account_id == request.args['account_id'])
    
    if request.args.get('category_id') and request.args['category_id'] != 'all':
        query = query.filter(Transaction.category_id == request.args['category_id'])
    
    if request.args.get('type') and request.args['type'] != 'all':
        query = query.filter(Transaction.type == TransactionType(request.args['type']))
    
    if request.args.get('search'):
        search_term = f"%{request.args['search']}%"
        query = query.filter(or_(
            Transaction.description.ilike(search_term),
            Transaction.amount.ilike(search_term)
        ))
    
    # Calculate statistics for all filtered transactions
    all_filtered_transactions = query.all()
    total_income = sum(float(t.amount) for t in all_filtered_transactions if t.type == TransactionType.INCOME)
    total_expense = sum(float(t.amount) for t in all_filtered_transactions if t.type == TransactionType.EXPENSE)
    
    # Order and paginate
    page = request.args.get('page', 1, type=int)
    per_page = 25
    
    transactions = query.order_by(
        Transaction.date.desc(),
        Transaction.created_at.desc()
    ).paginate(page=page, per_page=per_page, error_out=False)
    
    # Get accounts and categories for filter dropdowns
    accounts = Account.query.filter_by(
        user_id=current_user.id,
        is_active=True
    ).order_by(Account.name).all()
    
    categories = Category.query.filter_by(
        user_id=current_user.id,
        is_active=True
    ).order_by(Category.name).all()
    
    return render_template('transactions/index.html',
                         transactions=transactions,
                         form=form,
                         accounts=accounts,
                         categories=categories,
                         total_income=total_income,
                         total_expense=total_expense,
                         filter_params=request.args,
                         date=date)

@transactions_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    """Create new transaction"""
    form = TransactionForm()
    
    # Populate account and category choices
    form.account_id.choices = [(acc.id, f"{acc.name} ({acc.currency} {acc.current_balance:,.2f})") 
                              for acc in Account.query.filter_by(
                                  user_id=current_user.id,
                                  is_active=True
                              ).all()]
    
    # Determine the transaction type to use for category choices.
    # If this is a POST, prefer the submitted value so choices match validation.
    selected_type = request.form.get('type') if request.method == 'POST' else (form.type.data or 'expense')
    form.type.data = selected_type
    form.set_category_choices(selected_type)
    
    if form.validate_on_submit():
        transaction = Transaction(
            amount=form.amount.data,
            type=TransactionType(form.type.data),
            date=form.date.data,
            description=form.description.data,
            user_id=current_user.id,
            account_id=form.account_id.data,
            category_id=form.category_id.data,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            sync_status=SyncStatus.LOCAL
        )
        
        # Update account balance
        account = Account.query.get(form.account_id.data)
        if account:
            account.update_balance(TransactionType(form.type.data), form.amount.data)
        
        db.session.add(transaction)
        db.session.commit()
        
        flash('Transaction added successfully!', 'success')
        return redirect(url_for('transactions.index'))
    
    return render_template('transactions/create.html', form=form)

@transactions_bp.route('/<int:transaction_id>')
@login_required
def view(transaction_id):
    """View transaction details"""
    transaction = Transaction.query.filter_by(
        id=transaction_id,
        user_id=current_user.id
    ).first_or_404()
    
    return render_template('transactions/view.html', transaction=transaction)

@transactions_bp.route('/<int:transaction_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(transaction_id):
    """Edit transaction"""
    transaction = Transaction.query.filter_by(
        id=transaction_id,
        user_id=current_user.id
    ).first_or_404()
    
    form = TransactionForm(obj=transaction)
    
    # Populate account and category choices
    form.account_id.choices = [(acc.id, f"{acc.name} ({acc.currency} {acc.current_balance:,.2f})") 
                              for acc in Account.query.filter_by(
                                  user_id=current_user.id,
                                  is_active=True
                              ).all()]
    
    form.category_id.choices = [(cat.id, f"{cat.icon} {cat.name}") 
                               for cat in Category.query.filter_by(
                                   user_id=current_user.id,
                                   is_active=True
                               ).all()]
    
    if form.validate_on_submit():
        # Store old values for account balance adjustment
        old_account_id = transaction.account_id
        old_amount = transaction.amount
        old_type = transaction.type
        
        # Update transaction
        transaction.amount = form.amount.data
        transaction.type = TransactionType(form.type.data)
        transaction.date = form.date.data
        transaction.description = form.description.data
        transaction.account_id = form.account_id.data
        transaction.category_id = form.category_id.data
        transaction.updated_at = datetime.utcnow()
        
        # Adjust account balances
        if old_account_id != form.account_id.data:
            # Reverse old account balance
            old_account = Account.query.get(old_account_id)
            if old_account:
                if old_type == TransactionType.INCOME:
                    old_account.current_balance -= old_amount
                else:
                    old_account.current_balance += old_amount
            
            # Apply to new account
            new_account = Account.query.get(form.account_id.data)
            if new_account:
                new_account.update_balance(TransactionType(form.type.data), form.amount.data)
        else:
            # Same account, adjust balance difference
            account = Account.query.get(form.account_id.data)
            if account:
                # Reverse old transaction
                if old_type == TransactionType.INCOME:
                    account.current_balance -= old_amount
                else:
                    account.current_balance += old_amount
                
                # Apply new transaction
                account.update_balance(TransactionType(form.type.data), form.amount.data)
        
        db.session.commit()
        
        flash('Transaction updated successfully!', 'success')
        return redirect(url_for('transactions.view', transaction_id=transaction_id))
    
    # Get similar transactions (same category or same amount range)
    similar_transactions = Transaction.query.filter(
        Transaction.user_id == current_user.id,
        Transaction.id != transaction_id,
        or_(
            Transaction.category_id == transaction.category_id,
            Transaction.amount.between(float(transaction.amount) * 0.9, float(transaction.amount) * 1.1)
        )
    ).order_by(Transaction.date.desc()).limit(5).all()
    
    # Calculate net change for template
    def calculate_net_change():
        # This will be called in template context
        return 0.00  # Placeholder - actual calculation in JavaScript
    
    return render_template('transactions/edit.html', 
                         form=form, 
                         transaction=transaction,
                         similar_transactions=similar_transactions,
                         calculate_net_change=calculate_net_change)

@transactions_bp.route('/<int:transaction_id>/delete', methods=['POST'])
@login_required
def delete(transaction_id):
    """Delete transaction"""
    transaction = Transaction.query.filter_by(
        id=transaction_id,
        user_id=current_user.id
    ).first_or_404()
    
    # Reverse account balance
    account = Account.query.get(transaction.account_id)
    if account:
        if transaction.type == TransactionType.INCOME:
            account.current_balance -= transaction.amount
        else:
            account.current_balance += transaction.amount
    
    db.session.delete(transaction)
    db.session.commit()
    
    # If this was an AJAX/JSON request (fetch), return JSON for the client to handle
    if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.headers.get('Accept', '').lower().startswith('application/json'):
        return jsonify({'success': True, 'message': 'Transaction deleted'})

    flash('Transaction deleted successfully!', 'success')
    return redirect(url_for('transactions.index'))

@transactions_bp.route('/bulk-delete', methods=['POST'])
@login_required
def bulk_delete():
    """Delete multiple transactions"""
    data = request.get_json()
    transaction_ids = data.get('transaction_ids', [])
    
    if not transaction_ids:
        return jsonify({'error': 'No transactions selected'}), 400
    
    # Get transactions and reverse account balances
    transactions = Transaction.query.filter(
        Transaction.id.in_(transaction_ids),
        Transaction.user_id == current_user.id
    ).all()
    
    for transaction in transactions:
        account = Account.query.get(transaction.account_id)
        if account:
            if transaction.type == TransactionType.INCOME:
                account.current_balance -= transaction.amount
            else:
                account.current_balance += transaction.amount
        
        db.session.delete(transaction)
    
    db.session.commit()
    
    return jsonify({'success': True, 'message': f'{len(transactions)} transactions deleted'})

@transactions_bp.route('/api/quick-add', methods=['POST'])
@login_required
def quick_add():
    """Quick add transaction API (for mobile/quick entry)"""
    data = request.get_json()
    
    try:
        transaction = Transaction(
            amount=data['amount'],
            type=TransactionType(data['type']),
            date=datetime.strptime(data['date'], '%Y-%m-%d').date(),
            description=data.get('description', ''),
            user_id=current_user.id,
            account_id=data['account_id'],
            category_id=data['category_id'],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            sync_status=SyncStatus.LOCAL
        )
        
        # Update account balance
        account = Account.query.get(data['account_id'])
        if account:
            account.update_balance(TransactionType(data['type']), data['amount'])
        
        db.session.add(transaction)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Transaction added',
            'transaction_id': transaction.id
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@transactions_bp.route('/export/csv')
@login_required
def export_csv():
    """Export transactions as CSV"""
    import csv
    from io import StringIO
    
    # Get filtered transactions
    query = Transaction.query.filter_by(user_id=current_user.id)
    
    # Apply filters from request
    if request.args.get('date_from'):
        date_from = datetime.strptime(request.args['date_from'], '%Y-%m-%d').date()
        query = query.filter(Transaction.date >= date_from)
    
    if request.args.get('date_to'):
        date_to = datetime.strptime(request.args['date_to'], '%Y-%m-%d').date()
        query = query.filter(Transaction.date <= date_to)
    
    transactions = query.order_by(Transaction.date).all()
    
    # Create CSV
    output = StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow(['Date', 'Type', 'Amount', 'Category', 'Account', 'Description'])
    
    # Write data
    for t in transactions:
        writer.writerow([
            t.date.isoformat(),
            t.type.value,
            float(t.amount),
            t.category.name if t.category else '',
            t.account.name if t.account else '',
            t.description or ''
        ])
    
    output.seek(0)
    
    return output.getvalue(), 200, {
        'Content-Type': 'text/csv',
        'Content-Disposition': 'attachment; filename=transactions.csv'
    }