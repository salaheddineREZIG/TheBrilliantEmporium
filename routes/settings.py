from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user, logout_user
from datetime import datetime
from extensions import db
from models import User, Account, Category, Transaction, Budget
from forms.main import SettingsForm, ImportForm
import json
import csv
from io import StringIO

settings_bp = Blueprint('settings', __name__)

@settings_bp.route('/')
@login_required
def index():
    """Settings dashboard"""
    form = SettingsForm()
    
    # TODO: Load user settings from database
    
    return render_template('settings/index.html', form=form)

@settings_bp.route('/update', methods=['POST'])
@login_required
def update():
    """Update settings"""
    form = SettingsForm()
    
    if form.validate_on_submit():
        # TODO: Save settings to database
        
        flash('Settings updated successfully!', 'success')
        return redirect(url_for('settings.index'))
    
    return render_template('settings/index.html', form=form)

@settings_bp.route('/export-data')
@login_required
def export_data():
    """Export all user data as JSON"""
    # Get all user data
    user_data = current_user.to_dict(include_relationships=True)
    
    # Get accounts
    accounts = Account.query.filter_by(user_id=current_user.id).all()
    user_data['accounts_detailed'] = [acc.to_dict(include_relationships=True) for acc in accounts]
    
    # Get categories
    categories = Category.query.filter_by(user_id=current_user.id).all()
    user_data['categories_detailed'] = [cat.to_dict(include_relationships=True) for cat in categories]
    
    # Get transactions
    transactions = Transaction.query.filter_by(user_id=current_user.id).all()
    user_data['transactions_detailed'] = [t.to_dict(include_relationships=True) for t in transactions]
    
    # Get budgets
    budgets = Budget.query.filter_by(user_id=current_user.id).all()
    user_data['budgets_detailed'] = [b.to_dict(include_relationships=True) for b in budgets]
    
    # Convert to JSON
    json_data = json.dumps(user_data, indent=2, default=str)
    
    return json_data, 200, {
        'Content-Type': 'application/json',
        'Content-Disposition': 'attachment; filename=brilliant-emporium-export.json'
    }

@settings_bp.route('/import-data', methods=['GET', 'POST'])
@login_required
def import_data():
    """Import data from file"""
    form = ImportForm()
    
    if form.validate_on_submit():
        file = form.file.data
        import_type = form.import_type.data
        
        try:
            if import_type == 'json':
                data = json.load(file)
                # TODO: Process JSON import
                flash('JSON import feature coming soon!', 'info')
                
            elif import_type == 'csv':
                # Read CSV
                stream = StringIO(file.stream.read().decode("UTF8"), newline=None)
                csv_reader = csv.DictReader(stream)
                
                # TODO: Process CSV import
                flash('CSV import feature coming soon!', 'info')
            
            return redirect(url_for('settings.index'))
            
        except Exception as e:
            flash(f'Error importing data: {str(e)}', 'danger')
    
    return render_template('settings/import.html', form=form)

@settings_bp.route('/delete-account', methods=['POST'])
@login_required
def delete_account():
    """Delete user account and all data"""
    confirm = request.form.get('confirm')
    
    if confirm != current_user.email:
        flash('Please enter your email correctly to confirm account deletion.', 'danger')
        return redirect(url_for('settings.index'))
    
    # Get user data for backup (optional)
    user_data = current_user.to_dict(include_relationships=True)
    
    # Delete all user data
    Transaction.query.filter_by(user_id=current_user.id).delete()
    Budget.query.filter_by(user_id=current_user.id).delete()
    Category.query.filter_by(user_id=current_user.id).delete()
    Account.query.filter_by(user_id=current_user.id).delete()
    
    # Delete user
    db.session.delete(current_user)
    db.session.commit()
    
    logout_user()
    flash('Your account and all data have been deleted successfully.', 'info')
    return redirect(url_for('auth.login'))

@settings_bp.route('/api/backup')
@login_required
def api_backup():
    """API endpoint for data backup"""
    # Get counts
    accounts_count = Account.query.filter_by(user_id=current_user.id).count()
    transactions_count = Transaction.query.filter_by(user_id=current_user.id).count()
    categories_count = Category.query.filter_by(user_id=current_user.id).count()
    budgets_count = Budget.query.filter_by(user_id=current_user.id).count()
    
    # Get latest transaction date
    latest_transaction = Transaction.query.filter_by(
        user_id=current_user.id
    ).order_by(Transaction.date.desc()).first()
    
    return jsonify({
        'backup_date': datetime.utcnow().isoformat(),
        'user': current_user.name,
        'email': current_user.email,
        'stats': {
            'accounts': accounts_count,
            'transactions': transactions_count,
            'categories': categories_count,
            'budgets': budgets_count
        },
        'latest_data': {
            'transaction_date': latest_transaction.date.isoformat() if latest_transaction else None,
            'total_balance': sum(float(acc.current_balance) 
                               for acc in Account.query.filter_by(user_id=current_user.id).all())
        }
    })