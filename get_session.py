"""Obtain an auth token using environment variables, local JSON or a prompt."""
import getpass
import json
import os
from pathlib import Path
import sys

from kinorium import KinoriumClient
from kinorium.exceptions import KinoriumError

LOCAL_CREDENTIALS = Path(__file__).with_name("get_session.local.json")


def load_credentials(path=None):
    """Environment variables take precedence over the ignored local file."""
    source = Path(path) if path is not None else LOCAL_CREDENTIALS
    values = {}
    if source.exists() or path is not None:
        values = json.loads(source.read_text(encoding="utf-8"))
        if not isinstance(values, dict):
            raise ValueError("Credentials file must contain a JSON object")
    email = os.getenv("KINORIUM_EMAIL", values.get("email", ""))
    password = os.getenv("KINORIUM_PASSWORD", values.get("password", ""))
    if not isinstance(email, str) or not isinstance(password, str):
        raise ValueError("Email and password must be strings")
    return email, password


def main():
    client = None
    try:
        email, password = load_credentials()
        email = email or input("Email: ").strip()
        password = password or getpass.getpass("Password: ")
        if not email or not password:
            print("Email and password cannot be empty.", file=sys.stderr)
            return 1
        client = KinoriumClient()
        print("Authenticating...")
        client.authenticate(email, password)
        auth = client.auth_cookie
        if not auth:
            print("Authentication did not return an auth token.", file=sys.stderr)
            return 1
        print("Success! Copy this token to use in your code:")
        print(auth)
        print("Example usage:")
        print(f'client = KinoriumClient(auth="{auth}")')
        return 0
    except (KinoriumError, OSError, ValueError) as exc:
        print(f"Authentication failed: {exc}", file=sys.stderr)
        return 1
    except (KeyboardInterrupt, EOFError):
        print("Aborted.", file=sys.stderr)
        return 130
    finally:
        if client is not None:
            client._request._session.close()


if __name__ == "__main__":
    sys.exit(main())
