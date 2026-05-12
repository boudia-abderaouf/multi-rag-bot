import argparse
from project_bootstrap import configure_project_path

configure_project_path()

from ui_app import serve


def main():
    parser = argparse.ArgumentParser(description="Lance une UI web locale minimale pour le retrieval.")
    parser.add_argument("--host", default="127.0.0.1", help="Host d'ecoute local.")
    parser.add_argument("--port", type=int, default=8000, help="Port HTTP local.")
    args = parser.parse_args()
    serve(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
