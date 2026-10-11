"""
Generate an Argon2id password hash.
Usage:  python -m scripts.generate_hash
"""
import getpass
from app.core.security import hash_password


def main() -> None:
    pw = getpass.getpass("Password to hash: ")
    if len(pw) < 8:
        print("Password should be at least 8 characters.")
        raise SystemExit(1)
    print()
    print("Argon2id hash:")
    print(hash_password(pw))
    print()
    print("Copy the line above and paste it into the SQL INSERT.")


if __name__ == "__main__":
    main()