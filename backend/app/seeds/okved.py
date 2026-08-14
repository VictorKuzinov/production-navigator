import asyncio
import csv

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import AsyncSessionLocal
from app.models.okved import OKVED


def get_level(code: str) -> int:
    if code.isalpha():
        return 0

    return code.count(".") + 1


def get_parent_code(code: str) -> str | None:
    if code.isalpha():
        return None

    if "." not in code:
        return None

    return code.rsplit(".", 1)[0]


async def seed_okved(
        session: AsyncSession,
) -> None:

    with open(
        "app/seeds/okved.csv",
        encoding="utf-8",
    ) as file:

        reader = csv.reader(
            file,
            delimiter=";",
        )

        for row in reader:
            if len(row) != 3:
                continue
            
            section, code, name = row

            name = name.strip()
            code = code.strip()

            if not code:
                code = section.strip()

            result = await session.execute(
                select(OKVED).where(
                    OKVED.code == code
                )
            )

            existing = result.scalar_one_or_none()

            values = {
                "code": code,
                "name_ru": name.strip(),
                "parent_code": get_parent_code(code),
                "level": get_level(code),
            }

            if existing is None:
                session.add(
                    OKVED(**values)
                )
            else:
                existing.name_ru = values["name_ru"]
                existing.parent_code = values["parent_code"]
                existing.level = values["level"]

    await session.commit()


async def main():
    async with AsyncSessionLocal() as session:
        await seed_okved(session)


if __name__ == "__main__":
    asyncio.run(main())