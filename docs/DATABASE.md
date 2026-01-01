# Database Setup Documentation

## Database Included in Backend/Frontend Separation

Yes, the database is **fully included** in the separation plan. Here's what's set up:

## Database Components

### 1. PostgreSQL Service
- **Service**: Included in `docker-compose.yml`
- **Port**: 5432
- **Image**: postgres:15-alpine
- **Persistent Storage**: Volume `postgres_data`

### 2. Database Schema
The `cloud-migration/init.sql` file contains the complete schema:

#### Core Tables:
- **users** - User accounts and authentication
- **user_sessions** - Active user sessions
- **audit_logs** - System audit trail

#### Data Tables:
- **call_recordings** - Metadata for uploaded audio files
- **analysis_results** - Analysis results linked to recordings
- **agent_audit_results** - Agent audit data
- **lite_audit_results** - Lite audit data
- **campaign_audit_results** - Campaign audit summaries
- **quota_usage** - Daily quota tracking

#### Features:
- UUID primary keys
- JSONB columns for flexible metadata
- Indexes for performance
- Triggers for automatic timestamp updates
- PostgreSQL extensions (uuid-ossp, pg_trgm)

### 3. Backend Integration
- **Connection**: `backend/core/database.py` uses existing `lib/database.py`
- **Initialization**: Database connection tested on backend startup
- **Services**: All backend services access database through existing managers

### 4. Automatic Schema Creation
When PostgreSQL starts for the first time:
1. Docker mounts `init.sql` to `/docker-entrypoint-initdb.d/`
2. PostgreSQL automatically executes all `.sql` files in that directory
3. Schema is created automatically

## Database Configuration

### Environment Variables (Backend)
```env
DB_TYPE=postgresql
POSTGRES_HOST=postgres  # Service name in Docker
POSTGRES_PORT=5432
POSTGRES_DB=vos_tool
POSTGRES_USER=vos_user
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
```

### Connection String
The backend uses the existing `DatabaseManager` from `lib/database.py` which:
- Supports connection pooling
- Handles both PostgreSQL and SQLite (for development)
- Provides unified query interface

## Database Access

### From Backend
All database access goes through:
- `lib/database.py` - DatabaseManager class
- `lib/dashboard_manager.py` - DashboardManager, UserManager, SessionManager
- Backend services use these existing managers

### From Frontend
**No direct database access** - Frontend only communicates with backend API

## Migration Notes

The database schema is backward compatible with existing code:
- Existing `dashboard_manager` methods work unchanged
- JSON fallback still available if database unavailable
- All existing queries and operations supported

## Verification

To verify database setup:

1. **Check PostgreSQL is running**:
   ```bash
   docker-compose ps postgres
   ```

2. **Check schema exists**:
   ```bash
   docker-compose exec postgres psql -U vos_user -d vos_tool -c "\dt"
   ```

3. **Check backend connection**:
   - Backend logs should show "Database connection established" on startup
   - Visit http://localhost:8000/health to verify backend is running

## Troubleshooting

### Database not initializing
- Check PostgreSQL logs: `docker-compose logs postgres`
- Verify `init.sql` is mounted correctly
- Check file permissions

### Connection errors
- Verify environment variables are set
- Check network connectivity between backend and postgres services
- Ensure PostgreSQL is fully started before backend (use `depends_on`)

### Schema missing tables
- Drop and recreate database volume: `docker-compose down -v`
- Restart services: `docker-compose up`

