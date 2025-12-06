# How to Install Docker on Windows (Super Simple!)

## 🎯 The Problem
You got this error: `'docker' is not recognized`
This means Docker isn't installed yet. Let's fix that!

---

## Step 1: Download Docker Desktop

1. **Open your web browser**
2. **Go to:** https://www.docker.com/products/docker-desktop/
3. **Click the big "Download for Windows" button**
4. **Wait for it to download** (it's a big file, about 500MB)

---

## Step 2: Install Docker Desktop

1. **Find the downloaded file** (usually in your Downloads folder)
   - It's called something like: `Docker Desktop Installer.exe`

2. **Double-click it** to start installing

3. **Follow the installer:**
   - Click "Next" or "Install" when it asks
   - It might ask for admin permission - click "Yes"
   - Wait for it to install (5-10 minutes)

4. **When it says "Installation complete"** - click "Close" or "Finish"

---

## Step 3: Start Docker Desktop

1. **Look for Docker Desktop icon** on your desktop or in Start menu
2. **Double-click it** to start
3. **Wait for it to start** (you'll see a whale icon in your system tray)
4. **It might ask you to accept terms** - click "Accept"

⏳ **First time starting takes 2-5 minutes** - be patient!

---

## Step 4: Check if Docker Works

1. **Open Command Prompt again:**
   - Press Windows key + R
   - Type: `cmd`
   - Press Enter

2. **Type this:**
   ```
   docker --version
   ```

3. **Press Enter**

4. **If you see something like:** `Docker version 24.0.0` or similar
   - ✅ **SUCCESS!** Docker is installed!

5. **If you still get an error:**
   - Make sure Docker Desktop is running (check the whale icon in system tray)
   - Close and reopen Command Prompt
   - Try again

---

## Step 5: Restart Your Computer (Optional but Recommended)

Sometimes Windows needs a restart for everything to work properly.

1. **Save all your work**
2. **Restart your computer**
3. **After restart, open Command Prompt again**
4. **Try:** `docker --version` again

---

## ✅ Once Docker Works

Go back to your project folder and try again:

```
cd C:\Users\vos\Desktop\save v.1
docker build -f runpod.dockerfile -t vos-tool:runpod .
```

---

## 🆘 Still Not Working?

### Problem: "Docker Desktop won't start"
**Solution:**
- Make sure you have Windows 10/11 (64-bit)
- Check if virtualization is enabled in BIOS (advanced - ask for help if needed)
- Restart your computer

### Problem: "Still says 'docker' is not recognized"
**Solution:**
1. Make sure Docker Desktop is running (whale icon in system tray)
2. Close Command Prompt completely
3. Open a NEW Command Prompt
4. Try `docker --version` again

### Problem: "Installation failed"
**Solution:**
- Make sure you have admin rights
- Try right-clicking the installer and "Run as Administrator"
- Check you have enough disk space (need at least 4GB free)

---

## 💡 Quick Checklist

Before you continue:
- [ ] Docker Desktop downloaded
- [ ] Docker Desktop installed
- [ ] Docker Desktop is running (whale icon visible)
- [ ] `docker --version` works in Command Prompt
- [ ] You're ready to continue with the deployment steps!

---

**Once Docker is working, come back and we'll continue with the deployment!** 🚀

