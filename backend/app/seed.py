from sqlalchemy import text

from app.auth import hash_password
from app.database import Base, SessionLocal, engine
from app.models import User, Workspace

DEMO_EMAIL = "demo@opsflow.ai"
DEMO_PASSWORD = "demo123"


def ensure_pgvector_extension() -> None:
    try:
        with engine.begin() as connection:
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        print("Ensured pgvector extension")
    except Exception as exc:
        print(f"Warning: could not create pgvector extension automatically: {exc}")


def main() -> None:
    ensure_pgvector_extension()
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == DEMO_EMAIL).first()
        if not user:
            user = User(
                email=DEMO_EMAIL,
                full_name="Demo Ops Manager",
                hashed_password=hash_password(DEMO_PASSWORD),
            )
            db.add(user)
            db.commit()
            db.refresh(user)

        workspace = db.query(Workspace).filter(Workspace.owner_id == user.id).first()
        if not workspace:
            db.add(Workspace(name="Demo Ops Workspace", owner_id=user.id))
            db.commit()

        print("Seeded demo user/workspace")
    finally:
        db.close()


if __name__ == "__main__":
    main()
