from src.frontend.app import build_ui


def main() -> None:
    build_ui().launch(server_name="0.0.0.0", server_port=7860)


if __name__ == "__main__":
    main()
