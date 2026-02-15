# CoCo Deployment Guide - Raspberry Pi 5

This guide covers deploying the CoCo campus information kiosk to a Raspberry Pi 5 using Git.

## Prerequisites

### Raspberry Pi Requirements
- Raspberry Pi 5 (4GB or 8GB RAM recommended)
- Raspberry Pi OS (64-bit) installed
- Internet connection (for initial setup)
- microSD card (32GB+) or SSD

### Software Requirements
- Python 3.8 or higher (pre-installed on Raspberry Pi OS)
- Git (pre-installed on Raspberry Pi OS)
- OpenAI API key

---

## Part 1: Prepare Repository (On Your Dev Machine)

### 1.1 Create GitHub Repository

```bash
# Navigate to project
cd vibecoding_coco

# Create a new repository on GitHub (github.com/new), then:
git remote add origin https://github.com/YOUR_USERNAME/coco-kiosk.git

# Push to GitHub
git push -u origin main

# Push all tags
git push origin --tags
```

### 1.2 Tag Current Version for Deployment

```bash
# Create deployment tag
git tag -a v1.0-deploy -m "First deployment version"
git push origin v1.0-deploy
```

### 1.3 Pre-Ingest Documents (REQUIRED)

**CRITICAL**: The Raspberry Pi runs in runtime mode only. You must ingest documents on your development machine before deploying.

```bash
# Navigate to app directory
cd campus_rag_chatbot

# Ingest documents (creates vector_store/ folder)
python admin.py ingest documents_to_ingest/

# Verify vector store was created
ls -la vector_store/
# Should show: index.faiss, index.pkl

# Commit the vector store
git add vector_store/
git commit -m "Add pre-ingested vector store for RPi deployment"
git push
```

### 1.4 Verify Repository is Clean

Before deploying, ensure:
- [ ] No `.env` files are committed (check with `git ls-files | grep .env`)
- [ ] API keys are not in any committed files
- [ ] `.gitignore` excludes sensitive files
- [ ] **Vector store is committed** (check with `git ls-files vector_store/`)

---

## Part 2: Initial Setup on Raspberry Pi

### 2.1 Connect to Raspberry Pi

```bash
# SSH into your Pi (replace with your Pi's IP address)
ssh pi@192.168.1.XXX

# Or use a monitor and keyboard directly
```

### 2.2 Clone the Repository

```bash
# Navigate to home directory
cd ~

# Clone the repository
git clone https://github.com/YOUR_USERNAME/coco-kiosk.git

# Enter project directory
cd coco-kiosk
```

### 2.3 Checkout Specific Version

```bash
# List available tags
git tag -l

# Checkout the deployment version
git checkout v1.0-deploy

# Or checkout a specific iteration
git checkout iteration_5
```

### 2.4 Run Setup Script

```bash
# Make script executable
chmod +x pi-setup.sh

# Run setup
./pi-setup.sh
```

The script will:
1. Install system packages (Python 3.11, ffmpeg, espeak-ng, tesseract-ocr, etc.)
2. Check Python version (3.11 recommended for Piper TTS)
3. Create a Python virtual environment
4. Install dependencies from `requirements_rpi.txt` (ARM64 optimized)
5. Create `.env` file from template
6. Optionally download voice models (~135MB) for offline STT/TTS
7. Verify pre-ingested vector store exists (NO ingestion on RPi)

**IMPORTANT**: The Raspberry Pi runs in **runtime mode only**. Document ingestion must be performed on the development machine before deployment.

### 2.5 Configure Environment Variables

Edit the `.env` file:

```bash
cd campus_rag_chatbot
nano .env
```

Add your keys:

```
OPENAI_API_KEY=sk-your-openai-api-key-here
ADMIN_API_KEY=your-generated-uuid-here
```

To generate an admin API key:

```bash
python3 -c "import uuid; print(uuid.uuid4())"
```

Save and exit (Ctrl+X, Y, Enter).

### 2.6 Vector Store (Pre-Ingested)

**The RPi does NOT perform document ingestion.** The vector store must be pre-ingested on your development machine and included in the git repository.

If you see "Vector store not found" error, follow these steps on your **development machine**:

```bash
# On your development machine (Windows/Mac/Linux)
cd campus_rag_chatbot
python admin.py ingest documents_to_ingest/

# Commit the vector store to git
git add vector_store/
git commit -m "Add pre-ingested vector store"
git push
```

Then on the Raspberry Pi:

```bash
cd ~/coco-kiosk
git pull
```

The setup script will verify the vector store exists during Step 7.

---

## Part 3: Running the Application

### 3.1 Start the Server

```bash
# Activate virtual environment (if not active)
source ~/coco-kiosk/venv/bin/activate

# Navigate to app directory
cd ~/coco-kiosk/campus_rag_chatbot

# Start the server
python app.py
```

The server will start on `http://0.0.0.0:8000`

### 3.2 Access the Application

From any device on the same network:

- **User Interface:** `http://<pi-ip>:8000/`
- **Admin Interface:** `http://<pi-ip>:8000/admin`
- **Health Check:** `http://<pi-ip>:8000/health`

Find your Pi's IP address:

```bash
hostname -I
```

### 3.3 Auto-Start on Boot (Systemd Service)

Create a systemd service for automatic startup:

```bash
sudo nano /etc/systemd/system/coco.service
```

Add the following content:

```ini
[Unit]
Description=CoCo Campus Information Kiosk
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/coco-kiosk/campus_rag_chatbot
Environment=PATH=/home/pi/coco-kiosk/venv/bin
ExecStart=/home/pi/coco-kiosk/venv/bin/python app.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start the service:

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable auto-start on boot
sudo systemctl enable coco

# Start the service now
sudo systemctl start coco

# Check status
sudo systemctl status coco
```

Service commands:

```bash
sudo systemctl start coco    # Start
sudo systemctl stop coco     # Stop
sudo systemctl restart coco  # Restart
sudo systemctl status coco   # Check status
journalctl -u coco -f        # View logs
```

---

## Part 4: Updating the Application

### 4.1 Pull Latest Changes

```bash
# Stop the service
sudo systemctl stop coco

# Navigate to repository
cd ~/coco-kiosk

# Fetch updates
git fetch origin

# See available tags
git tag -l

# Checkout new version
git checkout v1.1-deploy  # or new tag name

# Reinstall dependencies (if requirements.txt changed)
source venv/bin/activate
pip install -r campus_rag_chatbot/requirements.txt

# Restart service
sudo systemctl start coco
```

### 4.2 Switching Between Versions

```bash
# Stop service
sudo systemctl stop coco

# List all available versions
git tag -l

# Switch to a different version
git checkout iteration_4

# Restart
sudo systemctl start coco
```

### 4.3 Rolling Back

If a new version has issues:

```bash
# Stop service
sudo systemctl stop coco

# Go back to previous working version
git checkout v1.0-deploy

# Restart
sudo systemctl start coco
```

---

## Part 5: Environment-Specific Settings

### Development vs Kiosk Mode

| Setting | Development | Kiosk (Production) |
|---------|-------------|-------------------|
| Debug logging | Enabled | Disabled |
| CORS | Allow all | Restrict to kiosk IP |
| Workers | 1 | 1-2 |

For kiosk mode, consider editing `app.py` CORS settings:

```python
# Change from:
allow_origins=["*"]

# To:
allow_origins=["http://localhost", "http://127.0.0.1"]
```

### Secure API Key Storage

For production, consider:

1. **File permissions:**
   ```bash
   chmod 600 ~/coco-kiosk/campus_rag_chatbot/.env
   ```

2. **Environment variables in systemd:**
   Instead of `.env` file, add to service:
   ```ini
   Environment=OPENAI_API_KEY=sk-xxx
   Environment=ADMIN_API_KEY=xxx
   ```

---

## Troubleshooting

### Issue: "ModuleNotFoundError"

```bash
# Ensure virtual environment is activated
source ~/coco-kiosk/venv/bin/activate

# Reinstall dependencies
pip install -r campus_rag_chatbot/requirements.txt
```

### Issue: faiss-cpu installation fails

On ARM64, try:

```bash
pip install faiss-cpu --no-cache-dir
```

If that fails:

```bash
# Install from conda-forge (alternative)
pip install faiss-cpu==1.7.4
```

### Issue: Voice not working (Piper TTS)

Piper TTS requires Python 3.11. Check your Python version:

```bash
python --version
```

If not 3.11, voice will automatically use cloud fallback (edge-tts).

To manually download voice models:

```bash
./download-voice-models.sh
```

This downloads:
- Whisper STT model (~75MB) for offline speech-to-text
- Piper TTS model (~60MB) for offline text-to-speech

### Issue: "No vector store found"

```bash
cd ~/coco-kiosk/campus_rag_chatbot
source ../venv/bin/activate
python admin.py ingest data/
```

### Issue: Cannot connect from other devices

```bash
# Check if server is running
curl http://localhost:8000/health

# Check firewall
sudo ufw status

# Allow port 8000 if needed
sudo ufw allow 8000
```

### Issue: Service won't start

```bash
# Check logs
journalctl -u coco -n 50

# Test manually
cd ~/coco-kiosk/campus_rag_chatbot
source ../venv/bin/activate
python app.py
```

### Issue: Out of memory

- Reduce number of ingested documents
- Use swap:
  ```bash
  sudo dphys-swapfile swapoff
  sudo nano /etc/dphys-swapfile  # Set CONF_SWAPSIZE=2048
  sudo dphys-swapfile setup
  sudo dphys-swapfile swapon
  ```

---

## Quick Reference

| Task | Command |
|------|---------|
| Start service | `sudo systemctl start coco` |
| Stop service | `sudo systemctl stop coco` |
| Restart service | `sudo systemctl restart coco` |
| View logs | `journalctl -u coco -f` |
| Check status | `sudo systemctl status coco` |
| Update to new tag | `git fetch && git checkout <tag>` |
| Find Pi IP | `hostname -I` |
| Activate venv | `source ~/coco-kiosk/venv/bin/activate` |

---

## Deployment Checklist

- [ ] Repository pushed to GitHub
- [ ] Tagged version created
- [ ] Pi has internet access
- [ ] Repository cloned on Pi
- [ ] Correct tag checked out
- [ ] Setup script run successfully
- [ ] `.env` configured with API keys
- [ ] Documents ingested
- [ ] Server starts without errors
- [ ] Can access from browser
- [ ] Systemd service configured (optional)
- [ ] Auto-start on boot enabled (optional)
