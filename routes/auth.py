# auth.py
from flask import Blueprint, render_template, redirect, url_for, flash, request
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import db, login_manager
from models import User, Account, Category, Budget, Transaction, AccountType, TransactionType
from forms.auth import LoginForm, RegistrationForm, ForgotPasswordForm, ResetPasswordForm, ProfileForm, ChangePasswordForm
from flask_login import login_user, logout_user, login_required, current_user
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from datetime import datetime, date
import os

# Create blueprint
auth_bp = Blueprint('auth', __name__)

# Token serializer for password reset
SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
serializer = URLSafeTimedSerializer(SECRET_KEY)

# User loader for Flask-Login
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Helper Functions
def create_default_categories(user_id):
    """Create default categories for new users"""
    default_categories = [
        # Income Categories
        {'name': 'Salary', 'type': TransactionType.INCOME, 'icon': '💰', 'color': '#4CAF50'},
        {'name': 'Freelance', 'type': TransactionType.INCOME, 'icon': '💼', 'color': '#2196F3'},
        {'name': 'Investment', 'type': TransactionType.INCOME, 'icon': '📈', 'color': '#FF9800'},
        {'name': 'Gift', 'type': TransactionType.INCOME, 'icon': '🎁', 'color': '#E91E63'},
        {'name': 'Other Income', 'type': TransactionType.INCOME, 'icon': '📥', 'color': '#9C27B0'},
        
        # Expense Categories
        {'name': 'Food & Dining', 'type': TransactionType.EXPENSE, 'icon': '🍔', 'color': '#FF5722'},
        {'name': 'Transportation', 'type': TransactionType.EXPENSE, 'icon': '🚗', 'color': '#3F51B5'},
        {'name': 'Shopping', 'type': TransactionType.EXPENSE, 'icon': '🛍️', 'color': '#673AB7'},
        {'name': 'Entertainment', 'type': TransactionType.EXPENSE, 'icon': '🎬', 'color': '#00BCD4'},
        {'name': 'Bills & Utilities', 'type': TransactionType.EXPENSE, 'icon': '💡', 'color': '#009688'},
        {'name': 'Healthcare', 'type': TransactionType.EXPENSE, 'icon': '🏥', 'color': '#F44336'},
        {'name': 'Education', 'type': TransactionType.EXPENSE, 'icon': '📚', 'color': '#795548'},
        {'name': 'Travel', 'type': TransactionType.EXPENSE, 'icon': '✈️', 'color': '#FF9800'},
        {'name': 'Other Expense', 'type': TransactionType.EXPENSE, 'icon': '📤', 'color': '#607D8B'},
    ]
    
    for cat_data in default_categories:
        category = Category(
            name=cat_data['name'],
            type=cat_data['type'],
            icon=cat_data['icon'],
            color=cat_data['color'],
            user_id=user_id,
            created_at=datetime.utcnow()
        )
        db.session.add(category)
    
    db.session.commit()
    return len(default_categories)

def create_default_account(user_id):
    """Create default account for new users"""
    default_account = Account(
        name='Main Account',
        type=AccountType.CHECKING,
        initial_balance=0.00,
        current_balance=0.00,
        currency='USD',
        user_id=user_id,
        created_at=datetime.utcnow()
    )
    
    db.session.add(default_account)
    db.session.commit()
    return default_account

# Routes
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Handle user login"""
    # Redirect if already logged in
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
    
    form = LoginForm()
    
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        
        if user and check_password_hash(user.hashed_password, form.password.data):
            # Use the remember_me field if present on the form
            remember = getattr(form, 'remember_me', None)
            remember_value = remember.data if remember is not None else False
            login_user(user, remember=remember_value)
            
            # Update last login time
            user.last_login = datetime.utcnow()
            db.session.commit()
            
            flash('Login successful!', 'success')
            
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            return redirect(url_for('dashboard.index'))
        else:
            flash('Invalid email or password. Please try again.', 'danger')
    
    return render_template('auth/login.html', form=form)

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """Handle user registration"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
    
    form = RegistrationForm()
    
    if form.validate_on_submit():
        # Check if email exists
        if User.query.filter_by(email=form.email.data).first():
            flash('Email already registered. Please use a different email or login.', 'danger')
            return render_template('auth/register.html', form=form)
        
        # Create new user
        hashed_password = generate_password_hash(
            form.password.data,
            method='pbkdf2:sha256',
            salt_length=16
        )
        
        user = User(
            email=form.email.data,
            name=form.name.data,
            hashed_password=hashed_password,
            created_at=datetime.utcnow()
        )
        
        db.session.add(user)
        db.session.commit()
        
        # Create default data
        categories_count = create_default_categories(user.id)
        create_default_account(user.id)
        
        # Login user
        login_user(user)
        
        flash(f'Account created successfully! Welcome to The Brilliant Emporium.', 'success')
        flash(f'We\'ve created {categories_count} default categories and a main account for you.', 'info')
        
        return redirect(url_for('dashboard.index'))
    
    return render_template('auth/register.html', form=form)

@auth_bp.route('/logout')
@login_required
def logout():
    """Handle user logout"""
    logout_user()
    flash('You have been logged out successfully.', 'info')
    # Render the landing page directly to avoid a redirect loop that
    # sometimes sends users back to the login page.
    return render_template('landing.html', logout_message='You have been logged out successfully.')

@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """Handle password reset request"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
    
    form = ForgotPasswordForm()
    
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        
        if user:
            # Generate token
            token = serializer.dumps(user.email, salt='password-reset-salt')
            
            # Create reset URL
            reset_url = url_for('auth.reset_password', token=token, _external=True)
            
            # Flash message with clickable link (development only!)
            flash(f'Password reset link (development): {reset_url}', 'info')
            flash('In production, this would be sent via email.', 'warning')
        
        # Security: Always show the same message
        flash('If an account exists with that email, you will receive reset instructions.', 'info')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/forgot_password.html', form=form)

@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    """Handle password reset with token"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
    
    form = ResetPasswordForm()
    
    try:
        email = serializer.loads(token, salt='password-reset-salt', max_age=3600)
        user = User.query.filter_by(email=email).first()
        
        if not user:
            flash('Invalid or expired reset token.', 'danger')
            return redirect(url_for('auth.forgot_password'))
        
        if form.validate_on_submit():
            hashed_password = generate_password_hash(
                form.password.data,
                method='pbkdf2:sha256',
                salt_length=16
            )
            
            user.hashed_password = hashed_password
            db.session.commit()
            
            flash('Your password has been reset successfully! Please login.', 'success')
            return redirect(url_for('auth.login'))
        
        return render_template('auth/reset_password.html', form=form, token=token)
    
    except (SignatureExpired, BadSignature):
        flash('Invalid or expired reset token.', 'danger')
        return redirect(url_for('auth.forgot_password'))

@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """Handle user profile management"""
    profile_form = ProfileForm(obj=current_user)
    password_form = ChangePasswordForm()
    
    # Handle POST requests
    if request.method == 'POST':
        # Determine which form was submitted
        if 'update_profile' in request.form:
            # Use validate_on_submit() which also checks CSRF
            if profile_form.validate_on_submit():
                # Update name
                current_user.name = profile_form.name.data
                
                # Update email if changed and password is correct
                if profile_form.email.data != current_user.email:
                    if not profile_form.current_password.data:
                        flash('Current password is required to change email.', 'danger')
                    elif check_password_hash(current_user.hashed_password, profile_form.current_password.data):
                        # Check if email is taken by another user
                        existing_user = User.query.filter_by(email=profile_form.email.data).first()
                        if existing_user and existing_user.id != current_user.id:
                            flash('Email already in use by another account.', 'danger')
                        else:
                            current_user.email = profile_form.email.data
                            flash('Email updated successfully.', 'success')
                    else:
                        flash('Current password is incorrect.', 'danger')
                else:
                    # Email didn't change, just update name
                    flash('Profile updated successfully!', 'success')
                
                db.session.commit()
                return redirect(url_for('auth.profile'))
            else:
                # Form validation failed
                flash('Please correct the errors below.', 'danger')
        
        elif 'change_password' in request.form:
            if password_form.validate_on_submit():
                # Verify current password
                if not check_password_hash(current_user.hashed_password, password_form.current_password.data):
                    flash('Current password is incorrect.', 'danger')
                else:
                    # Update password
                    hashed_password = generate_password_hash(
                        password_form.new_password.data,
                        method='pbkdf2:sha256',
                        salt_length=16
                    )
                    
                    current_user.hashed_password = hashed_password
                    db.session.commit()
                    
                    flash('Password changed successfully!', 'success')
                    return redirect(url_for('auth.profile'))
            else:
                flash('Please correct the errors below.', 'danger')
    
    # Get user statistics for display
    accounts_count = Account.query.filter_by(user_id=current_user.id).count()
    transactions_count = Transaction.query.filter_by(user_id=current_user.id).count()
    categories_count = Category.query.filter_by(user_id=current_user.id).count()
    budgets_count = Budget.query.filter_by(user_id=current_user.id).count()
    
    # Mock recent activities (you can implement real activity tracking later)
    recent_activities = [
        {
            'icon': 'wallet2',
            'title': 'Account Created',
            'description': 'Your main account was set up',
            'time': current_user.created_at.strftime('%b %d, %Y')
        },
        {
            'icon': 'tags',
            'title': 'Categories Added',
            'description': f'{categories_count} default categories were created',
            'time': current_user.created_at.strftime('%b %d, %Y')
        },
        {
            'icon': 'box-arrow-in-right',
            'title': 'Last Login',
            'description': 'You logged into your account',
            'time': current_user.last_login.strftime('%b %d, %H:%M') if current_user.last_login else 'Never'
        }
    ]
    
    # Add more activities if they exist
    if accounts_count > 0:
        recent_activities.append({
            'icon': 'wallet2',
            'title': 'Accounts Active',
            'description': f'You have {accounts_count} active account(s)',
            'time': 'Today'
        })
    
    if transactions_count > 0:
        recent_activities.append({
            'icon': 'arrow-left-right',
            'title': 'Transactions Recorded',
            'description': f'You have {transactions_count} transaction(s)',
            'time': 'Today'
        })
    
    return render_template('auth/profile.html', 
                         profile_form=profile_form, 
                         password_form=password_form,
                         accounts_count=accounts_count,
                         transactions_count=transactions_count,
                         categories_count=categories_count,
                         budgets_count=budgets_count,
                         recent_activities=recent_activities)    
