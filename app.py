import streamlit as st
import uuid
import os
from livekit import api
from datetime import timedelta
import streamlit.components.v1 as components
from dotenv import load_dotenv

load_dotenv()

# Public URL detection logic:
# When deployed in headless mode (STREAMLIT_SERVER_HEADLESS=true), construct the base URL using HTTPS and the host from the Streamlit request.
# This ensures the app uses the correct public URL for sharing links in production.
# In local development, default to http://localhost:8501.
if os.getenv('STREAMLIT_SERVER_HEADLESS') == 'true':
    base_url = f"https://{st.request.host}"
else:
    base_url = "http://localhost:8501"

def generate_token_for_room(room_name):
    """
    Generates a JWT token for joining a LiveKit Cloud room with a specific room name.
    """
    api_key = os.getenv('LIVEKIT_API_KEY')
    api_secret = os.getenv('LIVEKIT_API_SECRET')
    ws_url = os.getenv('LIVEKIT_WS_URL')

    if not api_key or not api_secret:
        st.error("LIVEKIT_API_KEY and LIVEKIT_API_SECRET must be set in environment variables")
        return None

    try:
        identity = str(uuid.uuid4())
        token = api.AccessToken(api_key, api_secret)
        token.identity = identity

        grant = api.VideoGrant()
        grant.room_join = True
        grant.room = room_name
        token.video_grant = grant

        token.ttl = timedelta(hours=1)
        jwt_token = token.to_jwt()

        return {
            'identity': identity,
            'token': jwt_token,
            'ws_url': ws_url
        }
    except Exception as e:
        st.error(f"Failed to generate token: {e}")
        return None

def start_recording(room_name):
    api_key = os.getenv('LIVEKIT_API_KEY')
    api_secret = os.getenv('LIVEKIT_API_SECRET')
    if not api_key or not api_secret:
        st.error("LIVEKIT_API_KEY and LIVEKIT_API_SECRET must be set in environment variables")
        return None
    egress_svc = api.egress_service.EgressService(api_key, api_secret)
    request = api.RoomCompositeEgressRequest(room_name=room_name)
    try:
        response = egress_svc.start_egress(request)
        return response.egress_id
    except Exception as e:
        st.error(f"Failed to start recording: {e}")
        return None

def stop_recording(egress_id):
    api_key = os.getenv('LIVEKIT_API_KEY')
    api_secret = os.getenv('LIVEKIT_API_SECRET')
    if not api_key or not api_secret:
        st.error("LIVEKIT_API_KEY and LIVEKIT_API_SECRET must be set in environment variables")
        return
    egress_svc = api.egress_service.EgressService(api_key, api_secret)
    request = api.StopEgressRequest(egress_id=egress_id)
    try:
        egress_svc.stop_egress(request)
        st.success("Recording stopped successfully")
    except Exception as e:
        st.error(f"Failed to stop recording: {e}")

st.title("LiveKit Video Call App")

# Join-via-link behavior:
# Parse the URL query parameters to check for a 'room' parameter.
# If present, set the room name from the URL and flag it as coming from the URL.
# This allows users to join a specific room directly by clicking a shared link, bypassing the room creation step.
query_params = st.query_params
if 'room' in query_params:
    st.session_state.room = query_params['room']
    st.session_state.room_from_url = True

# Create Room button
if not st.session_state.get('room_from_url', False):
    if st.button("Create Room"):
        room_name = str(uuid.uuid4())
        st.session_state.room = room_name

# Display room name and shareable link if room exists
if 'room' in st.session_state:
    st.write(f"Room Name: {st.session_state.room}")
    link = f"{base_url}/?room={st.session_state.room}"
    st.write(f"Shareable Link: {link}")

    # Copy Link button using HTML component
    components.html(f"""
    <button onclick="navigator.clipboard.writeText('{link}')">Copy Link</button>
    """, height=50)

    # Join Call button
    if st.button("Join Call"):
        token_data = generate_token_for_room(st.session_state.room)
        if token_data:
            st.success("Token generated successfully. Joining the call...")
            # Embed LiveKit video call component
            html = f"""
            <div id="video-container" style="display: flex; flex-wrap: wrap;"></div>
            <button id="toggle-camera">Toggle Camera</button>
            <button id="toggle-mic">Toggle Mic</button>
            <script src="https://cdn.jsdelivr.net/npm/livekit-client@latest/dist/livekit-client.umd.js"></script>
            <script>
            const token = '{token_data['token']}';
            const wsUrl = '{token_data['ws_url']}';
            const room = new LivekitClient.Room();
            let cameraEnabled = true;
            let micEnabled = true;
            async function connect() {{
                try {{
                    await room.connect(wsUrl, token);
                    // Publish local tracks
                    try {{
                        await room.localParticipant.setCameraEnabled(cameraEnabled);
                    }} catch (error) {{
                        alert('Failed to enable camera: ' + error.message);
                        console.error('Camera enable error:', error);
                    }}
                    try {{
                        await room.localParticipant.setMicrophoneEnabled(micEnabled);
                    }} catch (error) {{
                        alert('Failed to enable microphone: ' + error.message);
                        console.error('Microphone enable error:', error);
                    }}
                    // Attach local video
                    room.localParticipant.on(LivekitClient.ParticipantEvent.TrackPublished, (track) => {{
                        if (track.source === LivekitClient.Track.Source.Camera) {{
                            const video = document.createElement('video');
                            video.id = 'local-video';
                            video.autoplay = true;
                            video.muted = true;  // Mute local video to avoid feedback
                            document.getElementById('video-container').appendChild(video);
                            track.track.attach(video);
                        }}
                    }});
                    // Handle remote participants
                    room.on(LivekitClient.RoomEvent.ParticipantConnected, (participant) => {{
                        addParticipantVideo(participant);
                    }});
                    room.participants.forEach(addParticipantVideo);
                }} catch (error) {{
                    alert('Failed to connect to room: ' + error.message);
                    console.error('Failed to connect:', error);
                }}
            }}
            function addParticipantVideo(participant) {{
                participant.on(LivekitClient.ParticipantEvent.TrackSubscribed, (track) => {{
                    if (track.source === LivekitClient.Track.Source.Camera) {{
                        const video = document.createElement('video');
                        video.id = `video-${{participant.identity}}`;
                        video.autoplay = true;
                        document.getElementById('video-container').appendChild(video);
                        track.track.attach(video);
                    }}
                }});
            }}
            document.getElementById('toggle-camera').addEventListener('click', async () => {{
                cameraEnabled = !cameraEnabled;
                try {{
                    await room.localParticipant.setCameraEnabled(cameraEnabled);
                }} catch (error) {{
                    alert('Failed to toggle camera: ' + error.message);
                    console.error('Toggle camera error:', error);
                    cameraEnabled = !cameraEnabled;  // Revert on error
                }}
            }});
            document.getElementById('toggle-mic').addEventListener('click', async () => {{
                micEnabled = !micEnabled;
                try {{
                    await room.localParticipant.setMicrophoneEnabled(micEnabled);
                }} catch (error) {{
                    alert('Failed to toggle microphone: ' + error.message);
                    console.error('Toggle microphone error:', error);
                    micEnabled = !micEnabled;  // Revert on error
                }}
            }});
            connect();
            </script>
            """
            components.html(html, height=600)

    # Start Recording button
    if st.button("Start Recording"):
        if 'egress_id' in st.session_state:
            st.warning("Recording already in progress")
        else:
            egress_id = start_recording(st.session_state.room)
            if egress_id:
                st.session_state.egress_id = egress_id
                st.success("Recording started successfully")

    # Stop Recording button
    if st.button("Stop Recording"):
        if 'egress_id' in st.session_state:
            stop_recording(st.session_state.egress_id)
            del st.session_state.egress_id
        else:
            st.warning("No recording in progress")

# Recording Information
st.markdown("### Recording Storage and Access")
st.markdown("""
Recordings created via LiveKit Egress are stored in **LiveKit Cloud**.

- **Storage Location**: Recordings are uploaded to the cloud storage configured for your LiveKit project (e.g., AWS S3, Google Cloud Storage, or Azure Blob Storage).
- **Access Methods**:
  - **Dashboard**: Log in to your LiveKit Cloud dashboard at [cloud.livekit.io](https://cloud.livekit.io) to view and download recordings.
  - **API**: Use the LiveKit API to list and retrieve egress information, including download URLs for completed recordings.
  - **Webhooks**: Configure webhooks to receive notifications when recordings are complete, including metadata and access links.

Note: Ensure your LiveKit project has egress enabled and storage configured in the dashboard.
""")