from fastapi import FastAPI

app = FastAPI(
    title="Production Navigator API",
    version="0.1.0",
)

@app.get("/health", tags=["Health"])
def health() -> dict[str, str]:
    return {"status": "ok"}

def main():
    health


if __name__ == "__main__":
    main()
