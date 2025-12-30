from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from datetime import datetime
from extensions import db
from models import Category, Transaction, TransactionType
from forms.main import CategoryForm
import json

categories_bp = Blueprint('categories', __name__)

@categories_bp.route('/')
@login_required
def index():
    """List all categories"""
    # Get categories organized by type
    expense_categories = Category.query.filter_by(
        user_id=current_user.id,
        type=TransactionType.EXPENSE,
        is_active=True
    ).order_by(Category.name).all()
    
    income_categories = Category.query.filter_by(
        user_id=current_user.id,
        type=TransactionType.INCOME,
        is_active=True
    ).order_by(Category.name).all()
    
    # Get transaction counts and subcategories
    all_categories = expense_categories + income_categories
    for category in all_categories:
        category.transaction_count = Transaction.query.filter_by(
            category_id=category.id,
            user_id=current_user.id
        ).count()
        
        # Get subcategories
        category.subcategories = Category.query.filter_by(
            parent_id=category.id,
            is_active=True
        ).all()
    
    return render_template('categories/index.html',
                         expense_categories=expense_categories,
                         income_categories=income_categories)

@categories_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    """Create new category"""
    form = CategoryForm()
    
    # Set default values from URL parameters
    if request.args.get('type'):
        form.type.data = request.args.get('type')
    
    # Populate parent category choices
    form.parent_id.choices = [(0, 'None (Top Level)')] + [
        (cat.id, f"{cat.icon} {cat.name}") 
        for cat in Category.query.filter_by(
            user_id=current_user.id,
            parent_id=None,
            is_active=True
        ).all()
    ]
    
    # Common icons for selection
    icons = ['📁', '💰', '🛒', '🍽️', '🚗', '🏠', '🏥', '🎓', '🎬', '🏋️', '✈️', '👕', 
             '📱', '💻', '🎮', '📚', '🎵', '🎨', '⚽', '🎭', '💡', '🔧', '🎁', '💸']
    
    # Common colors for quick selection
    quick_colors = ['#FF6B6B', '#FFD166', '#06D6A0', '#118AB2', '#073B4C',
                   '#EF476F', '#7209B7', '#3A86FF', '#FB5607', '#8338EC']
    
    if form.validate_on_submit():
        category = Category(
            name=form.name.data,
            type=TransactionType(form.type.data),
            icon=form.icon.data,
            color=form.color.data,
            user_id=current_user.id,
            parent_id=form.parent_id.data if form.parent_id.data and form.parent_id.data != 0 else None,
            created_at=datetime.utcnow(),
            is_system=False,
            is_active=True
        )
        
        db.session.add(category)
        db.session.commit()
        
        flash('Category created successfully!', 'success')
        return redirect(url_for('categories.index'))
    
    return render_template('categories/create.html', 
                         form=form, 
                         icons=icons, 
                         quick_colors=quick_colors)

@categories_bp.route('/<int:category_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(category_id):
    """Edit category"""
    category = Category.query.filter_by(
        id=category_id,
        user_id=current_user.id
    ).first_or_404()
    
    # Prevent editing system categories
    if category.is_system:
        flash('System categories cannot be edited.', 'danger')
        return redirect(url_for('categories.index'))
    
    form = CategoryForm(obj=category)
    
    # Populate parent category choices (exclude self and descendants)
    all_categories = Category.query.filter_by(
        user_id=current_user.id,
        is_active=True
    ).all()
    
    # Helper function to check if a category is self or descendant
    def is_self_or_descendant(cat, target_id):
        if cat.id == target_id:
            return True
        # Check descendants
        for subcat in cat.subcategories:
            if is_self_or_descendant(subcat, target_id):
                return True
        return False
    
    # Get available parents (not self or descendants)
    available_parents = [cat for cat in all_categories 
                        if cat.parent_id is None and 
                        not is_self_or_descendant(cat, category_id) and
                        cat.id != category_id]
    
    form.parent_id.choices = [(0, 'None (Top Level)')] + [
        (cat.id, f"{cat.icon} {cat.name}") 
        for cat in available_parents
    ]
    
    # Common icons and colors
    icons = ['📁', '💰', '🛒', '🍽️', '🚗', '🏠', '🏥', '🎓', '🎬', '🏋️', '✈️', '👕', 
             '📱', '💻', '🎮', '📚', '🎵', '🎨', '⚽', '🎭', '💡', '🔧', '🎁', '💸']
    
    quick_colors = ['#FF6B6B', '#FFD166', '#06D6A0', '#118AB2', '#073B4C',
                   '#EF476F', '#7209B7', '#3A86FF', '#FB5607', '#8338EC']
    
    # Get transaction count
    category.transaction_count = Transaction.query.filter_by(
        category_id=category.id,
        user_id=current_user.id
    ).count()
    
    # Get subcategories
    category.subcategories = Category.query.filter_by(
        parent_id=category.id,
        is_active=True
    ).all()
    
    if form.validate_on_submit():
        category.name = form.name.data
        category.type = TransactionType(form.type.data)
        category.icon = form.icon.data
        category.color = form.color.data
        category.parent_id = form.parent_id.data if form.parent_id.data and form.parent_id.data != 0 else None
        
        db.session.commit()
        
        flash('Category updated successfully!', 'success')
        return redirect(url_for('categories.index'))
    
    return render_template('categories/edit.html', 
                         form=form, 
                         category=category,
                         icons=icons, 
                         quick_colors=quick_colors)

@categories_bp.route('/<int:category_id>/delete', methods=['POST'])
@login_required
def delete(category_id):
    """Delete category (soft delete)"""
    category = Category.query.filter_by(
        id=category_id,
        user_id=current_user.id
    ).first_or_404()
    
    # Prevent deleting system categories
    if category.is_system:
        flash('System categories cannot be deleted.', 'danger')
        return redirect(url_for('categories.index'))
    
    # Check if category has transactions
    transaction_count = Transaction.query.filter_by(
        category_id=category_id,
        user_id=current_user.id
    ).count()
    
    if transaction_count > 0:
        flash('Cannot delete category with transactions. Archive it instead.', 'danger')
        return redirect(url_for('categories.index'))
    
    # Check if category has subcategories
    if category.subcategories:
        # Move subcategories to parent or make them top-level
        for subcat in category.subcategories:
            subcat.parent_id = category.parent_id
        
        flash('Subcategories moved to parent category.', 'info')
    
    # Soft delete
    category.is_active = False
    db.session.commit()
    
    flash('Category deleted successfully!', 'success')
    return redirect(url_for('categories.index'))

@categories_bp.route('/<int:category_id>/restore', methods=['POST'])
@login_required
def restore(category_id):
    """Restore archived category"""
    category = Category.query.filter_by(
        id=category_id,
        user_id=current_user.id
    ).first_or_404()
    
    category.is_active = True
    db.session.commit()
    
    flash('Category restored successfully!', 'success')
    return redirect(url_for('categories.index'))

@categories_bp.route('/api/categories/<type>')
@login_required
def get_categories_by_type(type):
    """Get categories by type for API"""
    categories = Category.query.filter_by(
        user_id=current_user.id,
        type=TransactionType(type),
        is_active=True
    ).order_by(Category.name).all()
    
    return jsonify([{
        'id': cat.id,
        'name': cat.name,
        'icon': cat.icon,
        'color': cat.color
    } for cat in categories])

def self_or_descendant(category, target_id, all_categories):
    """Check if category is self or descendant of target"""
    if category.id == target_id:
        return True
    
    current = category
    while current.parent_id:
        if current.parent_id == target_id:
            return True
        # Find parent
        parent = next((c for c in all_categories if c.id == current.parent_id), None)
        if not parent:
            break
        current = parent
    
    return False