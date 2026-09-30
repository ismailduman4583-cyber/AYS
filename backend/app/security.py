from datetime import datetime, timedelta, timezone
import jwt
from pwdlib import PasswordHash
from .config import settings

ph = PasswordHash.recommended()

def verify_password(plain, hashed): return ph.verify(plain, hashed)
def hash_password(plain): return ph.hash(plain)
def create_token(user_id: str):
    exp=datetime.now(timezone.utc)+timedelta(minutes=settings.jwt_expire_minutes)
    return jwt.encode({'sub':user_id,'exp':exp},settings.jwt_secret,algorithm='HS256')
