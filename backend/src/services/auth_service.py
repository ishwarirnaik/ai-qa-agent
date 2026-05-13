from src.repositories.user_repository import UserRepository


class AuthService:
    def __init__(self, user_repository: UserRepository | None = None):
        self.user_repository = user_repository or UserRepository()

    def login(self, email: str, password: str) -> bool:
        return self.user_repository.verify_user(email, password)

    def signup(self, email: str, password: str) -> bool:
        return self.user_repository.create_user(email, password)

