import os
import uuid
from livekit import api
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

def generate_token():
    """
    Generates a JWT token for joining a LiveKit Cloud room.
    Uses dynamic room name and random user identity.
    """
    # Retrieve environment variables
    api_key = os.getenv('LIVEKIT_API_KEY')
    api_secret = os.getenv('LIVEKIT_API_SECRET')
    ws_url = os.getenv('LIVEKIT_WS_URL')  # For client connection (not used in token generation)

    if not api_key or not api_secret:
        raise ValueError("LIVEKIT_API_KEY and LIVEKIT_API_SECRET must be set in environment variables")

    # Generate dynamic room name
    room_name = str(uuid.uuid4())

    # Generate random user identity
    identity = str(uuid.uuid4())

    # Create AccessToken
    token = api.AccessToken(api_key, api_secret)
    token.identity = identity

    # Set video grant for room join
    grant = api.VideoGrant()
    grant.room_join = True
    grant.room = room_name
    token.video_grant = grant

    # Set token expiry
    token.ttl = timedelta(hours=1)

    # Generate JWT
    jwt_token = token.to_jwt()

    return {
        'room_name': room_name,
        'identity': identity,
        'token': jwt_token,
        'ws_url': ws_url
    }

if __name__ == "__main__":
    result = generate_token()
    print(f"Room Name: {result['room_name']}")
    print(f"Identity: {result['identity']}")
    print(f"Token: {result['token']}")
    print(f"WS URL: {result['ws_url']}")