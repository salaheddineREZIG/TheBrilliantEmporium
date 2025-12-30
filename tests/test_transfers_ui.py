def test_transfers_create_shows_accounts(app, client):
    # register and login user (registration logs in)
    client.post('/auth/register', data={
        'name': 'UI Test',
        'email': 'ui@example.com',
        'password': 'password',
        'confirm_password': 'password'
    }, follow_redirects=True)

    resp = client.get('/transfers/create')
    assert resp.status_code == 200
    data = resp.get_data(as_text=True)
    assert 'id="fromAccountsList"' in data
    assert 'id="toAccountsList"' in data
    assert 'class="account-selector' in data
