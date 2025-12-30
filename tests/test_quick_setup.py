import pytest
from datetime import date, timedelta
from app import create_app
from extensions import db
from models import User, Transaction, TransactionType, Category, Budget


@pytest.fixture
def app():
    app = create_app({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
        'WTF_CSRF_ENABLED': False,
    })

    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def register_user(client, email='test@example.com', password='password', name='Test'):
    return client.post('/auth/register', data={
        'name': name,
        'email': email,
        'password': password,
        'confirm_password': password
    }, follow_redirects=True)


def test_quick_setup_creates_budgets(app, client):
    register_user(client)

    # Confirm user and account/categories exist
    user = User.query.filter_by(email='test@example.com').first()
    assert user is not None

    # Pick an expense category
    cat = Category.query.filter_by(user_id=user.id, type=TransactionType.EXPENSE).first()
    assert cat is not None

    # Plan months: choose February 2025 and previous month January 2025 for transactions
    target_month = '202502'
    year = int(target_month[:4])
    month = int(target_month[4:6])

    # previous month
    prev_month = month - 1 if month > 1 else 12
    prev_year = year if month > 1 else year - 1

    prev_start = date(prev_year, prev_month, 1)
    if prev_month == 12:
        prev_end = date(prev_year + 1, 1, 1) - timedelta(days=1)
    else:
        prev_end = date(prev_year, prev_month + 1, 1) - timedelta(days=1)

    # Create a transaction in the previous month (amount > 0)
    # Registration creates a default account for the user
    account = user.accounts[0]
    t = Transaction(amount=100.00, date=prev_start, type=TransactionType.EXPENSE, category_id=cat.id, user_id=user.id, account_id=account.id)
    db.session.add(t)
    db.session.commit()

    # Call quick_setup
    resp = client.post('/budgets/quick-setup', json={'month': target_month})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data and data.get('success') is True

    # Verify budget was created with 10% reduction
    budget = Budget.query.filter_by(user_id=user.id, category_id=cat.id, month=int(target_month)).first()
    assert budget is not None
    assert abs(float(budget.amount) - 90.0) < 0.01


def test_quick_setup_invalid_month(app, client):
    register_user(client, email='bad@example.com')

    resp = client.post('/budgets/quick-setup', json={'month': 'bad'})
    assert resp.status_code == 400
    data = resp.get_json()
    assert 'Invalid month format' in data.get('error', '')


def test_quick_setup_missing_month(app, client):
    register_user(client, email='none@example.com')

    resp = client.post('/budgets/quick-setup', json={})
    assert resp.status_code == 400
    data = resp.get_json()
    assert data.get('error') == 'Month required'
