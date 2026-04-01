# Running VOS Tool with Docker Desktop

## Using Docker Desktop GUI

### Step 1: Open Docker Desktop

1. Launch **Docker Desktop** from your Windows Start menu
2. Wait for Docker Desktop to fully start (whale icon in system tray should be steady)

### Step 2: Navigate to Your Project

1. In Docker Desktop, click on **"Containers"** tab (left sidebar)
2. Or use the terminal in Docker Desktop:
   - Click on the terminal icon or use PowerShell/CMD
   - Navigate to your project:
     ```bash
     cd "C:\Users\vos\Desktop\save v.1"
     ```

### Step 3: Start Services via Docker Desktop

#### Option A: Using Docker Desktop UI

1. Open **Docker Desktop**
2. Go to **"Containers"** tab
3. You should see your services listed (if already created):
   - `vos-backend`
   - `vos-frontend`
   - `vos-redis`

4. To start/stop services:
   - Click the **▶️ Play** button to start
   - Click the **⏸️ Stop** button to stop
   - Click the **🔄 Restart** button to restart

#### Option B: Using Terminal in Docker Desktop

1. In Docker Desktop, open the terminal (or use PowerShell)
2. Navigate to your project folder
3. Run:
   ```bash
   docker-compose up -d
   ```

### Step 4: View Running Containers

1. In Docker Desktop, go to **"Containers"** tab
2. You'll see all running containers:
   - **vos-backend** - Backend API (port 8000)
   - **vos-frontend** - Frontend UI (port 8501)
   - **vos-redis** - Redis cache (port 6379)

3. Click on any container to:
   - View logs
   - See resource usage
   - Access container shell
   - View container details

### Step 5: Access the Application

Once containers are running (green status):

1. Open your web browser
2. Go to: **http://localhost:8501**
3. You should see the VOS Tool login page

## Docker Desktop Features

### View Logs

1. Click on a container name (e.g., `vos-backend`)
2. Go to **"Logs"** tab
3. See real-time logs

### Container Actions

Right-click on any container or use the action buttons:
- **Start** - Start the container
- **Stop** - Stop the container
- **Restart** - Restart the container
- **Delete** - Remove the container
- **View Logs** - See container logs
- **Inspect** - View detailed container information
- **Exec** - Open shell inside container

### Resource Monitoring

1. Click on a container
2. Go to **"Stats"** tab
3. See:
   - CPU usage
   - Memory usage
   - Network I/O
   - Block I/O

## Quick Start Commands (Terminal)

If you prefer using terminal in Docker Desktop:

```bash
# Navigate to project
cd "C:\Users\vos\Desktop\save v.1"

# Start all services
docker-compose up -d

# View status
docker-compose ps

# View logs
docker-compose logs -f

# Stop all services
docker-compose down
```

## Troubleshooting in Docker Desktop

### Containers Won't Start

1. Check **"Logs"** tab for errors
2. Verify Docker Desktop is running (whale icon in system tray)
3. Check if ports are available:
   - Port 8000 (Backend)
   - Port 8501 (Frontend)
   - Port 6379 (Redis)

### View Container Logs

1. Click on container name
2. Go to **"Logs"** tab
3. Look for error messages

### Restart a Specific Container

1. Find the container in the list
2. Click **🔄 Restart** button
3. Or right-click → **Restart**

### Check Container Health

1. Click on container
2. Look at the status indicator:
   - 🟢 Green = Healthy/Running
   - 🟡 Yellow = Starting/Unhealthy
   - 🔴 Red = Stopped/Error

## Docker Desktop Settings

### Allocate Resources

1. Click **⚙️ Settings** (gear icon)
2. Go to **"Resources"**
3. Adjust:
   - **CPUs**: Recommended 4+
   - **Memory**: Recommended 8GB+
   - **Disk**: Ensure enough space

### Enable WSL 2 (If Needed)

1. Settings → **"General"**
2. Enable **"Use the WSL 2 based engine"**
3. Apply & Restart

## Visual Guide

### Docker Desktop Interface

```
┌─────────────────────────────────────┐
│  Docker Desktop                     │
├─────────────────────────────────────┤
│  Containers | Images | Volumes      │
├─────────────────────────────────────┤
│  vos-backend    [▶️] [⏸️] [🔄]      │
│  vos-frontend   [▶️] [⏸️] [🔄]      │
│  vos-redis      [▶️] [⏸️] [🔄]      │
└─────────────────────────────────────┘
```

## Daily Workflow

### Morning: Start Services

1. Open Docker Desktop
2. Go to **"Containers"** tab
3. Click **▶️ Start** on all services
4. Or run: `docker-compose up -d`

### During Work

- Monitor containers in Docker Desktop
- View logs if needed
- Check resource usage

### Evening: Stop Services (Optional)

1. Click **⏸️ Stop** on all services
2. Or run: `docker-compose stop`

## Tips

- Keep Docker Desktop running in the background
- Use the GUI for visual monitoring
- Use terminal for quick commands
- Containers auto-restart if Docker Desktop restarts (if configured)
- All data persists in Docker volumes

## Access Points

Once running in Docker Desktop:

- **Frontend**: http://localhost:8501
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

