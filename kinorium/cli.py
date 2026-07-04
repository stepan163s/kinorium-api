import sys
import getpass
from kinorium.client import KinoriumClient
from kinorium.exceptions import KinoriumError

def main():
    print("Kinorium API Authentication Helper")
    print("==================================")
    
    try:
        email = input("Email: ").strip()
        if not email:
            print("Error: Email cannot be empty.", file=sys.stderr)
            sys.exit(1)
            
        password = getpass.getpass("Password: ")
        if not password:
            print("Error: Password cannot be empty.", file=sys.stderr)
            sys.exit(1)
            
        print("\nAuthenticating...")
        client = KinoriumClient()
        client.authenticate(email, password)
        
        auth = client.auth_cookie
        phpsessid = client.phpsessid_cookie
        
        if not auth or not phpsessid:
            print("Error: Authentication succeeded but cookies were not set.", file=sys.stderr)
            sys.exit(1)
            
        print("\nSuccess! Your session cookies:")
        print(f"auth: {auth}")
        print(f"PHPSESSID: {phpsessid}")
        print("\nHTTP Cookie Header:")
        print(f"Cookie: auth={auth}; PHPSESSID={phpsessid}")
        
    except KinoriumError as e:
        print(f"\nAuthentication Error: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nAborted.", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
