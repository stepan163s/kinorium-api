from kinorium import KinoriumClient
from kinorium.exceptions import KinoriumError

# ==========================================
# ENTER YOUR KINORIUM CREDENTIALS HERE
# ==========================================
EMAIL = "your_email@example.com"
PASSWORD = "your_password"
# ==========================================

def main():
    if EMAIL == "your_email@example.com" or PASSWORD == "your_password":
        print("Please edit 'get_session.py' and replace the placeholders with your actual email and password.")
        return

    client = KinoriumClient()
    try:
        print("Authenticating...")
        client.authenticate(EMAIL, PASSWORD)
        
        auth = client.auth_cookie
        
        if not auth:
            print("\nError: Authentication succeeded but the 'auth' token was not returned.")
            return

        print("\nSuccess! Copy this token to use in your code:")
        print(auth)
        print("\nExample usage:")
        print(f'client = KinoriumClient(auth="{auth}")')
        
    except KinoriumError as e:
        print(f"\nAuthentication failed: {e}")
    except KeyboardInterrupt:
        print("\nAborted.")

if __name__ == "__main__":
    main()
