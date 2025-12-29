from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from datetime import datetime, date
from extensions import db
from models import Transfer, Account, Transaction, TransactionType
from forms.main import TransferForm

transfers_bp = Blueprint('transfers', __name__)

@transfers_bp.route('/')
@login_required
def index():
    """List all transfers"""
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    transfers = Transfer.query.filter_by(
        user_id=current_user.id
    ).order_by(Transfer.date.desc(), Transfer.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return render_template('transfers/index.html', transfers=transfers)

@transfers_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    """Create new transfer"""
    form = TransferForm()
    
    # Populate account choices
    accounts = Account.query.filter_by(
        user_id=current_user.id,
        is_active=True
    ).all()
    
    form.from_account_id.choices = [(acc.id, f"{acc.name} ({acc.currency} {acc.current_balance:,.2f})") 
                                   for acc in accounts]
    form.to_account_id.choices = [(acc.id, f"{acc.name} ({acc.currency} {acc.current_balance:,.2f})") 
                                 for acc in accounts]
    
    if form.validate_on_submit():
        from_account = Account.query.get(form.from_account_id.data)
        to_account = Account.query.get(form.to_account_id.data)
        
        if not from_account or not to_account:
            flash('Invalid account selected.', 'danger')
            return render_template('transfers/create.html', form=form)
        
        # Check if from account has sufficient balance
        if float(from_account.current_balance) < float(form.amount.data):
            flash('Insufficient balance in source account.', 'danger')
            return render_template('transfers/create.html', form=form)
        
        # Create transfer
        transfer = Transfer(
            amount=form.amount.data,
            date=form.date.data,
            description=form.description.data,
            user_id=current_user.id,
            from_account_id=form.from_account_id.data,
            to_account_id=form.to_account_id.data,
            created_at=datetime.utcnow()
        )
        
        # Update account balances
        from_account.current_balance -= form.amount.data
        to_account.current_balance += form.amount.data
        
        db.session.add(transfer)
        db.session.commit()
        
        flash('Transfer completed successfully!', 'success')
        return redirect(url_for('transfers.index'))
    
    return render_template('transfers/create.html', form=form)

@transfers_bp.route('/<int:transfer_id>/delete', methods=['POST'])
@login_required
def delete(transfer_id):
    """Delete transfer (reverse the transaction)"""
    transfer = Transfer.query.filter_by(
        id=transfer_id,
        user_id=current_user.id
    ).first_or_404()
    
    # Reverse account balances
    from_account = Account.query.get(transfer.from_account_id)
    to_account = Account.query.get(transfer.to_account_id)
    
    if from_account:
        from_account.current_balance += transfer.amount
    if to_account:
        to_account.current_balance -= transfer.amount
    
    db.session.delete(transfer)
    db.session.commit()
    
    flash('Transfer deleted successfully!', 'success')
    return redirect(url_for('transfers.index'))