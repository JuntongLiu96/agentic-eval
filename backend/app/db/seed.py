import json
from pathlib import Path

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.scorer_template import ScorerTemplate

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"


async def seed_scorer_templates(db: AsyncSession) -> None:
    """Load built-in scorer templates from YAML files if not already seeded."""
    result = await db.execute(select(ScorerTemplate))
    if result.scalars().first() is not None:
        return  # Already seeded

    for yaml_file in sorted(TEMPLATES_DIR.glob("*.yaml")):
        with open(yaml_file) as f:
            data = yaml.safe_load(f)

        template = ScorerTemplate(
            name=data["name"],
            description=data["description"],
            category=data["category"],
            template_prompt=data["template_prompt"],
            output_format=data["output_format"],
            example_scorer=json.dumps(data["example_scorer"]),
            usage_instructions=data["usage_instructions"],
        )
        db.add(template)

    await db.commit()
