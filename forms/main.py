from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, SelectField, DecimalField, DateField, TextAreaField, BooleanField, IntegerField, RadioField, FileField
from wtforms.validators import DataRequired, Email, Length, EqualTo, NumberRange, Optional, ValidationError
from datetime import date
from models import AccountType, TransactionType


class ValidMonth:
    """Validator for month field in YYYYMM format"""
    def __init__(self, message=None):
        if not message:
            message = 'Month must be in YYYYMM format (e.g., 202412)'
        self.message = message

    def __call__(self, form, field):
        try:
            month_str = str(field.data)
            if len(month_str) != 6:
                raise ValidationError(self.message)
            
            year = int(month_str[:4])
            month = int(month_str[4:6])
            
            if year < 2000 or year > 2100:
                raise ValidationError('Year must be between 2000 and 2100')
            if month < 1 or month > 12:
                raise ValidationError('Month must be between 1 and 12')
        except (ValueError, TypeError):
            raise ValidationError(self.message)

class PositiveAmount:
    """Validator for positive amounts"""
    def __init__(self, message=None):
        if not message:
            message = 'Amount must be positive'
        self.message = message

    def __call__(self, form, field):
        if field.data is None or field.data <= 0:
            raise ValidationError(self.message)

class DateNotFuture:
    """Validator to ensure date is not in the future"""
    def __init__(self, message=None):
        if not message:
            message = 'Date cannot be in the future'
        self.message = message

    def __call__(self, form, field):
        if field.data and field.data > date.today():
            raise ValidationError(self.message)


# ============== ACCOUNT FORMS ==============
class AccountForm(FlaskForm):
    """Form for creating/editing accounts"""
    name = StringField('Account Name', validators=[
        DataRequired(message='Account name is required'),
        Length(min=2, max=100, message='Name must be between 2 and 100 characters')
    ], render_kw={
        "placeholder": "e.g., Chase Checking, PayPal, Cash",
        "class": "form-control"
    })
    
    type = SelectField('Account Type', choices=[
        (AccountType.CHECKING.value, 'Checking Account'),
        (AccountType.SAVINGS.value, 'Savings Account'),
        (AccountType.CREDIT_CARD.value, 'Credit Card'),
        (AccountType.CASH.value, 'Cash'),
        (AccountType.WALLET.value, 'Digital Wallet'),
        (AccountType.INVESTMENT.value, 'Investment Account'),
        (AccountType.LOAN.value, 'Loan')
    ], validators=[
        DataRequired(message='Please select an account type')
    ], render_kw={
        "class": "form-select"
    })
    
    initial_balance = DecimalField('Initial Balance', validators=[
        DataRequired(message='Initial balance is required'),
        PositiveAmount()
    ], default=0.00, places=2, render_kw={
        "placeholder": "0.00",
        "class": "form-control",
        "step": "0.01"
    })
    
    currency = SelectField('Currency', choices=[
        ('USD', 'US Dollar ($)'),
        ('EUR', 'Euro (€)'),
        ('GBP', 'British Pound (£)'),
        ('CAD', 'Canadian Dollar (C$)'),
        ('AUD', 'Australian Dollar (A$)')
    ], default='USD', render_kw={
        "class": "form-select"
    })
    
    submit = SubmitField('Save Account', render_kw={
        "class": "btn btn-primary"
    })


# ============== TRANSACTION FORMS ==============
class TransactionForm(FlaskForm):
    """Form for creating/editing transactions"""
    type = RadioField('Transaction Type', choices=[
        (TransactionType.EXPENSE.value, 'Expense'),
        (TransactionType.INCOME.value, 'Income')
    ], validators=[
        DataRequired(message='Please select transaction type')
    ], default=TransactionType.EXPENSE.value)
    
    amount = DecimalField('Amount', validators=[
        DataRequired(message='Amount is required'),
        PositiveAmount()
    ], places=2, render_kw={
        "placeholder": "0.00",
        "class": "form-control",
        "step": "0.01"
    })
    
    date = DateField('Date', validators=[
        DataRequired(message='Date is required'),
        DateNotFuture()
    ], default=date.today, render_kw={
        "class": "form-control",
        "type": "date"
    })
    
    account_id = SelectField('Account', coerce=int, validators=[
        DataRequired(message='Please select an account')
    ], render_kw={
        "class": "form-select"
    })
    
    category_id = SelectField('Category', coerce=int, validators=[
        DataRequired(message='Please select a category')
    ], render_kw={
        "class": "form-select"
    })
    
    description = TextAreaField('Description', validators=[
        Optional(),
        Length(max=200, message='Description cannot exceed 200 characters')
    ], render_kw={
        "placeholder": "Add a description or note...",
        "class": "form-control",
        "rows": 3
    })
    
    # Recurring transaction fields (optional)
    is_recurring = BooleanField('Make this a recurring transaction')
    
    recurring_frequency = SelectField('Frequency', choices=[
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('yearly', 'Yearly')
    ], default='monthly', render_kw={
        "class": "form-select",
        "disabled": True
    })
    
    recurring_end_date = DateField('End Date', validators=[
        Optional()
    ], render_kw={
        "class": "form-control",
        "type": "date",
        "disabled": True
    })
    
    submit = SubmitField('Save Transaction', render_kw={
        "class": "btn btn-primary"
    })
    
    def __init__(self, *args, **kwargs):
        super(TransactionForm, self).__init__(*args, **kwargs)
        # Dynamically populate account and category choices
        self.account_id.choices = []
        self.category_id.choices = []


# ============== TRANSFER FORM ==============
class TransferForm(FlaskForm):
    """Form for transferring money between accounts"""
    amount = DecimalField('Amount', validators=[
        DataRequired(message='Amount is required'),
        PositiveAmount()
    ], places=2, render_kw={
        "placeholder": "0.00",
        "class": "form-control",
        "step": "0.01"
    })
    
    date = DateField('Date', validators=[
        DataRequired(message='Date is required'),
        DateNotFuture()
    ], default=date.today, render_kw={
        "class": "form-control",
        "type": "date"
    })
    
    from_account_id = SelectField('From Account', coerce=int, validators=[
        DataRequired(message='Please select source account')
    ], render_kw={
        "class": "form-select"
    })
    
    to_account_id = SelectField('To Account', coerce=int, validators=[
        DataRequired(message='Please select destination account')
    ], render_kw={
        "class": "form-select"
    })
    
    description = TextAreaField('Description', validators=[
        Optional(),
        Length(max=200, message='Description cannot exceed 200 characters')
    ], render_kw={
        "placeholder": "Add a description or note...",
        "class": "form-control",
        "rows": 2
    })
    
    submit = SubmitField('Transfer Money', render_kw={
        "class": "btn btn-primary"
    })
    
    def validate(self, extra_validators=None):
        """Custom validation to ensure different accounts"""
        if not super().validate(extra_validators):
            return False
        
        if self.from_account_id.data == self.to_account_id.data:
            self.to_account_id.errors.append('Cannot transfer to the same account')
            return False
        
        return True


# ============== CATEGORY FORMS ==============
class CategoryForm(FlaskForm):
    """Form for creating/editing categories"""
    name = StringField('Category Name', validators=[
        DataRequired(message='Category name is required'),
        Length(min=2, max=100, message='Name must be between 2 and 100 characters')
    ], render_kw={
        "placeholder": "e.g., Groceries, Salary, Entertainment",
        "class": "form-control"
    })
    
    type = SelectField('Type', choices=[
        (TransactionType.EXPENSE.value, 'Expense'),
        (TransactionType.INCOME.value, 'Income')
    ], validators=[
        DataRequired(message='Please select category type')
    ], render_kw={
        "class": "form-select"
    })
    
    parent_id = SelectField('Parent Category (Optional)', coerce=int, validators=[
        Optional()
    ], render_kw={
        "class": "form-select"
    })
    
    icon = SelectField('Icon', choices=[
        ('💰', '💰 Money'),
        ('🍔', '🍔 Food'),
        ('🚗', '🚗 Transportation'),
        ('🏠', '🏠 Housing'),
        ('💡', '💡 Utilities'),
        ('🛒', '🛒 Shopping'),
        ('🎬', '🎬 Entertainment'),
        ('🏥', '🏥 Healthcare'),
        ('📚', '📚 Education'),
        ('✈️', '✈️ Travel'),
        ('💼', '💼 Salary'),
        ('🎁', '🎁 Gift'),
        ('📈', '📈 Investment'),
        ('📤', '📤 Other Expense'),
        ('📥', '📥 Other Income')
    ], default='💰', render_kw={
        "class": "form-select"
    })
    
    color = StringField('Color', validators=[
        Optional(),
        Length(max=7)
    ], default='#808080', render_kw={
        "class": "form-control",
        "type": "color"
    })
    
    submit = SubmitField('Save Category', render_kw={
        "class": "btn btn-primary"
    })


# ============== BUDGET FORMS ==============
class BudgetForm(FlaskForm):
    """Form for creating/editing budgets"""
    category_id = SelectField('Category', coerce=int, validators=[
        DataRequired(message='Please select a category')
    ], render_kw={
        "class": "form-select"
    })
    
    amount = DecimalField('Budget Amount', validators=[
        DataRequired(message='Amount is required'),
        PositiveAmount()
    ], places=2, render_kw={
        "placeholder": "0.00",
        "class": "form-control",
        "step": "0.01"
    })
    
    month = IntegerField('Month', validators=[
        DataRequired(message='Month is required'),
        ValidMonth()
    ], render_kw={
        "placeholder": "YYYYMM (e.g., 202412)",
        "class": "form-control",
        "min": "200001",
        "max": "209912"
    })
    
    submit = SubmitField('Save Budget', render_kw={
        "class": "btn btn-primary"
    })




# ============== SETTINGS FORMS ==============
class SettingsForm(FlaskForm):
    """Form for application settings"""
    default_currency = SelectField('Default Currency', choices=[
        ('USD', 'US Dollar ($)'),
        ('EUR', 'Euro (€)'),
        ('GBP', 'British Pound (£)'),
        ('CAD', 'Canadian Dollar (C$)'),
        ('AUD', 'Australian Dollar (A$)')
    ], default='USD', render_kw={
        "class": "form-select"
    })
    
    date_format = SelectField('Date Format', choices=[
        ('MM/DD/YYYY', 'MM/DD/YYYY'),
        ('DD/MM/YYYY', 'DD/MM/YYYY'),
        ('YYYY-MM-DD', 'YYYY-MM-DD')
    ], default='MM/DD/YYYY', render_kw={
        "class": "form-select"
    })
    
    first_day_of_week = SelectField('First Day of Week', choices=[
        ('0', 'Sunday'),
        ('1', 'Monday')
    ], default='0', render_kw={
        "class": "form-select"
    })
    
    theme = SelectField('Theme', choices=[
        ('dark', 'Dark Mode'),
        ('light', 'Light Mode')
    ], default='dark', render_kw={
        "class": "form-select"
    })
    
    # Notification settings
    budget_alerts = BooleanField('Budget alerts', default=True)
    large_transactions = BooleanField('Large transaction alerts', default=True)
    weekly_summary = BooleanField('Weekly summary emails', default=True)
    
    submit = SubmitField('Save Settings', render_kw={
        "class": "btn btn-primary"
    })


# ============== SEARCH/FILTER FORMS ==============
class TransactionFilterForm(FlaskForm):
    """Form for filtering transactions"""
    date_from = DateField('From', validators=[
        Optional()
    ], render_kw={
        "class": "form-control",
        "type": "date"
    })
    
    date_to = DateField('To', validators=[
        Optional()
    ], render_kw={
        "class": "form-control",
        "type": "date"
    })
    
    account_id = SelectField('Account', coerce=int, validators=[
        Optional()
    ], render_kw={
        "class": "form-select"
    })
    
    category_id = SelectField('Category', coerce=int, validators=[
        Optional()
    ], render_kw={
        "class": "form-select"
    })
    
    type = SelectField('Type', choices=[
        ('all', 'All'),
        ('income', 'Income'),
        ('expense', 'Expense')
    ], default='all', render_kw={
        "class": "form-select"
    })
    
    search = StringField('Search', validators=[
        Optional(),
        Length(max=100)
    ], render_kw={
        "placeholder": "Search description...",
        "class": "form-control"
    })
    
    submit = SubmitField('Apply Filters', render_kw={
        "class": "btn btn-secondary"
    })
    
    clear = SubmitField('Clear Filters', render_kw={
        "class": "btn btn-outline-secondary"
    })


class SearchForm(FlaskForm):
    """Form for global search"""
    query = StringField('Search', validators=[
        DataRequired(message='Please enter a search term'),
        Length(min=2, max=100, message='Search term must be between 2 and 100 characters')
    ], render_kw={
        "placeholder": "Search transactions, accounts, categories...",
        "class": "form-control"
    })
    
    submit = SubmitField('Search', render_kw={
        "class": "btn btn-primary"
    })


# ============== IMPORT/EXPORT FORMS ==============
class ImportForm(FlaskForm):
    """Form for importing data"""
    import_type = SelectField('Import Type', choices=[
        ('csv', 'CSV File'),
        ('json', 'JSON File')
    ], default='csv', render_kw={
        "class": "form-select"
    })
    
    file = FileField('File', validators=[
        DataRequired(message='Please select a file to upload')
    ], render_kw={
        "class": "form-control",
        "accept": ".csv,.json"
    })
    
    submit = SubmitField('Import Data', render_kw={
        "class": "btn btn-primary"
    })


