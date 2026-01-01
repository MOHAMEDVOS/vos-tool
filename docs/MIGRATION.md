# Backend/Frontend Separation Migration Guide

## Overview

The application has been separated into:
- **Backend**: FastAPI REST API (port 8000)
- **Frontend**: Streamlit UI (port 8501)

## What Has Been Implemented

### Backend (FastAPI)
✅ Complete backend structure with:
- Authentication API (`/api/auth/`) - JWT-based authentication
- Audio Processing API (`/api/audio/`) - File upload and processing
- Dashboard API (`/api/dashboard/`) - Audit data retrieval
- Settings API (`/api/settings/`) - User management
- ReadyMode API (`/api/readymode/`) - Call downloading

### Frontend (Streamlit)
✅ API client created (`frontend/api_client.py`)
✅ Authentication module updated to use API
⚠️ Main app.py still needs full migration

## Next Steps to Complete Migration

### 1. Update Login Function in app.py

Replace the login logic in `show_login_page()` function:

```python
# OLD (lines ~385-417):
if user_manager.verify_user_password(username, password):
    # ... session creation logic

# NEW:
from frontend.api_client import get_api_client

api_client = get_api_client()
try:
    result = api_client.login(username, password)
    st.success(f"Welcome, {username}! Loading platform...")
    st.rerun()
except Exception as e:
    st.error(f"Login failed: {str(e)}")
```

### 2. Update Dashboard Components

Update `app_ai/ui/components.py` to use API client:

```python
from frontend.api_client import get_api_client

def show_agent_audit_dashboard():
    api_client = get_api_client()
    
    # Get data from API instead of direct call
    data = api_client.get_agent_audits(
        start_date=start_date,
        end_date=end_date,
        agent_name=agent_name
    )
    # ... display data
```

### 3. Update Audio Processing

Update audit section to use API:

```python
# Upload file
file_info = api_client.upload_audio(file_content, filename)

# Start processing
job = api_client.process_audio(file_info["file_id"], audit_type="heavy")

# Poll for status
status = api_client.get_processing_status(job["job_id"])

# Get results when complete
results = api_client.get_processing_results(job["job_id"])
```

### 4. Update Settings Section

Replace direct user_manager calls with API calls:

```python
# Get users
users = api_client.list_users()

# Create user
api_client.create_user(user_data)

# Update user
api_client.update_user(username, user_data)
```

## Testing

1. Start backend:
   ```bash
   cd backend
   uvicorn backend.main:app --reload
   ```

2. Start frontend:
   ```bash
   export BACKEND_URL=http://localhost:8000
   streamlit run app.py
   ```

3. Test endpoints:
   - Visit http://localhost:8000/docs for API documentation
   - Test login flow
   - Test dashboard data loading
   - Test audio upload/processing

## Environment Variables

### Backend
```env
SECRET_KEY=your-secret-key
JWT_SECRET=your-jwt-secret
POSTGRES_HOST=localhost
POSTGRES_DB=vos_tool
POSTGRES_USER=vos_user
POSTGRES_PASSWORD=your-password
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000
FRONTEND_URL=http://localhost:8501
```

### Frontend
```env
BACKEND_URL=http://localhost:8000
```

## Docker Deployment

```bash
docker-compose up
```

This starts both services with proper networking.

## Notes

- The backend uses JWT tokens for authentication
- Session management is handled by the backend
- All database operations go through the backend API
- File uploads are handled by the backend
- The frontend is now stateless (except for token storage)

## Troubleshooting

### CORS Errors
- Ensure `FRONTEND_URL` in backend matches your frontend URL
- Check CORS_ORIGINS in `backend/core/config.py`

### Authentication Issues
- Verify JWT_SECRET is set in backend
- Check token is being stored in session_state
- Verify backend is accessible from frontend

### Database Connection
- Ensure PostgreSQL is running
- Check database credentials in environment variables
- Verify database schema is initialized

