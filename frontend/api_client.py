"""
API Client for communicating with the backend FastAPI service.
"""

import requests
from typing import Optional, Dict, Any, List
from datetime import date
import streamlit as st
import logging

logger = logging.getLogger(__name__)


class APIClient:
    """Client for backend API communication."""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        """Initialize API client.
        
        Args:
            base_url: Base URL of the backend API
        """
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
    
    def _get_headers(self) -> Dict[str, str]:
        """Get request headers with authentication token."""
        headers = {"Content-Type": "application/json"}
        
        # Get token from session state
        token = st.session_state.get("access_token")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        
        return headers
    
    def _handle_response(self, response: requests.Response) -> Dict[str, Any]:
        """Handle API response."""
        try:
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            if response.status_code == 401:
                # Unauthorized - clear session
                if "access_token" in st.session_state:
                    del st.session_state["access_token"]
                if "authenticated" in st.session_state:
                    del st.session_state["authenticated"]
            logger.error(f"API error: {e}")
            raise
        except Exception as e:
            logger.error(f"API request error: {e}")
            raise
    
    # Authentication endpoints
    def login(self, username: str, password: str) -> Dict[str, Any]:
        """Login and get access token."""
        response = self.session.post(
            f"{self.base_url}/api/auth/login",
            json={"username": username, "password": password}
        )
        result = self._handle_response(response)
        
        # Store token in session state
        st.session_state["access_token"] = result["access_token"]
        st.session_state["authenticated"] = True
        st.session_state["username"] = result["username"]
        st.session_state["role"] = result["role"]
        st.session_state["session_id"] = result["session_id"]
        
        return result
    
    def logout(self) -> Dict[str, Any]:
        """Logout current user."""
        try:
            response = self.session.post(
                f"{self.base_url}/api/auth/logout",
                headers=self._get_headers()
            )
            result = self._handle_response(response)
        finally:
            # Clear session state
            for key in ["access_token", "authenticated", "username", "role", "session_id"]:
                if key in st.session_state:
                    del st.session_state[key]
        
        return result
    
    def get_current_user(self) -> Dict[str, Any]:
        """Get current user information."""
        response = self.session.get(
            f"{self.base_url}/api/auth/me",
            headers=self._get_headers()
        )
        return self._handle_response(response)
    
    def check_session(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        """Check if session is valid.
        
        Args:
            session_id: Optional session ID to validate. If provided, validates the specific session.
                       If None, checks if any active session exists (for backwards compatibility).
        """
        params = {}
        if session_id:
            params["session_id"] = session_id
        
        response = self.session.get(
            f"{self.base_url}/api/auth/session",
            headers=self._get_headers(),
            params=params if params else None
        )
        return self._handle_response(response)
    
    # Audio processing endpoints
    def upload_audio(self, file_content: bytes, filename: str) -> Dict[str, Any]:
        """Upload audio file."""
        files = {"file": (filename, file_content)}
        headers = {}
        token = st.session_state.get("access_token")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        
        response = self.session.post(
            f"{self.base_url}/api/audio/upload",
            files=files,
            headers=headers
        )
        return self._handle_response(response)
    
    def process_audio(
        self,
        file_id: str,
        audit_type: str = "heavy",
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Start audio processing."""
        response = self.session.post(
            f"{self.base_url}/api/audio/process",
            json={
                "file_id": file_id,
                "audit_type": audit_type,
                "options": options or {}
            },
            headers=self._get_headers()
        )
        return self._handle_response(response)
    
    def get_processing_status(self, job_id: str) -> Dict[str, Any]:
        """Get processing job status."""
        response = self.session.get(
            f"{self.base_url}/api/audio/status/{job_id}",
            headers=self._get_headers()
        )
        return self._handle_response(response)
    
    def get_processing_results(self, job_id: str) -> Dict[str, Any]:
        """Get processing job results."""
        response = self.session.get(
            f"{self.base_url}/api/audio/results/{job_id}",
            headers=self._get_headers()
        )
        return self._handle_response(response)
    
    # Dashboard endpoints
    def get_agent_audits(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        agent_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get agent audit data."""
        params = {}
        if start_date:
            params["start_date"] = start_date.isoformat()
        if end_date:
            params["end_date"] = end_date.isoformat()
        if agent_name:
            params["agent_name"] = agent_name
        
        response = self.session.get(
            f"{self.base_url}/api/dashboard/agent-audits",
            params=params,
            headers=self._get_headers()
        )
        return self._handle_response(response)
    
    def get_lite_audits(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> Dict[str, Any]:
        """Get lite audit data."""
        params = {}
        if start_date:
            params["start_date"] = start_date.isoformat()
        if end_date:
            params["end_date"] = end_date.isoformat()
        
        response = self.session.get(
            f"{self.base_url}/api/dashboard/lite-audits",
            params=params,
            headers=self._get_headers()
        )
        return self._handle_response(response)
    
    def get_campaign_audits(
        self,
        campaign: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> Dict[str, Any]:
        """Get campaign audit data."""
        params = {}
        if campaign:
            params["campaign"] = campaign
        if start_date:
            params["start_date"] = start_date.isoformat()
        if end_date:
            params["end_date"] = end_date.isoformat()
        
        response = self.session.get(
            f"{self.base_url}/api/dashboard/campaign-audits",
            params=params,
            headers=self._get_headers()
        )
        return self._handle_response(response)
    
    def get_campaigns(self) -> List[str]:
        """Get list of available campaigns."""
        response = self.session.get(
            f"{self.base_url}/api/dashboard/campaigns",
            headers=self._get_headers()
        )
        return self._handle_response(response)
    
    def clear_agent_audits(self) -> Dict[str, Any]:
        """Clear agent audit data."""
        response = self.session.post(
            f"{self.base_url}/api/dashboard/clear/agent-audits",
            headers=self._get_headers()
        )
        return self._handle_response(response)
    
    def clear_lite_audits(self) -> Dict[str, Any]:
        """Clear lite audit data."""
        response = self.session.post(
            f"{self.base_url}/api/dashboard/clear/lite-audits",
            headers=self._get_headers()
        )
        return self._handle_response(response)
    
    def clear_campaign_audits(self, campaign: Optional[str] = None) -> Dict[str, Any]:
        """Clear campaign audit data."""
        params = {}
        if campaign:
            params["campaign"] = campaign
        
        response = self.session.post(
            f"{self.base_url}/api/dashboard/clear/campaign-audits",
            params=params,
            headers=self._get_headers()
        )
        return self._handle_response(response)
    
    # Settings endpoints
    def get_settings(self) -> Dict[str, Any]:
        """Get user settings."""
        response = self.session.get(
            f"{self.base_url}/api/settings/",
            headers=self._get_headers()
        )
        return self._handle_response(response)
    
    def update_settings(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        """Update user settings."""
        response = self.session.put(
            f"{self.base_url}/api/settings/",
            json=settings,
            headers=self._get_headers()
        )
        return self._handle_response(response)

    # AssemblyAI API key endpoints
    def get_assemblyai_key_status(self) -> Dict[str, Any]:
        """Check if the current user has an AssemblyAI API key set."""
        response = self.session.get(
            f"{self.base_url}/api/settings/assemblyai-key",
            headers=self._get_headers(),
        )
        return self._handle_response(response)

    def update_assemblyai_key(self, api_key: str) -> Dict[str, Any]:
        """Set or update the current user's AssemblyAI API key.

        Pass an empty string to clear the key.
        """
        payload = {"api_key": api_key}
        response = self.session.put(
            f"{self.base_url}/api/settings/assemblyai-key",
            json=payload,
            headers=self._get_headers(),
        )
        return self._handle_response(response)
    
    def list_users(self) -> Dict[str, Any]:
        """List all users (admin only)."""
        response = self.session.get(
            f"{self.base_url}/api/settings/users",
            headers=self._get_headers()
        )
        return self._handle_response(response)
    
    def create_user(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create new user (admin only)."""
        response = self.session.post(
            f"{self.base_url}/api/settings/users",
            json=user_data,
            headers=self._get_headers()
        )
        return self._handle_response(response)
    
    def update_user(self, username: str, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update user (owner only)."""
        response = self.session.put(
            f"{self.base_url}/api/settings/users/{username}",
            json=user_data,
            headers=self._get_headers()
        )
        return self._handle_response(response)
    
    def delete_user(self, username: str) -> Dict[str, Any]:
        """Delete user (owner only)."""
        response = self.session.delete(
            f"{self.base_url}/api/settings/users/{username}",
            headers=self._get_headers()
        )
        return self._handle_response(response)
    
    # ReadyMode endpoints
    def download_readymode_calls(
        self,
        dialer_url: Optional[str] = None,
        max_calls: Optional[int] = None
    ) -> Dict[str, Any]:
        """Download calls from ReadyMode."""
        response = self.session.post(
            f"{self.base_url}/api/readymode/download",
            json={
                "dialer_url": dialer_url,
                "max_calls": max_calls
            },
            headers=self._get_headers()
        )
        return self._handle_response(response)
    
    def get_readymode_status(self) -> Dict[str, Any]:
        """Get ReadyMode status."""
        response = self.session.get(
            f"{self.base_url}/api/readymode/status",
            headers=self._get_headers()
        )
        return self._handle_response(response)


# Global API client instance
_api_client: Optional[APIClient] = None


def get_api_client() -> APIClient:
    """Get or create API client instance."""
    global _api_client
    if _api_client is None:
        import os
        base_url = os.getenv("BACKEND_URL", "http://localhost:8000")
        _api_client = APIClient(base_url)
    return _api_client

