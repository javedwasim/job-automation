import pytest

from app.security.token_encryption import decrypt_token, encrypt_token


def test_encrypt_decrypt_round_trip() -> None:
    plaintext = "ya29.some-fake-access-token"

    ciphertext = encrypt_token(plaintext)

    assert ciphertext != plaintext
    assert decrypt_token(ciphertext) == plaintext


def test_decrypt_rejects_corrupted_ciphertext() -> None:
    ciphertext = encrypt_token("some-token")
    corrupted = ciphertext[:-4] + "abcd"

    with pytest.raises(ValueError):
        decrypt_token(corrupted)
