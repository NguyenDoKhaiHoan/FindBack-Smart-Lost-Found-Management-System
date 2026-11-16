from alembic.config import Config
from sqlalchemy import inspect, select

from alembic import command
from app.core.config import BACKEND_DIR
from app.modules.claims_returns.models.claim import Claim, ClaimEvidence, ReturnRecord
from app.modules.posts.models.post import Post
from tests.decision_helpers import legacy_return, pending


def test_upgrade_downgrade_with_existing_referencing_data_preserves_records(world):
    claim_id = pending(world)
    legacy_return(world, claim_id, "ARRANGED")
    schema = None if world.engine.dialect.name == "sqlite" else world.settings.database_schema
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.attributes["schema"] = schema
    with world.engine.connect() as connection:
        config.attributes["connection"] = connection
        command.downgrade(config, "0001_claims_api")
        assert "completed_claim_id" not in {
            c["name"] for c in inspect(connection).get_columns("posts", schema=schema)
        }
        command.upgrade(config, "head")
        if world.engine.dialect.name == "sqlite":
            assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1
    with world.factory() as session:
        assert session.get(Claim, claim_id).status == "PENDING"
        assert session.get(Post, world.ids["found"]).completed_claim_id is None
        assert (
            session.scalar(select(ClaimEvidence)).private_content
            == "Fictional secret marking DEMO-123"
        )
        assert session.scalar(select(ReturnRecord)).status == "ARRANGED"
