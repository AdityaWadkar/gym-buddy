import bcrypt

from utils import generate_password_hash


def test_hash_generator_outputs_a_hash_without_storing_plaintext(
    monkeypatch, capsys
) -> None:
    answers = iter(("test-only-password", "test-only-password"))
    monkeypatch.setattr(generate_password_hash, "getpass", lambda prompt: next(answers))

    generate_password_hash.main()
    output = capsys.readouterr().out
    password_hash = output.strip().splitlines()[-1]

    assert password_hash.startswith("$2")
    assert bcrypt.checkpw(b"test-only-password", password_hash.encode("utf-8"))
    assert "test-only-password" not in output
