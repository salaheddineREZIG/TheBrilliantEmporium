from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, BooleanField
from wtforms.validators import Optional
from wtforms.validators import DataRequired, Email, Length, EqualTo, ValidationError
from models import db, User

# ============== CUSTOM VALIDATORS ==============
class UniqueEmail:
    """Validator to check if email is unique"""
    def __init__(self, message=None):
        if not message:
            message = 'This email is already registered.'
        self.message = message

    def __call__(self, form, field):
        user = User.query.filter_by(email=field.data).first()
        if user:
            raise ValidationError(self.message)


# ============== AUTHENTICATION FORMS ==============
class LoginForm(FlaskForm):
    """Form for user login"""
    email = StringField('Email', validators=[
        DataRequired(message='Email is required'),
        Email(message='Please enter a valid email address')
    ], render_kw={
        "placeholder": "your.email@example.com",
        "class": "form-control form-control-lg"
    })
    
    password = PasswordField('Password', validators=[
        DataRequired(message='Password is required'),
        Length(min=6, message='Password must be at least 6 characters')
    ], render_kw={
        "placeholder": "Enter your password",
        "class": "form-control form-control-lg"
    })

    remember_me = BooleanField('Remember Me', default=False, render_kw={
        "class": "form-check-input"
    })
        
    submit = SubmitField('Login', render_kw={
        "class": "btn btn-primary btn-lg w-100"
    })


class RegistrationForm(FlaskForm):
    """Form for user registration"""
    name = StringField('Full Name', validators=[
        DataRequired(message='Name is required'),
        Length(min=2, max=100, message='Name must be between 2 and 100 characters')
    ], render_kw={
        "placeholder": "John Doe",
        "class": "form-control form-control-lg"
    })
    
    email = StringField('Email', validators=[
        DataRequired(message='Email is required'),
        Email(message='Please enter a valid email address'),
        UniqueEmail(message='This email is already registered')
    ], render_kw={
        "placeholder": "your.email@example.com",
        "class": "form-control form-control-lg"
    })
    
    password = PasswordField('Password', validators=[
        DataRequired(message='Password is required'),
        Length(min=6, message='Password must be at least 6 characters'),
        Length(max=128, message='Password is too long')
    ], render_kw={
        "placeholder": "Create a strong password",
        "class": "form-control form-control-lg"
    })
    
    confirm_password = PasswordField('Confirm Password', validators=[
        DataRequired(message='Please confirm your password'),
        EqualTo('password', message='Passwords must match')
    ], render_kw={
        "placeholder": "Confirm your password",
        "class": "form-control form-control-lg"
    })
    
    submit = SubmitField('Create Account', render_kw={
        "class": "btn btn-primary btn-lg w-100"
    })


# ============== PASSWORD MANAGEMENT FORMS ==============
class ForgotPasswordForm(FlaskForm):
    """Form for password reset request"""
    email = StringField('Email', validators=[
        DataRequired(message='Email is required'),
        Email(message='Please enter a valid email address')
    ], render_kw={
        "placeholder": "Enter your email address",
        "class": "form-control form-control-lg"
    })
    
    submit = SubmitField('Send Reset Link', render_kw={
        "class": "btn btn-primary btn-lg w-100"
    })


class ResetPasswordForm(FlaskForm):
    """Form for password reset"""
    password = PasswordField('New Password', validators=[
        DataRequired(message='Password is required'),
        Length(min=6, message='Password must be at least 6 characters')
    ], render_kw={
        "placeholder": "Enter new password",
        "class": "form-control form-control-lg"
    })
    
    confirm_password = PasswordField('Confirm New Password', validators=[
        DataRequired(message='Please confirm your password'),
        EqualTo('password', message='Passwords must match')
    ], render_kw={
        "placeholder": "Confirm new password",
        "class": "form-control form-control-lg"
    })
    
    submit = SubmitField('Reset Password', render_kw={
        "class": "btn btn-primary btn-lg w-100"
    })

# ============== PROFILE FORMS ==============
class ProfileForm(FlaskForm):
    """Form for editing user profile"""
    name = StringField('Full Name', validators=[
        DataRequired(message='Name is required'),
        Length(min=2, max=100, message='Name must be between 2 and 100 characters')
    ], render_kw={
        "class": "form-control"
    })
    
    email = StringField('Email', validators=[
        DataRequired(message='Email is required'),
        Email(message='Please enter a valid email address')
    ], render_kw={
        "class": "form-control"
    })
    
    current_password = PasswordField('Current Password (required to change email)', validators=[
        Optional()
    ], render_kw={
        "placeholder": "Enter current password to change email",
        "class": "form-control"
    })


class ChangePasswordForm(FlaskForm):
    """Form for changing password"""
    current_password = PasswordField('Current Password', validators=[
        DataRequired(message='Current password is required')
    ], render_kw={
        "class": "form-control"
    })
    
    new_password = PasswordField('New Password', validators=[
        DataRequired(message='New password is required'),
        Length(min=6, message='Password must be at least 6 characters')
    ], render_kw={
        "class": "form-control"
    })
    
    confirm_password = PasswordField('Confirm New Password', validators=[
        DataRequired(message='Please confirm your password'),
        EqualTo('new_password', message='Passwords must match')
    ], render_kw={
        "class": "form-control"
    })