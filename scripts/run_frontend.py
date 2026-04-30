import uvicorn


def main() -> None:
    uvicorn.run("src.api.app:app", host="0.0.0.0", port=7860, reload=False)


if __name__ == "__main__":
    main()
