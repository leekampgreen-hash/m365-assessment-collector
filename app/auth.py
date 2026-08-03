"""Authentication smoke test. Run with: python auth.py"""

from main import GraphClient


if __name__ == "__main__":
    GraphClient()._token()
    print("Authentication Success")
