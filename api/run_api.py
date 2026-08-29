"""Application entrypoint for the read-only Operations Analytics API."""
from .operations import create_server


def main() -> None:
    create_server().serve_forever()


if __name__ == "__main__":
    main()
