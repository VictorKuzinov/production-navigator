import asyncio

import httpx

from app.core.config import settings


async def req_fns(inn: str) -> int:
    params = {
        "req": inn,
        "key": settings.api_fns_key,
    }

    async with httpx.AsyncClient() as client:
        response = await client.get(
            settings.url_fns,
            params=params,
        )

    response.raise_for_status()
    return response.json()

async def main():
    result = await req_fns("6673240060")
    print(f"Starting server...{result}")



if __name__ == "__main__":
    asyncio.run(main())