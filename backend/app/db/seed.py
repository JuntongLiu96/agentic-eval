import json
from pathlib import Path

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.scorer_template import ScorerTemplate

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"


async def seed_scorer_templates(db: AsyncSession) -> None:
    """Load built-in scorer templates from YAML files. Updates existing templates by name."""
    for yaml_file in sorted(TEMPLATES_DIR.glob("*.yaml")):
        with open(yaml_file) as f:
            data = yaml.safe_load(f)

        # Check if template with this name already exists
        result = await db.execute(
            select(ScorerTemplate).where(ScorerTemplate.name == data["name"])
        )
        existing = result.scalars().first()

        if existing:
            # Update existing template
            existing.description = data["description"]
            existing.category = data["category"]
            existing.template_prompt = data["template_prompt"]
            existing.example_scorer = json.dumps(data["example_scorer"])
            existing.usage_instructions = data["usage_instructions"]
        else:
            # Create new template
            template = ScorerTemplate(
                name=data["name"],
                description=data["description"],
                category=data["category"],
                template_prompt=data["template_prompt"],
                example_scorer=json.dumps(data["example_scorer"]),
                usage_instructions=data["usage_instructions"],
            )
            db.add(template)

    await db.commit()
