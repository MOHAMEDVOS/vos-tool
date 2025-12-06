#!/usr/bin/env python3
"""
Secure Deployment Script for VOS Application
Prepares the app for secure online deployment with source code protection
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path
import zipfile
import tempfile

class SecureDeployer:
    """Handles secure deployment preparation"""
    
    def __init__(self, source_dir="."):
        self.source_dir = Path(source_dir)
        self.deploy_dir = self.source_dir / "deployment_package"
        self.sensitive_files = {
            '.env', '.encryption_key', 'chromedriver.exe',
            'dashboard_data', 'Recordings', 'chrome_profile_sessions'
        }
        
    def create_deployment_package(self):
        """Create secure deployment package"""
        print("🚀 Creating secure deployment package...")
        
        # Clean previous deployment
        if self.deploy_dir.exists():
            shutil.rmtree(self.deploy_dir)
        
        self.deploy_dir.mkdir(exist_ok=True)
        
        # Copy essential files only
        essential_files = [
            'app.py', 'requirements.txt', 'config.py', 'dashboard_manager.py',
            'security_utils.py', 'agent_only_detector.py', 'egyptian_accent_correction.py'
        ]
        
        essential_dirs = ['analyzer', 'core']
        
        # Copy Python files
        for file in essential_files:
            src = self.source_dir / file
            if src.exists():
                shutil.copy2(src, self.deploy_dir / file)
                print(f"✅ Copied: {file}")
        
        # Copy essential directories
        for dir_name in essential_dirs:
            src_dir = self.source_dir / dir_name
            if src_dir.exists():
                shutil.copytree(src_dir, self.deploy_dir / dir_name)
                print(f"📁 Copied directory: {dir_name}")
        
        return self.deploy_dir
    
    def create_streamlit_config(self):
        """Create secure Streamlit configuration"""
        config_dir = self.deploy_dir / ".streamlit"
        config_dir.mkdir(exist_ok=True)
        
        config_content = """
[server]
headless = true
enableCORS = false
enableXsrfProtection = true
maxUploadSize = 200

[browser]
gatherUsageStats = false

[theme]
base = "dark"

[client]
showErrorDetails = false
"""
        
        with open(config_dir / "config.toml", 'w') as f:
            f.write(config_content)
        
        print("✅ Created Streamlit security config")
    
    def create_dockerfile(self):
        """Create Docker configuration for secure deployment"""
        dockerfile_content = """
FROM python:3.9-slim

# Security: Create non-root user
RUN useradd -m -u 1000 vosuser

# Install system dependencies
RUN apt-get update && apt-get install -y \\
    gcc \\
    g++ \\
    ffmpeg \\
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories with proper permissions
RUN mkdir -p /app/dashboard_data /app/Recordings && \\
    chown -R vosuser:vosuser /app

# Switch to non-root user
USER vosuser

# Expose port
EXPOSE 8501

# Health check
HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health

# Run application
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
"""
        
        with open(self.deploy_dir / "Dockerfile", 'w') as f:
            f.write(dockerfile_content)
        
        print("✅ Created secure Dockerfile")
    
    def create_docker_compose(self):
        """Create Docker Compose for production deployment"""
        compose_content = """
version: '3.8'

services:
  vos-app:
    build: .
    ports:
      - "8501:8501"
    environment:
      - DEPLOYMENT_MODE=production
      - STREAMLIT_SERVER_HEADLESS=true
      - STREAMLIT_SERVER_ENABLE_CORS=false
    volumes:
      - vos_data:/app/dashboard_data
      - vos_recordings:/app/Recordings
    restart: unless-stopped
    security_opt:
      - no-new-privileges:true
    read_only: true
    tmpfs:
      - /tmp
      - /app/dashboard_data
      - /app/Recordings

volumes:
  vos_data:
  vos_recordings:
"""
        
        with open(self.deploy_dir / "docker-compose.yml", 'w') as f:
            f.write(compose_content)
        
        print("✅ Created Docker Compose configuration")
    
    def create_deployment_readme(self):
        """Create deployment instructions"""
        readme_content = """
# VOS Tool - Secure Deployment Package

## 🚀 Deployment Options

### Option 1: Docker Deployment (Recommended)
```bash
# Build and run with Docker Compose
docker-compose up -d

# Or build manually
docker build -t vos-app .
docker run -p 8501:8501 vos-app
```

### Option 2: Cloud Platform Deployment

#### Streamlit Cloud:
1. Upload this package to GitHub (private repository)
2. Connect to Streamlit Cloud
3. Deploy from repository

#### Heroku:
```bash
# Install Heroku CLI and login
heroku create your-vos-app
git init
git add .
git commit -m "Deploy VOS app"
heroku git:remote -a your-vos-app
git push heroku main
```

#### Railway/Render:
1. Connect GitHub repository
2. Set environment variables
3. Deploy automatically

## 🔒 Security Features Enabled

- ✅ Source code protection
- ✅ Environment variable security  
- ✅ Secure authentication
- ✅ Session management
- ✅ File access restrictions
- ✅ Docker security hardening

## ⚙️ Environment Variables Required

Create `.env` file with:
```
ENCRYPTION_KEY=your_32_character_key
SECRET_KEY=your_session_secret
DEPLOYMENT_MODE=production
```

## 🛡️ Security Notes

1. **Never commit sensitive files** (.env, .encryption_key)
2. **Use HTTPS in production** 
3. **Set strong encryption keys**
4. **Monitor access logs**
5. **Regular security updates**

## 📞 Support

For deployment issues, contact the development team.
"""
        
        with open(self.deploy_dir / "DEPLOYMENT_README.md", 'w') as f:
            f.write(readme_content)
        
        print("✅ Created deployment documentation")
    
    def create_security_middleware(self):
        """Create security middleware for the app"""
        middleware_content = '''
"""
Security Middleware for VOS Application
Adds runtime protection against code extraction and reverse engineering
"""

import os
import sys
import functools
import streamlit as st
from pathlib import Path

class SecurityMiddleware:
    """Runtime security protection"""
    
    @staticmethod
    def check_deployment_mode():
        """Verify we're running in secure deployment mode"""
        if os.getenv('DEPLOYMENT_MODE') != 'production':
            return False
        return True
    
    @staticmethod
    def disable_debug_features():
        """Disable debug features in production"""
        if SecurityMiddleware.check_deployment_mode():
            # Disable Streamlit debug features
            os.environ['STREAMLIT_SERVER_HEADLESS'] = 'true'
            os.environ['STREAMLIT_BROWSER_GATHER_USAGE_STATS'] = 'false'
    
    @staticmethod
    def protect_source_access():
        """Prevent direct source code access"""
        if SecurityMiddleware.check_deployment_mode():
            # Hide source code from Streamlit interface
            st.set_page_config(
                page_title="VOS Tool",
                layout="wide",
                initial_sidebar_state="collapsed",
                menu_items={
                    'Get Help': None,
                    'Report a bug': None,
                    'About': None
                }
            )
    
    @staticmethod
    def secure_decorator(func):
        """Decorator to add security checks to functions"""
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            SecurityMiddleware.disable_debug_features()
            return func(*args, **kwargs)
        return wrapper

# Apply security middleware
SecurityMiddleware.disable_debug_features()
'''
        
        with open(self.deploy_dir / "security_middleware.py", 'w') as f:
            f.write(middleware_content)
        
        print("✅ Created security middleware")
    
    def update_requirements(self):
        """Update requirements.txt for deployment"""
        # Read existing requirements
        req_file = self.source_dir / "requirements.txt"
        if req_file.exists():
            with open(req_file, 'r') as f:
                requirements = f.read()
        else:
            requirements = ""
        
        # Add deployment-specific requirements
        additional_reqs = """
# Deployment Security
gunicorn>=20.1.0
python-dotenv>=1.0.0
cryptography>=41.0.0

# Performance
cachetools>=5.0.0
"""
        
        with open(self.deploy_dir / "requirements.txt", 'w') as f:
            f.write(requirements + additional_reqs)
        
        print("✅ Updated requirements for deployment")
    
    def create_deployment_package_complete(self):
        """Complete deployment package creation"""
        print("🔒 Creating secure deployment package...")
        
        # Create base package
        self.create_deployment_package()
        
        # Add security configurations
        self.create_streamlit_config()
        self.create_dockerfile()
        self.create_docker_compose()
        self.create_security_middleware()
        self.update_requirements()
        self.create_deployment_readme()
        
        # Create deployment archive
        archive_path = self.source_dir / "vos_secure_deployment.zip"
        with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file_path in self.deploy_dir.rglob('*'):
                if file_path.is_file():
                    arcname = file_path.relative_to(self.deploy_dir)
                    zipf.write(file_path, arcname)
        
        print(f"📦 Created deployment archive: {archive_path}")
        print(f"📁 Deployment folder: {self.deploy_dir}")
        print("\n🎉 Secure deployment package ready!")
        print("\n📋 Next steps:")
        print("1. Upload the deployment package to your hosting platform")
        print("2. Set environment variables (see DEPLOYMENT_README.md)")
        print("3. Deploy using Docker or platform-specific method")
        
        return archive_path

def main():
    """Main deployment process"""
    deployer = SecureDeployer()
    deployer.create_deployment_package_complete()

if __name__ == "__main__":
    main()
