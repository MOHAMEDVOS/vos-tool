# Environment Variables Reference

Complete list of all environment variables used by VOS Tool.

## Required Variables

These must be set for the application to function:

| Variable | Description | Example |
|----------|-------------|---------|
| `POSTGRES_PASSWORD` | PostgreSQL database password | `secure_password_123` |
| `SECRET_KEY` | Application secret key for encryption | Generate with: `python -c "import secrets; print(secrets.token_urlsafe(32))"` |
| `JWT_SECRET` | JWT token signing secret | Generate with: `python -c "import secrets; print(secrets.token_urlsafe(32))"` |
| `ASSEMBLYAI_API_KEY` | AssemblyAI API key for transcription | Get from https://www.assemblyai.com/ |

## Database Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `POSTGRES_HOST` | PostgreSQL host address | `localhost` |
| `POSTGRES_PORT` | PostgreSQL port | `5432` |
| `POSTGRES_DB` | Database name | `vos_tool` |
| `POSTGRES_USER` | Database username | `vos_user` |
| `POSTGRES_PASSWORD` | Database password | **(Required)** |

## AssemblyAI Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `ASSEMBLYAI_API_KEY` | AssemblyAI API key | **(Required)** |
| `ASSEMBLYAI_TRANSCRIPTION_TIMEOUT` | Transcription API timeout (seconds) | `300` (5 minutes) |
| `ASSEMBLYAI_POLLING_INTERVAL` | Seconds between status checks | `5` |
| `ASSEMBLYAI_RETRY_ATTEMPTS` | Number of retry attempts on failure | `3` |
| `ASSEMBLYAI_ENABLE_SPEAKER_DIARIZATION` | Enable speaker diarization (true/false) | `false` |

**Note**: For 30-60 second files, the system uses progressive timeout calculation (180-210s) instead of the fixed timeout.

## Rebuttal Detection Timeouts

| Variable | Description | Default | Formula |
|----------|-------------|---------|---------|
| `ASSEMBLYAI_REBUTTAL_TIMEOUT_SECONDS` | Base timeout for rebuttal detection (seconds) | `180` (3 min) | BASE + (duration_min × 30s), capped 60-600s |
| `MAX_REBUTTAL_DURATION_SECONDS` | Skip rebuttal detection for files longer than this (seconds) | `600` (10 min) | - |

**Progressive Timeout Calculation**:
- 30-second file → ~180s timeout (3 minutes)
- 60-second file → ~210s timeout (3.5 minutes)
- Longer files scale proportionally up to 600s maximum

## Processing Timeouts

| Variable | Description | Default |
|----------|-------------|---------|
| `PROCESSING_TIMEOUT_SINGLE_FILE` | Overall timeout for single file processing (seconds) | `600` (10 minutes) |
| `PROCESSING_TIMEOUT_LITE_FILE` | Timeout for lite audit processing (seconds) | `60` (1 minute) |

## Server Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `BACKEND_HOST` | Backend server host | `0.0.0.0` |
| `BACKEND_PORT` | Backend server port | `8000` |
| `FRONTEND_URL` | Frontend URL for CORS | `http://localhost:8501` |
| `CORS_ORIGINS` | Comma-separated list of allowed origins | Auto-configured from FRONTEND_URL |
| `DEBUG` | Enable debug mode (true/false) | `false` |

## ReadyMode Configuration (Optional)

| Variable | Description | Default |
|----------|-------------|---------|
| `FORCE_READYMODE` | Force enable ReadyMode automation (true/false) | `false` |
| `READYMODE_USER` | ReadyMode username | - |
| `READYMODE_PASSWORD` | ReadyMode password | - |

## File Storage

| Variable | Description | Default |
|----------|-------------|---------|
| `RECORDINGS_ROOT` | Root directory for recordings | `./Recordings` |
| `UPLOAD_DIR` | Upload directory path | Uses `RECORDINGS_ROOT` |

## Advanced Settings (Optional)

| Variable | Description | Default |
|----------|-------------|---------|
| `ENCRYPTION_KEY` | Encryption key for sensitive data | - |
| `SESSION_SECRET` | Session management secret | - |
| `DEPLOYMENT_MODE` | Deployment mode (auto/enterprise/production) | `auto` |
| `DB_POOL_MAX_SIZE` | Database connection pool max size | `50` |
| `DB_CONNECT_TIMEOUT` | Database connection timeout (seconds) | `10` |
| `DB_QUERY_TIMEOUT` | Database query timeout (milliseconds) | `30000` |
| `MAX_CONCURRENT_USERS` | Maximum concurrent users | `4` |

## Timeout Troubleshooting

If you experience timeout errors:

1. **For 30-60 second files timing out**:
   - The system now uses progressive timeouts (180-210s)
   - Check logs for which stage is slow (transcription, accent correction, or detection)
   - If still timing out, increase `ASSEMBLYAI_REBUTTAL_TIMEOUT_SECONDS` to 300 or higher

2. **For longer files**:
   - Increase `ASSEMBLYAI_TRANSCRIPTION_TIMEOUT` (default: 300s)
   - Increase `PROCESSING_TIMEOUT_SINGLE_FILE` (default: 600s)
   - Files longer than `MAX_REBUTTAL_DURATION_SECONDS` will skip rebuttal detection

3. **Check performance logs**:
   - Look for warnings like "took Xx longer than file duration"
   - This indicates which processing stage needs optimization

## Example .env File

```bash
# Database
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=vos_tool
POSTGRES_USER=vos_user
POSTGRES_PASSWORD=your_secure_password

# Security
SECRET_KEY=your_secret_key_here
JWT_SECRET=your_jwt_secret_here

# AssemblyAI
ASSEMBLYAI_API_KEY=your_assemblyai_api_key
ASSEMBLYAI_TRANSCRIPTION_TIMEOUT=300
ASSEMBLYAI_REBUTTAL_TIMEOUT_SECONDS=180

# Processing Timeouts
PROCESSING_TIMEOUT_SINGLE_FILE=600
PROCESSING_TIMEOUT_LITE_FILE=60
MAX_REBUTTAL_DURATION_SECONDS=600

# Server
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000
FRONTEND_URL=http://localhost:8501
DEBUG=false
```
