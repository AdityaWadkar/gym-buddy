from getpass import getpass

import bcrypt


def main() -> None:
    password = getpass("Choose the Gym Buddy login password: ")
    confirmation = getpass("Enter it again: ")
    if not password:
        raise SystemExit("Password cannot be empty.")
    if password != confirmation:
        raise SystemExit("Passwords do not match.")

    password_hash = bcrypt.hashpw(
        password.encode("utf-8"), bcrypt.gensalt(rounds=12)
    ).decode("utf-8")
    print("\nAdd this bcrypt hash as GYM_BUDDY_PASSWORD_HASH in your .env file")
    print("or Streamlit secrets. Do not store or commit the original password.\n")
    print(password_hash)


if __name__ == "__main__":
    main()
