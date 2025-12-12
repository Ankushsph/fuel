"""
Simple RTSP test - paste your RTSP URL and run
"""
import cv2
import time

# TEST RTSP URLS - These are publicly available test streams
TEST_URLS = [
    # Public test stream 1
    "rtsp://wowzaec2demo.streamlock.net/vod/mp4:BigBuckBunny_115k.mp4",
    
    # Your camera URL from screenshot
    "rtsp://192.168.1.72:554/cam/realmonitor?channel=4&subtype=0&unicast=true&proto=Onvif",
]

def quick_test(url):
    print(f"\n{'='*70}")
    print(f"Testing: {url}")
    print(f"{'='*70}")
    
    cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 20000)
    
    print("Waiting for connection (up to 20 seconds)...")
    
    for i in range(10):
        if cap.isOpened():
            ret, frame = cap.read()
            if ret and frame is not None:
                h, w = frame.shape[:2]
                print(f"✅ SUCCESS! Connected and reading frames ({w}x{h})")
                
                # Read 5 frames to verify stability
                success_count = 0
                for j in range(5):
                    ret, frame = cap.read()
                    if ret:
                        success_count += 1
                    time.sleep(0.2)
                
                print(f"✅ Read {success_count}/5 test frames successfully")
                cap.release()
                return True
        
        print(f"  Attempt {i+1}/10...")
        time.sleep(2)
    
    print("❌ FAILED - Could not connect")
    cap.release()
    return False

if __name__ == "__main__":
    print("\n" + "="*70)
    print("RTSP CONNECTION TEST")
    print("="*70)
    
    print("\n📋 Available test URLs:")
    for i, url in enumerate(TEST_URLS, 1):
        print(f"{i}. {url}")
    
    print("\n" + "="*70)
    choice = input("Enter number to test (or paste your own RTSP URL): ").strip()
    
    if choice.startswith("rtsp://"):
        test_url = choice
    elif choice.isdigit() and 1 <= int(choice) <= len(TEST_URLS):
        test_url = TEST_URLS[int(choice) - 1]
    else:
        print("Invalid choice, testing first URL...")
        test_url = TEST_URLS[0]
    
    result = quick_test(test_url)
    
    if result:
        print("\n✅ RTSP URL IS WORKING!")
        print(f"Use this URL in your application: {test_url}")
    else:
        print("\n❌ RTSP URL NOT WORKING")
        print("Try the public test stream first:")
        print("rtsp://wowzaec2demo.streamlock.net/vod/mp4:BigBuckBunny_115k.mp4")
    
    input("\nPress Enter to exit...")
