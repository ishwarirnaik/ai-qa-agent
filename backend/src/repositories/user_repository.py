from src.api.database import DatabaseManager


class UserRepository:
    def create_user(self, email: str, password: str) -> bool:
        return DatabaseManager.create_user(email, password)

    def verify_user(self, email: str, password: str) -> bool:
        return DatabaseManager.verify_user(email, password)

