import time
from threading import Thread

import cv2 as cv
import numpy as np
import pyautogui
from PIL import ImageGrab

from .fishing.fishing_agent import FishingAgent


class MainAgent:
    def __init__(self):
        self.agents = []
        self.fishing_thread = None
        self.current_image = None  # latest full-screen frame, BGR numpy array


def update_screen(agent):
    t0 = time.time()
    fps_report_delay = 5
    fps_report_time = time.time()
    while True:
        # Build the frame in a LOCAL variable and publish it once, so other threads never see a
        # half-converted image (it used to briefly hold a PIL image -> "'Image' object is not
        # subscriptable").
        agent.current_image = cv.cvtColor(np.array(ImageGrab.grab()), cv.COLOR_RGB2BGR)

        ex_time = time.time() - t0
        if time.time() - fps_report_time >= fps_report_delay:
            print("FPS: " + str(1 / ex_time))
            fps_report_time = time.time()
        t0 = time.time()
        time.sleep(0.005)


def print_menu():
    print("Enter command:")
    print("\tS\tStart the screen capture.")
    print("\tF\tStart the fishing agent (Ctrl+C stops it).")
    print("\tQ\tQuit.")


def main():
    """Entry point: `uv run python-fishbot` (see [project.scripts] in pyproject.toml)."""
    main_agent = MainAgent()
    capture_started = False

    print_menu()
    while True:
        user_input = input().lower().strip()

        if user_input == "s":
            if capture_started:
                print("Screen capture is already running.")
                continue
            Thread(target=update_screen, args=(main_agent,),
                   name="update screen thread", daemon=True).start()
            capture_started = True
            print("Thread started")
        elif user_input == "f":
            if main_agent.current_image is None:
                print("Start the screen capture first (S), then try again.")
                continue
            try:
                FishingAgent(main_agent).run()
            except KeyboardInterrupt:
                print("\nFishing stopped (Ctrl+C).")
            except pyautogui.FailSafeException:
                print("\nFishing stopped (mouse moved to a screen corner).")
            print_menu()
        elif user_input == "q":
            break
        else:
            print("Input error.")
            print_menu()

    print("Done.")


if __name__ == "__main__":
    main()