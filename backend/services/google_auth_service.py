from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from sqlalchemy.orm import Session

from backend.models.user import User

GOOGLE_CLIENT_ID = "933212632381-f8ne172rmk8qucfprd2c1398cjhmrcsn.apps.googleusercontent.com"


class GoogleAuthService:

    @staticmethod
    def verify_google_token(token: str) -> dict:
        try:
            idinfo = id_token.verify_oauth2_token(token, google_requests.Request(), GOOGLE_CLIENT_ID)
            return idinfo
        except ValueError as e:
            raise ValueError(f"Invalid Google token: {str(e)}")

    @staticmethod
    def find_existing_user_by_email(db: Session, email: str):
        return db.query(User).filter(User.email == email).first()