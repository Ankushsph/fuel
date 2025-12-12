"""
Direct RTSP test - automatically tests multiple URLs
"""
import cv2
import time

# Multiple test URLs to try
TEST_URLS = [
    ("Public Demo 1", "rtsp://wowzaec2demo.streamlock.net/vod/mp4:BigBuckBunny_115k.mp4"),
    ("Public Demo 2", "rtsp://wowzaec2demo.streamlock.net/vod/mp4:BigBuckBunny_115k.mov"),
    ("Your Camera", "rtsp://192.168.1.72:554/cam/realmonitor?channel=4&subtype=0&unicast=true&proto=Onvif"),
]

def test_url(name, url):
    """Test a single RTSP URL"""
    print(f"\n{'='*70}")
    print(f"Testing: {name}")
    print(f"URL: {url}")
    print(f"{'='*70}")
    
    # Try both backends
    backends = [(cv2.CAP_FFMPEG, "FFMPEG"), (cv2.CAP_ANY, "ANY")]
    
    for backend, backend_name in backends:
        print(f"\n🔌 Trying {backend_name} backend...")
        cap = cv2.VideoCapture(url, backend)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 20000)
        cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 20000)
        
        # Try to connect
        connected = False
        for attempt in range(8):
            print(f"  Attempt {attempt + 1}/8...", end=" ", flush=True)
            
            if cap.isOpened():
                ret, frame = cap.read()
                if ret and frame is not None:
                    h, w = frame.shape[:2]
                    print(f"✅ SUCCESS! Frame: {w}x{h}")
                    
                    # Read a few more frames
                    success_count = 0
                    for i in range(5):
                        ret, frame = cap.read()
                        if ret:
                            success_count += 1
                        time.sleep(0.2)
                    
                    print(f"  ✅ Read {success_count}/5 test frames")
                    cap.release()
                    return True
                else:
                    print("❌ No frame")
            else:
                print("⏳ Not opened")
            
            time.sleep(1.5)
        
        cap.release()
        print(f"  ❌ Failed with {backend_name}")
    
    return False

if __name__ == "__main__":
    print("\n" + "="*70)
    print("AUTOMATIC RTSP CONNECTION TEST")
    print("="*70)
    print("\nTesting multiple RTSP URLs automatically...\n")
    
    results = {}
    for name, url in TEST_URLS:
        results[name] = test_url(name, url)
        time.sleep(1)
    
    # Summary
    print("\n" + "="*70)
    print("TEST RESULTS SUMMARY")
    print("="*70)
    
    working = []
    failed = []
    
    for name, success in results.items():
        if success:
            print(f"✅ {name}: WORKING")
            working.append(name)
        else:
            print(f"❌ {name}: FAILED")
            failed.append(name)
    
    print("\n" + "="*70)
    if working:
        print(f"✅ {len(working)} URL(s) working - You can use these in your application!")
    else:
        print("❌ No URLs working - Check your network/firewall settings")
    print("="*70)
    
    input("\nPress Enter to exit...")
