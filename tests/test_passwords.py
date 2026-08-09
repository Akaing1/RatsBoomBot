from web.passwords import hash_password, password_needs_rehash, verify_password


def test_hash_password_does_not_store_plaintext():
    password = "test-password"
    password_hash = hash_password(password)

    assert password_hash != password
    assert password not in password_hash


def test_verify_password_accepts_correct_password():
    password = "test-password"
    password_hash = hash_password(password)

    assert verify_password(password_hash, password) is True


def test_verify_password_rejects_incorrect_password():
    password_hash = hash_password("correct-password")

    assert verify_password(password_hash, "wrong-password") is False


def test_current_password_hash_does_not_need_rehash():
    password_hash = hash_password("test-password")

    assert password_needs_rehash(password_hash) is False
