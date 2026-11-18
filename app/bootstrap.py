from argon2 import PasswordHasher
from sqlalchemy import select

from app.config import settings
from app.db import transaction
from app.models import Account, Policy


def main():
    with transaction() as session:
        if not session.scalar(select(Account).limit(1)):
            password = settings().admin_password
            if len(password) < 16:
                raise ValueError("ADMIN_PASSWORD must contain at least 16 characters")
            session.add(
                Account(
                    username="admin",
                    password_hash=PasswordHasher().hash(password),
                    role="admin",
                    originals=True,
                )
            )
        if not session.scalar(select(Policy).limit(1)):
            session.add(Policy(name="Высокий риск — проверка аналитиком", conditions={"min_risk": 60}))


if __name__ == "__main__":
    main()
