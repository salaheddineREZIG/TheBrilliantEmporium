from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, current_app, send_file
from flask_login import login_required, current_user, logout_user
from datetime import datetime, date
from sqlalchemy import func, extract
from extensions import db
from models import User, Account, Category, Transaction, Budget, Transfer, UserSettings
from forms.main import SettingsForm, ImportForm, PreferencesForm
import json
import csv
import io
from io import StringIO
import os

settings_bp = Blueprint('settings', __name__, url_prefix='/settings')

# Helper function to get or create user settings
def get_user_settings(user_id):
    settings = UserSettings.query.filter_by(user_id=user_id).first()
    if not settings:
        settings = UserSettings(user_id=user_id)
        db.session.add(settings)
        db.session.commit()
    return settings

@settings_bp.route('/')
@login_required
def index():
    """Settings dashboard"""
    settings = get_user_settings(current_user.id)
    settings_form = SettingsForm(obj=settings)
    
    # Populate form with current settings
    settings_form.default_currency.data = settings.default_currency
    settings_form.date_format.data = settings.date_format
    settings_form.first_day_of_week.data = settings.first_day_of_week
    settings_form.theme.data = settings.theme
    settings_form.budget_alerts.data = settings.budget_alerts
    settings_form.large_transactions.data = settings.large_transactions
    settings_form.weekly_summary.data = settings.weekly_summary
    
    # Create preferences form
    preferences_form = PreferencesForm(obj=settings)
    
    # Import form
    import_form = ImportForm()
    
    # Get user stats
    accounts_count = Account.query.filter_by(user_id=current_user.id).count()
    transactions_count = Transaction.query.filter_by(user_id=current_user.id).count()
    categories_count = Category.query.filter_by(user_id=current_user.id).count()
    budgets_count = Budget.query.filter_by(user_id=current_user.id).count()
    
    return render_template('settings/index.html', 
                         settings_form=settings_form,
                         preferences_form=preferences_form,
                         import_form=import_form,
                         accounts_count=accounts_count,
                         transactions_count=transactions_count,
                         categories_count=categories_count,
                         budgets_count=budgets_count)

@settings_bp.route('/update', methods=['POST'])
@login_required
def update():
    """Update settings"""
    settings = get_user_settings(current_user.id)
    settings_form = SettingsForm()
    
    if settings_form.validate_on_submit():
        # Update settings
        settings.default_currency = settings_form.default_currency.data
        settings.date_format = settings_form.date_format.data
        settings.first_day_of_week = int(settings_form.first_day_of_week.data)
        settings.theme = settings_form.theme.data
        settings.budget_alerts = settings_form.budget_alerts.data
        settings.large_transactions = settings_form.large_transactions.data
        settings.weekly_summary = settings_form.weekly_summary.data
        
        db.session.commit()
        flash('Settings updated successfully!', 'success')
    else:
        for field, errors in settings_form.errors.items():
            for error in errors:
                flash(f'Error in {field}: {error}', 'danger')
    
    return redirect(url_for('settings.index'))

@settings_bp.route('/update-preferences', methods=['POST'])
@login_required
def update_preferences():
    """Update user preferences"""
    settings = get_user_settings(current_user.id)
    form = PreferencesForm()
    
    if form.validate_on_submit():
        settings.show_charts = form.show_charts.data
        settings.show_recent = form.show_recent.data
        settings.show_budgets = form.show_budgets.data
        settings.auto_categorize = form.auto_categorize.data
        settings.duplicate_detection = form.duplicate_detection.data
        settings.require_description = form.require_description.data
        settings.monthly_report = form.monthly_report.data
        settings.app_budget_alerts = form.app_budget_alerts.data
        settings.app_bill_reminders = form.app_bill_reminders.data
        settings.app_goals_update = form.app_goals_update.data
        
        db.session.commit()
        return jsonify({'success': True, 'message': 'Preferences updated successfully!'})
    
    return jsonify({'success': False, 'errors': form.errors})

@settings_bp.route('/export-data')
@login_required
def export_data():
    """Export all user data as JSON"""
    # Get all user data
    user_data = current_user.to_dict(include_relationships=True)
    
    # Get accounts
    accounts = Account.query.filter_by(user_id=current_user.id).all()
    user_data['accounts'] = [acc.to_dict(include_relationships=True) for acc in accounts]
    
    # Get categories
    categories = Category.query.filter_by(user_id=current_user.id).all()
    user_data['categories'] = [cat.to_dict(include_relationships=True) for cat in categories]
    
    # Get transactions
    transactions = Transaction.query.filter_by(user_id=current_user.id).all()
    user_data['transactions'] = [t.to_dict(include_relationships=True) for t in transactions]
    
    # Get budgets
    budgets = Budget.query.filter_by(user_id=current_user.id).all()
    user_data['budgets'] = [b.to_dict(include_relationships=True) for b in budgets]
    
    # Get transfers
    transfers = Transfer.query.filter_by(user_id=current_user.id).all()
    user_data['transfers'] = [t.to_dict() for t in transfers]
    
    # Get settings
    settings = get_user_settings(current_user.id)
    user_data['settings'] = settings.to_dict()
    
    # Convert to JSON
    json_data = json.dumps(user_data, indent=2, default=str)
    
    # Create response with download
    output = io.BytesIO()
    output.write(json_data.encode('utf-8'))
    output.seek(0)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"brilliant-emporium-export-{timestamp}.json"
    
    return send_file(output, 
                    mimetype='application/json',
                    as_attachment=True,
                    download_name=filename)

@settings_bp.route('/export-csv')
@login_required
def export_csv():
    """Export transactions as CSV"""
    transactions = Transaction.query.filter_by(user_id=current_user.id).all()
    
    # Create CSV content
    output = StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow(['Date', 'Type', 'Amount', 'Description', 'Account', 'Category'])
    
    # Write data
    for t in transactions:
        writer.writerow([
            t.date.isoformat(),
            t.type.value,
            float(t.amount),
            t.description or '',
            t.account.name if t.account else '',
            t.category.name if t.category else ''
        ])
    
    output.seek(0)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"transactions-export-{timestamp}.csv"
    
    return send_file(io.BytesIO(output.getvalue().encode('utf-8')),
                    mimetype='text/csv',
                    as_attachment=True,
                    download_name=filename)

@settings_bp.route('/import-data', methods=['GET', 'POST'])
@login_required
def import_data():
    """Import data from file"""
    import_form = ImportForm()
    
    if import_form.validate_on_submit():
        file = import_form.file.data
        import_type = import_form.import_type.data
        
        try:
            if import_type == 'json':
                data = json.load(file)
                success, message = import_json_data(data, current_user.id)
                if success:
                    flash(f'Successfully imported data: {message}', 'success')
                else:
                    flash(f'Import failed: {message}', 'danger')
                
            elif import_type == 'csv':
                # Read CSV
                stream = StringIO(file.stream.read().decode("UTF8"))
                csv_reader = csv.DictReader(stream)
                success, message = import_csv_data(csv_reader, current_user.id)
                if success:
                    flash(f'Successfully imported {message} transactions', 'success')
                else:
                    flash(f'Import failed: {message}', 'danger')
            
            return redirect(url_for('settings.index'))
            
        except Exception as e:
            flash(f'Error importing data: {str(e)}', 'danger')
    
    return render_template('settings/import.html', form=import_form)

def import_json_data(data, user_id):
    """Import data from JSON format"""
    try:
        # Import accounts
        accounts_map = {}
        if 'accounts' in data:
            for acc_data in data['accounts']:
                account = Account(
                    name=acc_data['name'],
                    type=acc_data['type'],
                    initial_balance=acc_data.get('initial_balance', 0),
                    current_balance=acc_data.get('current_balance', 0),
                    currency=acc_data.get('currency', 'USD'),
                    is_active=acc_data.get('is_active', True),
                    user_id=user_id
                )
                db.session.add(account)
                db.session.flush()  # Get the ID
                accounts_map[acc_data['id']] = account.id
        
        # Import categories
        categories_map = {}
        if 'categories' in data:
            for cat_data in data['categories']:
                category = Category(
                    name=cat_data['name'],
                    type=cat_data['type'],
                    icon=cat_data.get('icon', '📁'),
                    color=cat_data.get('color', '#808080'),
                    user_id=user_id,
                    parent_id=cat_data.get('parent_id'),
                    is_system=cat_data.get('is_system', False),
                    is_active=cat_data.get('is_active', True)
                )
                db.session.add(category)
                db.session.flush()
                categories_map[cat_data['id']] = category.id
        
        # Update parent IDs for categories
        if 'categories' in data:
            for cat_data in data['categories']:
                if cat_data.get('parent_id') and cat_data['id'] in categories_map:
                    category = Category.query.get(categories_map[cat_data['id']])
                    if category and cat_data['parent_id'] in categories_map:
                        category.parent_id = categories_map[cat_data['parent_id']]
        
        # Import transactions
        if 'transactions' in data:
            for txn_data in data['transactions']:
                transaction = Transaction(
                    amount=txn_data['amount'],
                    type=txn_data['type'],
                    date=datetime.strptime(txn_data['date'], '%Y-%m-%d').date() if isinstance(txn_data['date'], str) else txn_data['date'],
                    description=txn_data.get('description'),
                    user_id=user_id,
                    account_id=accounts_map.get(txn_data['account_id']),
                    category_id=categories_map.get(txn_data['category_id'])
                )
                db.session.add(transaction)
        
        db.session.commit()
        return True, f"Imported {len(data.get('accounts', []))} accounts, {len(data.get('categories', []))} categories, {len(data.get('transactions', []))} transactions"
        
    except Exception as e:
        db.session.rollback()
        return False, str(e)

def import_csv_data(csv_reader, user_id):
    """Import transactions from CSV format"""
    try:
        imported_count = 0
        for row in csv_reader:
            try:
                # Parse date
                txn_date = None
                for date_format in ['%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y']:
                    try:
                        txn_date = datetime.strptime(row['Date'], date_format).date()
                        break
                    except:
                        continue
                
                if not txn_date:
                    txn_date = date.today()
                
                # Get or create account
                account_name = row.get('Account', 'Imported Account')
                account = Account.query.filter_by(name=account_name, user_id=user_id).first()
                if not account:
                    account = Account(
                        name=account_name,
                        type='checking',
                        currency='USD',
                        user_id=user_id
                    )
                    db.session.add(account)
                
                # Get or create category
                category_name = row.get('Category', 'Uncategorized')
                category = Category.query.filter_by(name=category_name, user_id=user_id).first()
                if not category:
                    category = Category(
                        name=category_name,
                        type='expense' if float(row.get('Amount', 0)) < 0 else 'income',
                        user_id=user_id
                    )
                    db.session.add(category)
                
                # Create transaction
                amount = abs(float(row.get('Amount', 0)))
                txn_type = 'expense' if float(row.get('Amount', 0)) < 0 else 'income'
                
                transaction = Transaction(
                    amount=amount,
                    type=txn_type,
                    date=txn_date,
                    description=row.get('Description', ''),
                    user_id=user_id,
                    account_id=account.id,
                    category_id=category.id
                )
                db.session.add(transaction)
                imported_count += 1
                
            except Exception as e:
                current_app.logger.error(f"Error importing row {row}: {str(e)}")
                continue
        
        db.session.commit()
        return True, imported_count
        
    except Exception as e:
        db.session.rollback()
        return False, str(e)

@settings_bp.route('/delete-account', methods=['POST'])
@login_required
def delete_account():
    """Delete user account and all data"""
    confirm = request.form.get('confirm')
    
    if confirm != current_user.email:
        flash('Please enter your email correctly to confirm account deletion.', 'danger')
        return redirect(url_for('settings.index'))
    
    try:
        # Backup user data before deletion (optional)
        user_data = {
            'email': current_user.email,
            'name': current_user.name,
            'deleted_at': datetime.utcnow().isoformat()
        }
        
        # Delete all user data in correct order to respect foreign keys
        Transaction.query.filter_by(user_id=current_user.id).delete()
        Transfer.query.filter_by(user_id=current_user.id).delete()
        Budget.query.filter_by(user_id=current_user.id).delete()
        Category.query.filter_by(user_id=current_user.id).delete()
        Account.query.filter_by(user_id=current_user.id).delete()
        UserSettings.query.filter_by(user_id=current_user.id).delete()
        
        # Delete user
        db.session.delete(current_user)
        db.session.commit()
        
        logout_user()
        flash('Your account and all data have been deleted successfully.', 'info')
        return redirect(url_for('index'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting account: {str(e)}', 'danger')
        return redirect(url_for('settings.index'))

@settings_bp.route('/api/backup')
@login_required
def api_backup():
    """API endpoint for data backup"""
    # Get counts
    accounts_count = Account.query.filter_by(user_id=current_user.id).count()
    transactions_count = Transaction.query.filter_by(user_id=current_user.id).count()
    categories_count = Category.query.filter_by(user_id=current_user.id).count()
    budgets_count = Budget.query.filter_by(user_id=current_user.id).count()
    transfers_count = Transfer.query.filter_by(user_id=current_user.id).count()
    
    # Get latest transaction date
    latest_transaction = Transaction.query.filter_by(
        user_id=current_user.id
    ).order_by(Transaction.date.desc()).first()
    
    # Get total balance across all accounts
    total_balance = 0
    accounts = Account.query.filter_by(user_id=current_user.id).all()
    for acc in accounts:
        total_balance += float(acc.current_balance)
    
    # Get monthly stats
    current_month = datetime.now().strftime('%Y%m')
    monthly_expense = db.session.query(
        func.sum(Transaction.amount)
    ).filter(
        Transaction.user_id == current_user.id,
        Transaction.type == 'expense',
        extract('year', Transaction.date) == datetime.now().year,
        extract('month', Transaction.date) == datetime.now().month
    ).scalar() or 0
    
    monthly_income = db.session.query(
        func.sum(Transaction.amount)
    ).filter(
        Transaction.user_id == current_user.id,
        Transaction.type == 'income',
        extract('year', Transaction.date) == datetime.now().year,
        extract('month', Transaction.date) == datetime.now().month
    ).scalar() or 0
    
    return jsonify({
        'backup_date': datetime.utcnow().isoformat(),
        'user': current_user.name,
        'email': current_user.email,
        'stats': {
            'accounts': accounts_count,
            'transactions': transactions_count,
            'categories': categories_count,
            'budgets': budgets_count,
            'transfers': transfers_count
        },
        'latest_data': {
            'transaction_date': latest_transaction.date.isoformat() if latest_transaction else None,
            'total_balance': total_balance
        },
        'monthly_summary': {
            'month': current_month,
            'income': float(monthly_income),
            'expense': float(monthly_expense),
            'savings': float(monthly_income - monthly_expense)
        }
    })

@settings_bp.route('/clear-data', methods=['POST'])
@login_required
def clear_data():
    """Clear all user data but keep account"""
    confirm = request.form.get('confirm', '').strip().lower()
    
    if confirm != 'clear all data':
        flash('Please type "clear all data" to confirm.', 'danger')
        return redirect(url_for('settings.index'))
    
    try:
        # Clear all data but keep user account
        Transaction.query.filter_by(user_id=current_user.id).delete()
        Transfer.query.filter_by(user_id=current_user.id).delete()
        Budget.query.filter_by(user_id=current_user.id).delete()
        
        # Reset account balances
        Account.query.filter_by(user_id=current_user.id).update({'current_balance': 0, 'initial_balance': 0})
        
        db.session.commit()
        
        flash('All data has been cleared successfully. Your account remains active.', 'success')
        return redirect(url_for('dashboard.index'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error clearing data: {str(e)}', 'danger')
        return redirect(url_for('settings.index'))