from fastapi import (
    HTTPException,
    Request,
    status,
)

import secrets
import yaml

# Load config
def load_config(config_file='config.yml'):
    with open(config_file, 'r') as file:
        return yaml.safe_load(file)

config = load_config()

# Generate a secure secret key if not in config
if 'secret_key' not in config['server']:
    config['server']['secret_key'] = secrets.token_urlsafe(32)
    with open('config.yml', 'w') as file:
        yaml.dump(config, file)

SECRET_KEY = config['server']['secret_key']

def verify_session(request: Request) -> bool:
    """Verify that the request comes from our frontend session."""
    session = request.session
    return session.get('authenticated', False)

async def verify_frontend_request(request: Request) -> bool:
    """Dependency to verify frontend requests."""
    if not verify_session(request):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    return True

def init_session(request: Request) -> None:
    """Initialize a new frontend session."""
    request.session['authenticated'] = True 