"""
Quick test script to verify RTSP connection
Usage: python test_rtsp_connection.py
"""
import cv2
import time

def test_rtsp(rtsp_url):
    """Test RTSP connection with detailed logging"""
    print(f"\n{'='*60}")
    print(f"Testing RTSP Connection")
    print(f"{'='*60}")
    print(f"URL: {rtsp_url}")
    print(f"\n🔄 Attempting connection...")
    
    # Try multiple backends
    backends = [
        (cv2.CAP_FFMPEG, "FFMPEG"),
        (cv2.CAP_ANY, "ANY")
    ]
    
    for backend, backend_name in backends:
        print(f"\n🔌 Trying {backend_name} backend...")
        cap = cv2.VideoCapture(rtsp_url, backend)
        
        # Set timeouts
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 20000)
        cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 20000)
        
        # Try to connect
        max_attempts = 8
        for attempt in range(max_attempts):
            print(f"  Attempt {attempt + 1}/{max_attempts}...", end=" ")
            
            if cap.isOpened():
                # Try to read a frame
                ret, frame = cap.read()
                if ret and frame is not None:
                    h, w = frame.shape[:2]
                    print(f"✅ SUCCESS! Frame size: {w}x{h}")
                    
                    # Try to read a few more frames
                    print(f"\n📹 Reading test frames...")
                    for i in range(5):
                        ret, frame = cap.read()
                        if ret:
                            print(f"  Frame {i+1}: ✅ OK")
                        else:
                            print(f"  Frame {i+1}: ❌ Failed")
                        time.sleep(0.5)
                    
                    cap.release()
                    print(f"\n{'='*60}")
                    print(f"✅ RTSP CONNECTION SUCCESSFUL!")
                    print(f"{'='*60}\n")
                    return True
                else:
                    print("❌ Failed to read frame")
            else:
                print("⏳ Not opened yet")
            
            time.sleep(1.5)
        
        cap.release()
        print(f"❌ Failed with {backend_name} backend")
    
    print(f"\n{'='*60}")
    print(f"❌ ALL CONNECTION ATTEMPTS FAILED")
    print(f"{'='*60}")
    print(f"\nPossible issues:")
    print(f"  1. Camera is offline or not accessible")
    print(f"  2. Incorrect RTSP URL format")
    print(f"  3. Network/firewall blocking connection")
    print(f"  4. Authentication credentials incorrect")
    print(f"  5. Camera doesn't support RTSP protocol")
    print(f"\n")
    return False


if __name__ == "__main__":
    # Test with the RTSP URL from the screenshots
    test_url = "rtsp://192.168.1.72:554/cam/realmonitor?channel=4&subtype=0&unicast=true&proto=Onvif"
    
    print("\n" + "="*60)
    print("RTSP Connection Test Utility")
    print("="*60)
    
    # Allow user to input custom URL
    user_input = input(f"\nPress Enter to test default URL, or paste your RTSP URL: ").strip()
    if user_input:
        test_url = user_input
    
    test_rtsp(test_url)
