import time
from threading import Thread

import cv2 as cv
import numpy as np
from PIL import ImageGrab

from .fishing.fishing_agent import FishingAgent


class MainAgent:
    def __init__(self):
        self.agents = []
        self.fishing_thread = None
        self.current_image = None  # latest full-screen frame, BGR numpy array
        # zone / time / current_imageHSV are gone: the fishing agent no longer needs them.


def update_screen(agent):
    t0 = time.time()
    fps_report_delay = 5
    fps_report_time = time.time()
    while True:
        # Build the frame in a LOCAL variable and publish it once. Before, current_image briefly held
        # a PIL image between the two assignments, and the fishing thread could read it -> crash
        # ("'Image' object is not subscriptable").
        frame = cv.cvtColor(np.array(ImageGrab.grab()), cv.COLOR_RGB2BGR)
        agent.current_image = frame

        ex_time = time.time() - t0
        if time.time() - fps_report_time >= fps_report_delay:
            print("FPS: " + str(1 / ex_time))
            fps_report_time = time.time()
        t0 = time.time()
        time.sleep(0.005)


def print_menu():
    print("Enter command:")
    print("\tS\tStart the main agent (screen capture).")
    print("\tF\tStart the fishing agent.")
    print("\tQ\tQuit.")


if __name__ == "__main__":
    main_agent = MainAgent()

    print_menu()
    while True:
        user_input = input().lower().strip()

        if user_input == "s":
            Thread(target=update_screen, args=(main_agent,),
                   name="update screen thread", daemon=True).start()
            print("Thread started")
        elif user_input == "f":
            if main_agent.current_image is None:
                print("Start the screen capture first (S).")
                continue
            FishingAgent(main_agent).run()
        elif user_input == "q":
            cv.destroyAllWindows()
            break
        else:
            print("Input error.")
            print_menu()

    print("Done.")