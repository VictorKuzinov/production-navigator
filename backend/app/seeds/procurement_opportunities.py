import asyncio
import json
from pathlib import Path

from app.db.database import AsyncSessionLocal
from app.repositories.materials import MaterialRepository
from app.repositories.procurement_opportunities import (
    ProcurementOpportunityRepository,
)
from app.repositories.references import ReferenceRepository
from app.schemas.procurement_opportunities import PreparedOpportunityDocument
from app.services.procurement_opportunities import (
    ProcurementOpportunityIngestionService,
)

BUNDLED_FIXTURE_PATH = Path(__file__).with_name("procurement_opportunities.json")


def load_bundled_document(
    path: Path = BUNDLED_FIXTURE_PATH,
) -> PreparedOpportunityDocument:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return PreparedOpportunityDocument.model_validate(payload)


async def main() -> None:
    document = load_bundled_document()
    async with AsyncSessionLocal() as session:
        service = ProcurementOpportunityIngestionService(
            session=session,
            opportunity_repository=ProcurementOpportunityRepository(session),
            reference_repository=ReferenceRepository(session),
            material_repository=MaterialRepository(session),
        )
        result = await service.ingest_batch(document.opportunities)
    print(json.dumps(result.model_dump(), sort_keys=True))


if __name__ == "__main__":
    asyncio.run(main())
