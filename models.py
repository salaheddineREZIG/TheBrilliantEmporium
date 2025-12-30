# models.py
from extensions import db
from flask_login import UserMixin
from sqlalchemy.orm import relationship, backref
from sqlalchemy import ForeignKey, CheckConstraint, Enum, Numeric
from datetime import datetime, date
import enum

class TransactionType(enum.Enum):
    INCOME = "income"
    EXPENSE = "expense"

class AccountType(enum.Enum):
    CHECKING = "checking"
    SAVINGS = "savings"
    CREDIT_CARD = "credit_card"
    CASH = "cash"
    WALLET = "wallet"
    INVESTMENT = "investment"
    LOAN = "loan"

class SyncStatus(enum.Enum):
    LOCAL = 0
    SYNCED = 1
    PENDING = 2

# User Model with Flask-Login Mixin
class User(db.Model, UserMixin):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    hashed_password = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    last_login = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    accounts = relationship("Account", back_populates="user", cascade="all, delete-orphan")
    categories = relationship("Category", back_populates="user", cascade="all, delete-orphan")
    transactions = relationship("Transaction", back_populates="user", cascade="all, delete-orphan")
    budgets = relationship("Budget", back_populates="user", cascade="all, delete-orphan")
    
    def get_id(self):
        return str(self.id)
    
    def to_dict(self, include_relationships=False):
        data = {
            'id': self.id,
            'email': self.email,
            'name': self.name,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None
        }
        
        if include_relationships:
            data.update({
                'accounts': [account.to_dict() for account in self.accounts],
                'categories': [category.to_dict() for category in self.categories],
                'transaction_count': len(self.transactions),
                'budget_count': len(self.budgets)
            })
        
        return data

# ============== CATEGORY MODEL ==============
class Category(db.Model):
    """Represents spending/income categories with hierarchical structure"""
    __tablename__ = 'categories'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    type = db.Column(db.Enum(TransactionType), nullable=False)  # 'income' or 'expense'
    icon = db.Column(db.String(50), default='📁')  # Optional: for UI
    color = db.Column(db.String(7), default='#808080')  # Hex color
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    # Foreign Keys
    user_id = db.Column(db.Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=True)  # Null for system categories
    parent_id = db.Column(db.Integer, ForeignKey('categories.id', ondelete='SET NULL'), nullable=True)
    
    # Boolean flags
    is_system = db.Column(db.Boolean, default=False)  # System categories can't be deleted
    is_active = db.Column(db.Boolean, default=True)
    
    # Relationships
    user = relationship("User", back_populates="categories")
    parent = relationship("Category", remote_side=[id], backref=backref("subcategories", cascade="all, delete-orphan"))
    transactions = relationship("Transaction", back_populates="category")
    budgets = relationship("Budget", back_populates="category")
    
    # Indexes
    __table_args__ = (
        db.Index('idx_category_user_type', 'user_id', 'type'),
        db.Index('idx_category_parent', 'parent_id'),
    )
    
    def to_dict(self, include_relationships=False):
        """Serialize category data to dictionary"""
        data = {
            'id': self.id,
            'name': self.name,
            'type': self.type.value,
            'icon': self.icon,
            'color': self.color,
            'user_id': self.user_id,
            'parent_id': self.parent_id,
            'is_system': self.is_system,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
        
        if include_relationships and self.subcategories:
            data['subcategories'] = [cat.to_dict() for cat in self.subcategories]
        
        return data

# ============== ACCOUNT MODEL ==============
class Account(db.Model):
    """Represents a financial account (bank, cash, credit card, etc.)"""
    __tablename__ = 'accounts'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    type = db.Column(db.Enum(AccountType), nullable=False)
    initial_balance = db.Column(db.Numeric(12, 2), default=0.00)  # Initial balance when created
    current_balance = db.Column(db.Numeric(12, 2), default=0.00, nullable=False)
    currency = db.Column(db.String(3), default='USD')  # ISO currency code
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Foreign Keys
    user_id = db.Column(db.Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="accounts")
    transactions = relationship("Transaction", back_populates="account", cascade="all, delete-orphan")
    
    # Check constraint: balance can be negative for credit cards
    __table_args__ = (
        db.Index('idx_account_user', 'user_id'),
        db.Index('idx_account_user_active', 'user_id', 'is_active'),
    )
    
    def update_balance(self, transaction_type, amount):
        """Update account balance based on transaction type"""
        if transaction_type == TransactionType.INCOME:
            self.current_balance += amount
        else:  # EXPENSE
            self.current_balance -= amount
        self.updated_at = datetime.utcnow()
    
    def to_dict(self, include_relationships=False):
        """Serialize account data to dictionary"""
        data = {
            'id': self.id,
            'name': self.name,
            'type': self.type.value,
            'initial_balance': float(self.initial_balance),
            'current_balance': float(self.current_balance),
            'currency': self.currency,
            'is_active': self.is_active,
            'user_id': self.user_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
        
        if include_relationships:
            recent_transactions = [t.to_dict() for t in self.transactions[:10]]  # Last 10 transactions
            data['recent_transactions'] = recent_transactions
        
        return data

# ============== TRANSACTION MODEL ==============
class Transaction(db.Model):
    """Represents a financial transaction (income or expense)"""
    __tablename__ = 'transactions'
    
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    type = db.Column(db.Enum(TransactionType), nullable=False)
    date = db.Column(db.Date, nullable=False, default=date.today)
    description = db.Column(db.String(200), nullable=True)  # Note/description field
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Foreign Keys
    user_id = db.Column(db.Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    account_id = db.Column(db.Integer, ForeignKey('accounts.id', ondelete='CASCADE'), nullable=False)
    category_id = db.Column(db.Integer, ForeignKey('categories.id', ondelete='RESTRICT'), nullable=False)
    
    # Sync information (for mobile sync features)
    sync_status = db.Column(db.Enum(SyncStatus), default=SyncStatus.LOCAL)
    sync_id = db.Column(db.String(100), nullable=True, unique=True)  # For conflict resolution
    
    # Relationships
    user = relationship("User", back_populates="transactions")
    account = relationship("Account", back_populates="transactions")
    category = relationship("Category", back_populates="transactions")
    
    # Indexes for faster queries
    __table_args__ = (
        db.Index('idx_transaction_user_date', 'user_id', 'date'),
        db.Index('idx_transaction_account', 'account_id'),
        db.Index('idx_transaction_category', 'category_id'),
        db.Index('idx_transaction_type_date', 'type', 'date'),
        db.Index('idx_transaction_sync', 'sync_status', 'sync_id'),
        db.CheckConstraint('amount > 0', name='check_positive_amount'),
    )
    
    def to_dict(self, include_relationships=False):
        """Serialize transaction data to dictionary"""
        data = {
            'id': self.id,
            'amount': float(self.amount),
            'type': self.type.value,
            'date': self.date.isoformat() if self.date else None,
            'description': self.description,
            'user_id': self.user_id,
            'account_id': self.account_id,
            'category_id': self.category_id,
            'sync_status': self.sync_status.value,
            'sync_id': self.sync_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
        
        if include_relationships:
            data.update({
                'account_name': self.account.name if self.account else None,
                'category_name': self.category.name if self.category else None
            })
        
        return data

# ============== BUDGET MODEL ==============
class Budget(db.Model):
    """Represents monthly budget allocation for categories"""
    __tablename__ = 'budgets'
    
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    month = db.Column(db.Integer, nullable=False)  # Format: YYYYMM
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Foreign Keys
    user_id = db.Column(db.Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    category_id = db.Column(db.Integer, ForeignKey('categories.id', ondelete='CASCADE'), nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="budgets")
    category = relationship("Category", back_populates="budgets")
    
    # Composite unique constraint: one budget per category per month per user
    __table_args__ = (
        db.UniqueConstraint('user_id', 'category_id', 'month', name='uq_user_category_month'),
        db.Index('idx_budget_user_month', 'user_id', 'month'),
        db.CheckConstraint('month >= 200001 AND month <= 209912', name='check_valid_month'),
        db.CheckConstraint('amount >= 0', name='check_budget_amount'),
    )
    
    @property
    def spent_amount(self):
        """Total spent for this category in the budget month.

        This property can be computed dynamically or set by view code which
        pre-computes the value and assigns it. We keep an internal field
        `_spent_amount` so both usages work.
        """
        return float(getattr(self, '_spent_amount', 0.0))

    @spent_amount.setter
    def spent_amount(self, value):
        self._spent_amount = float(value) if value is not None else 0.0
    
    @property
    def remaining_amount(self):
        """Calculate remaining budget amount"""
        return float(self.amount) - self.spent_amount
    
    def to_dict(self, include_relationships=False):
        """Serialize budget data to dictionary"""
        data = {
            'id': self.id,
            'amount': float(self.amount),
            'month': self.month,
            'user_id': self.user_id,
            'category_id': self.category_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'spent_amount': self.spent_amount,
            'remaining_amount': self.remaining_amount
        }
        
        if include_relationships and self.category:
            data['category_name'] = self.category.name
        
        return data

# ============== TRANSFER MODEL (Optional but recommended) ==============
class Transfer(db.Model):
    """Represents money transfers between accounts (not spending)"""
    __tablename__ = 'transfers'
    
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    date = db.Column(db.Date, nullable=False, default=date.today)
    description = db.Column(db.String(200), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    # Foreign Keys
    user_id = db.Column(db.Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    from_account_id = db.Column(db.Integer, ForeignKey('accounts.id'), nullable=False)
    to_account_id = db.Column(db.Integer, ForeignKey('accounts.id'), nullable=False)
    
    # Relationships
    user = relationship("User")
    from_account = relationship("Account", foreign_keys=[from_account_id])
    to_account = relationship("Account", foreign_keys=[to_account_id])
    
    # Check constraint to prevent transferring to same account
    __table_args__ = (
        db.CheckConstraint('from_account_id != to_account_id', name='check_different_accounts'),
        db.CheckConstraint('amount > 0', name='check_transfer_amount'),
        db.Index('idx_transfer_user_date', 'user_id', 'date'),
    )
    
    def to_dict(self):
        """Serialize transfer data to dictionary"""
        return {
            'id': self.id,
            'amount': float(self.amount),
            'date': self.date.isoformat() if self.date else None,
            'description': self.description,
            'user_id': self.user_id,
            'from_account_id': self.from_account_id,
            'to_account_id': self.to_account_id,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
        
        
class UserSettings(db.Model):
    """User-specific application settings"""
    __tablename__ = 'user_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False, unique=True)
    
    # General Settings
    default_currency = db.Column(db.String(3), default='USD')
    date_format = db.Column(db.String(20), default='MM/DD/YYYY')  # MM/DD/YYYY, DD/MM/YYYY, YYYY-MM-DD
    first_day_of_week = db.Column(db.Integer, default=0)  # 0=Sunday, 1=Monday
    theme = db.Column(db.String(10), default='dark')  # dark, light, auto
    
    # Dashboard Preferences
    show_charts = db.Column(db.Boolean, default=True)
    show_recent = db.Column(db.Boolean, default=True)
    show_budgets = db.Column(db.Boolean, default=True)
    
    # Transaction Preferences
    auto_categorize = db.Column(db.Boolean, default=True)
    duplicate_detection = db.Column(db.Boolean, default=True)
    require_description = db.Column(db.Boolean, default=False)
    
    # Notification Settings
    budget_alerts = db.Column(db.Boolean, default=True)
    large_transactions = db.Column(db.Boolean, default=True)
    weekly_summary = db.Column(db.Boolean, default=True)
    monthly_report = db.Column(db.Boolean, default=True)
    app_budget_alerts = db.Column(db.Boolean, default=True)
    app_bill_reminders = db.Column(db.Boolean, default=True)
    app_goals_update = db.Column(db.Boolean, default=True)
    
    # Large transaction threshold (percentage of monthly income)
    large_transaction_threshold = db.Column(db.Numeric(5, 2), default=20.0)  # 20%
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", backref=backref("settings", uselist=False))
    
    def to_dict(self):
        """Serialize settings to dictionary"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'general': {
                'default_currency': self.default_currency,
                'date_format': self.date_format,
                'first_day_of_week': self.first_day_of_week,
                'theme': self.theme
            },
            'dashboard': {
                'show_charts': self.show_charts,
                'show_recent': self.show_recent,
                'show_budgets': self.show_budgets
            },
            'transactions': {
                'auto_categorize': self.auto_categorize,
                'duplicate_detection': self.duplicate_detection,
                'require_description': self.require_description
            },
            'notifications': {
                'budget_alerts': self.budget_alerts,
                'large_transactions': self.large_transactions,
                'weekly_summary': self.weekly_summary,
                'monthly_report': self.monthly_report,
                'app_budget_alerts': self.app_budget_alerts,
                'app_bill_reminders': self.app_bill_reminders,
                'app_goals_update': self.app_goals_update,
                'large_transaction_threshold': float(self.large_transaction_threshold)
            },
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }