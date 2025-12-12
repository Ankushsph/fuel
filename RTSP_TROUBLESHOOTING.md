# 🔧 RTSP Connection Troubleshooting Guide

## 🚨 Common Issues and Solutions

### Issue 1: "Stream connection timeout. Check camera and network."

**Causes:**
- Camera is offline or not powered on
- Network connectivity issues
- Firewall blocking RTSP port (usually 554)
- Incorrect RTSP URL format

**Solutions:**
1. **Verify camera is online:**
   - Ping the camera IP: `ping 192.168.1.72`
   - Check if camera web interface is accessible

2. **Check RTSP URL format:**
   ```
   Correct format: rtsp://[username]:[password]@[ip]:[port]/[path]
   
   Examples:
   rtsp://admin:password123@192.168.1.72:554/cam/realmonitor?channel=4&subtype=0&unicast=true&proto=Onvif
   rtsp://admin:12345@192.168.1.100:554/stream1
   rtsp://192.168.1.50:554/live/ch00_0
   ```

3. **Test connection manually:**
   ```bash
   python test_rtsp_connection.py
   ```

4. **Check firewall settings:**
   - Ensure port 554 (RTSP) is not blocked
   - Check Windows Firewall or antivirus settings

---

### Issue 2: Vehicle counting shows "0" even with cars moving

**Causes:**
- YOLO model not loaded properly
- RTSP stream not connected
- Camera angle doesn't capture vehicles clearly
- Low confidence threshold

**Solutions:**
1. **Verify YOLO model exists:**
   - Check if `model/yolov8m.pt` file exists
   - File size should be ~50MB

2. **Check console logs:**
   - Look for "✅ Started RTSP processing for pump X"
   - Look for "🚗 Pump X: Detected Y vehicles"

3. **Improve detection:**
   - Position camera to have clear view of vehicles
   - Ensure good lighting conditions
   - Vehicles should be clearly visible in frame

4. **Monitor logs in real-time:**
   - Vehicle count is logged every 10 seconds
   - Check terminal/console for detection messages

---

### Issue 3: Attendance not marking employees

**Causes:**
- Face recognition service not initialized
- Employee photos not clear enough
- Camera angle doesn't capture faces
- Face encodings not generated

**Solutions:**
1. **Verify employee photos:**
   - Photos should show face clearly
   - Good lighting, no sunglasses/masks
   - Face should be front-facing

2. **Re-upload employee photos:**
   - Delete and re-add employee
   - Ensure face is clearly visible in photo

3. **Check face recognition service:**
   - Look for "Face recognition unavailable" messages
   - Ensure `face_recognition` library is installed

4. **Camera positioning:**
   - Camera should capture employee faces clearly
   - Height should be at face level
   - Good lighting is essential

---

## 🔍 Testing Your RTSP Connection

### Method 1: Use Test Script
```bash
cd E:\fuelflux\Flue_flex_pvt_ltd_
python test_rtsp_connection.py
```

### Method 2: Use VLC Media Player
1. Open VLC Media Player
2. Go to Media → Open Network Stream
3. Paste your RTSP URL
4. Click Play
5. If video plays, RTSP URL is correct

### Method 3: Use FFmpeg
```bash
ffmpeg -i "rtsp://192.168.1.72:554/cam/realmonitor?channel=4&subtype=0&unicast=true&proto=Onvif" -frames:v 1 test.jpg
```

---

## 📋 RTSP URL Examples by Camera Brand

### Hikvision
```
rtsp://admin:password@192.168.1.64:554/Streaming/Channels/101
```

### Dahua
```
rtsp://admin:password@192.168.1.108:554/cam/realmonitor?channel=1&subtype=0
```

### Axis
```
rtsp://admin:password@192.168.1.100:554/axis-media/media.amp
```

### Foscam
```
rtsp://admin:password@192.168.1.50:554/videoMain
```

### Generic ONVIF
```
rtsp://admin:password@192.168.1.72:554/cam/realmonitor?channel=4&subtype=0&unicast=true&proto=Onvif
```

---

## ⚙️ Application Configuration

### Timeouts (Already Configured)
- Connection timeout: 20 seconds
- Read timeout: 20 seconds
- Reconnection attempts: 8 times
- Frame buffer: 1 (for low latency)

### Detection Settings
- **Face Recognition:**
  - Confidence threshold: 0.7 (70%)
  - Detection interval: Every 5th frame
  - Attendance cooldown: 30 seconds

- **Vehicle Detection:**
  - Confidence threshold: 0.3 (30%)
  - Detection interval: Every 1 second
  - Vehicle classes: Car, Motorcycle, Bus, Truck

---

## 🐛 Debug Mode

### Enable Detailed Logging

1. **Check console output:**
   - Run Flask app in terminal to see logs
   - Look for connection messages

2. **Key log messages:**
   ```
   ✅ Connected with FFMPEG on attempt X
   ✅ Started RTSP processing for pump X
   🚗 Pump X: Detected Y vehicles (frame Z)
   ✅ RTSP stream opened successfully for pump X
   ```

3. **Error messages to watch for:**
   ```
   ❌ Failed to open RTSP stream for pump X
   ⚠️  Frame read failed for pump X
   ❌ Too many failures for pump X, stopping
   ```

---

## 📞 Still Having Issues?

### Checklist:
- [ ] Camera is powered on and accessible
- [ ] RTSP URL format is correct
- [ ] Network allows RTSP traffic (port 554)
- [ ] Credentials (username/password) are correct
- [ ] Camera supports RTSP protocol
- [ ] YOLO model file exists (`model/yolov8m.pt`)
- [ ] Employee photos are clear and face-visible
- [ ] Python packages installed: `opencv-python`, `ultralytics`, `face_recognition`

### Next Steps:
1. Run the test script: `python test_rtsp_connection.py`
2. Check console logs for error messages
3. Verify camera settings in camera's web interface
4. Test RTSP URL in VLC Media Player first
5. Ensure firewall isn't blocking connections

---

## ✅ Success Indicators

### Attendance Monitor:
- Video stream loads without errors
- Employee faces are detected with green boxes
- "ATTENDANCE MARKED" appears when employee detected
- Employee status shows "Present" with green badge

### Vehicle Counting:
- Current vehicle count updates every 2 seconds
- Station status changes (Idle → Normal → Busy)
- Graph shows vehicle count trend
- Console logs show "🚗 Detected X vehicles"

---

## 🔄 Quick Restart

If issues persist, restart the application:

```bash
# Stop the Flask app (Ctrl+C)
# Then restart:
cd E:\fuelflux\Flue_flex_pvt_ltd_
python app.py
```

The application will:
- Reconnect to all RTSP streams
- Reload YOLO model
- Reinitialize face recognition
- Start background monitoring threads
