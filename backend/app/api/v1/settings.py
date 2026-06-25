import os
import time
import hmac
import hashlib
import base64
import json
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Header, Request
from pydantic import BaseModel, Field
from backend.app.config.settings import settings
from backend.app.services.scanner import _get_redis
from backend.scripts.login_fyers import generate_fyers_login_url
from backend.app.core.crypto import encrypt_str
import logging

logger = logging.getLogger("nse_scanner.settings")

router = APIRouter()

# In-memory attempts tracker (fallback if Redis is down)
_local_attempts = {}

def is_locked_out(ip: str) -> bool:
    # Try Redis
    redis_client = _get_redis()
    if redis_client:
        try:
            key = f"settings_login_attempts:{ip}"
            val = redis_client.get(key)
            if val and int(val) >= 5:
                return True
            return False
        except:
            pass
            
    # Fallback to in-memory
    now = time.time()
    if ip in _local_attempts:
        # Keep failures only within the last 15 minutes
        _local_attempts[ip] = [t for t in _local_attempts[ip] if now - t < 900]
        if len(_local_attempts[ip]) >= 5:
            return True
    return False

def register_failed_attempt(ip: str):
    # Try Redis
    redis_client = _get_redis()
    if redis_client:
        try:
            key = f"settings_login_attempts:{ip}"
            val = redis_client.get(key)
            if not val:
                redis_client.setex(key, 900, 1)  # 15 minutes TTL
            else:
                redis_client.incr(key)
            return
        except:
            pass
            
    # Fallback to in-memory
    now = time.time()
    if ip not in _local_attempts:
        _local_attempts[ip] = []
    _local_attempts[ip].append(now)

def clear_failed_attempts(ip: str):
    # Try Redis
    redis_client = _get_redis()
    if redis_client:
        try:
            key = f"settings_login_attempts:{ip}"
            redis_client.delete(key)
        except:
            pass
    if ip in _local_attempts:
        del _local_attempts[ip]


# Token generation and validation
def generate_session_token(expiry_minutes=30) -> str:
    expiry_time = int(time.time()) + (expiry_minutes * 60)
    msg = f"{expiry_time}"
    sig = hmac.new(settings.SECRET_KEY.encode(), msg.encode(), hashlib.sha256).hexdigest()
    token = f"{expiry_time}:{sig}"
    return base64.b64encode(token.encode()).decode()

def verify_session_token(token_str: str) -> bool:
    try:
        decoded = base64.b64decode(token_str.encode()).decode()
        expiry_time_str, sig = decoded.split(":")
        expiry_time = int(expiry_time_str)
        if time.time() > expiry_time:
            return False
        expected_sig = hmac.new(settings.SECRET_KEY.encode(), expiry_time_str.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(sig, expected_sig)
    except:
        return False

def get_current_session(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid session token.")
    
    token = authorization.split(" ")[1]
    if not verify_session_token(token):
        raise HTTPException(status_code=401, detail="Session expired or invalid token. Please log in again.")
    return token


# API Schemas
class UnlockRequest(BaseModel):
    pin: str

class UnlockResponse(BaseModel):
    token: str

class FyersConfigRequest(BaseModel):
    app_id: str
    secret_id: str
    redirect_uri: str

class FyersConfigResponse(BaseModel):
    app_id_masked: str
    redirect_uri: str
    authenticated: bool


# Endpoints
@router.post("/unlock", response_model=UnlockResponse)
def unlock_settings(payload: UnlockRequest, request: Request):
    """
    Validates settings access PIN and issues short-lived session token on success.
    Rate limited to 5 failed attempts per 15 minutes per IP.
    """
    client_ip = request.client.host if request.client else "unknown_ip"
    
    if is_locked_out(client_ip):
        raise HTTPException(status_code=429, detail="Too many failed attempts. Try again later.")
        
    if hmac.compare_digest(payload.pin.encode('utf-8'), settings.SETTINGS_PIN.encode('utf-8')):
        clear_failed_attempts(client_ip)
        token = generate_session_token(expiry_minutes=30)
        return {"token": token}
    else:
        register_failed_attempt(client_ip)
        # Return generic error; don't specify remaining attempts
        raise HTTPException(status_code=401, detail="Invalid settings PIN.")

@router.get("/fyers-config", response_model=FyersConfigResponse)
def get_fyers_config(session: str = Depends(get_current_session)):
    """
    Returns masked App ID, Redirect URI, and connection status.
    """
    app_id = settings.FYERS_APP_ID
    
    # Mask App ID (reveal only first 3 and last 4 characters if long enough)
    masked_app_id = "Not Configured"
    if app_id:
        if len(app_id) > 7:
            masked_app_id = f"{app_id[:3]}***{app_id[-4:]}"
        else:
            masked_app_id = "***"
            
    token_exists = os.path.exists(settings.token_path)
    
    return {
        "app_id_masked": masked_app_id,
        "redirect_uri": settings.FYERS_REDIRECT_URI,
        "authenticated": token_exists
    }

@router.post("/fyers-config")
def update_fyers_config(payload: FyersConfigRequest, session: str = Depends(get_current_session)):
    """
    Save Fyers credentials to data/fyers_config.json.
    """
    try:
        config_data = {
            "app_id": payload.app_id.strip(),
            "secret_id": encrypt_str(payload.secret_id.strip()),
            "redirect_uri": payload.redirect_uri.strip()
        }
        
        # Write to JSON file
        settings.config_path.write_text(json.dumps(config_data, indent=4))
        
        # Force reload values into the settings instance
        # Since settings uses @property to read dynamically, it updates immediately!
        return {"status": "success", "message": "Fyers configuration saved successfully."}
    except Exception as e:
        logger.error(f"Failed to save Fyers configuration: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to save Fyers configuration. Check server logs.")

@router.get("/login-url")
def get_settings_login_url(session: str = Depends(get_current_session)):
    """
    Generates OAuth2 login URL based on dynamically configured App ID & Redirect URI.
    """
    app_id = settings.FYERS_APP_ID
    redirect_uri = settings.FYERS_REDIRECT_URI
    
    if not app_id or not redirect_uri:
        raise HTTPException(status_code=400, detail="Fyers app_id or redirect_uri is not configured.")
        
    url = generate_fyers_login_url(app_id, redirect_uri)
    return {"login_url": url}
