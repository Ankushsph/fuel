# 📹 CAMERA SETUP - QUICK START

## 🎯 5-Minute Setup Guide for Petrol Bunk

### **Step 1: Find Camera IP (2 minutes)**

**Option A: Check Camera Label**
- Look for sticker on camera
- IP usually printed: `192.168.1.64`

**Option B: Use Router**
- Login to router: `http://192.168.1.1`
- Check connected devices
- Find camera by name/MAC

**Option C: Use Camera Tool**
- Hikvision: Download SADP Tool
- Dahua: Download Config Tool
- Scan network for cameras

### **Step 2: Access Camera (1 minute)**

1. Open browser
2. Type: `http://192.168.1.64` (your camera IP)
3. Login:
   - Username: `admin`
   - Password: Check camera label (often `admin` or `12345`)

### **Step 3: Get RTSP URL (2 minutes)**

**In camera web interface:**
1. Go to **Configuration** → **Network** → **Advanced**
2. Find **RTSP** section
3. Note the RTSP Port (usually `554`)
4. Note the Stream Path

**Build your RTSP URL:**
```
rtsp://[username]:[password]@[camera-ip]:554/[stream-path]
```

**Example for Hikvision:**
```
rtsp://admin:admin123@192.168.1.64:554/Streaming/Channels/101
```

**Example for Dahua:**
```
rtsp://admin:admin123@192.168.1.108:554/cam/realmonitor?channel=1&subtype=0
```

### **Step 4: Test in VLC (30 seconds)**

1. Open VLC Media Player
2. Media → Open Network Stream
3. Paste RTSP URL
4. Click Play
5. **Video should play!**

### **Step 5: Add to Application (30 seconds)**

1. Start app: `python app.py`
2. Login to dashboard
3. Go to Vehicle Counting or Vehicle Verification
4. Fill form:
   - Station Name: "Main Gate"
   - Location: "Petrol Bunk"
   - RTSP URL: (paste your URL)
5. Click "Add CCTV Stream"
6. **Done! Monitoring starts automatically!**

---

## 🔍 Common Camera RTSP URLs

### **Hikvision**
```
Main Stream:
rtsp://admin:password@192.168.1.64:554/Streaming/Channels/101

Sub Stream (lower quality, less CPU):
rtsp://admin:password@192.168.1.64:554/Streaming/Channels/102
```

### **Dahua / CP Plus**
```
Main Stream:
rtsp://admin:password@192.168.1.108:554/cam/realmonitor?channel=1&subtype=0

Sub Stream:
rtsp://admin:password@192.168.1.108:554/cam/realmonitor?channel=1&subtype=1
```

### **Axis**
```
rtsp://admin:password@192.168.1.100:554/axis-media/media.amp
```

### **Generic ONVIF**
```
rtsp://admin:password@192.168.1.72:554/onvif1
```

---

## ⚠️ Troubleshooting

### **Can't access camera web interface?**
- Check camera is powered on (look for LED)
- Ensure your computer is on same network
- Try default IPs: `192.168.1.64`, `192.168.1.108`, `192.168.1.100`
- Try pinging camera: `ping 192.168.1.64`

### **VLC can't play RTSP URL?**
- Double-check username/password
- Ensure RTSP is enabled in camera settings
- Try sub stream URL (lower quality)
- Check firewall isn't blocking port 554

### **Application shows "Connection timeout"?**
- **First test in VLC** - if VLC works, app will work
- Restart the application
- Check console for error messages
- Ensure camera is on same network as server

---

## 📝 Quick Checklist

Before adding camera to application:

- [ ] Camera is powered on and accessible
- [ ] Found camera IP address
- [ ] Can access camera web interface
- [ ] RTSP is enabled in camera
- [ ] Have correct username/password
- [ ] RTSP URL works in VLC Media Player
- [ ] Server and camera on same network

**If all checked, your camera will work in the application!**

---

## 🎯 What to Expect

### **After Adding Stream:**

**Console Output:**
```
🔄 Starting vehicle counting for pump 1...
📹 RTSP URL: rtsp://admin:***@192.168.1.64:554/...
🔌 Trying FFMPEG backend...
✅ Connected with FFMPEG on attempt 2
✅ Started RTSP processing for pump 1
🤖 YOLO model loaded: True
🚗 Pump 1: Detected 3 vehicles (frame 150)
```

**Dashboard:**
- Stream shows **🟢 MONITORING** or **🟢 DETECTING**
- Vehicle count updates every 2 seconds
- Detected plates appear in list
- Graph shows real-time trend

**This means it's working!**

---

## 💡 Pro Tips

1. **Use Sub Stream for testing** - Lower CPU usage, faster connection
2. **Test in VLC first** - Saves debugging time
3. **Use static IPs** - Prevents cameras changing IP
4. **Good lighting** - Essential for plate/face detection
5. **Proper camera angle** - Overhead for counting, straight-on for plates

---

## 📞 Need Help?

**Check these in order:**

1. Can you access camera web interface? → Fix network/IP first
2. Does RTSP work in VLC? → Fix camera RTSP settings
3. Does application show connection attempts? → Check console logs
4. Is YOLO model loaded? → Check `model/yolov8m.pt` exists

**Most issues are solved by testing in VLC first!**

---

## ✅ Success Indicators

**You'll know it's working when you see:**

✅ Stream card shows **🟢 MONITORING** or **🟢 DETECTING**  
✅ Console shows "✅ Connected with FFMPEG"  
✅ Console shows "🚗 Detected X vehicles"  
✅ Dashboard updates automatically  
✅ Data appears in database  

**Your application is ready for petrol bunk deployment!**
