import cv2 as cv
import numpy as np
import pyautogui
import time

class FishingAgent:
    def __init__(self, main_agent):
        self.main_agent = main_agent
        self.fishing_target = cv.imread("src\\python_fishbot\\fishing\\assets\\fishing_target2.jpg")
        self.fishing_thread = None
        
    def cast_lure(self):
        print("Casting...")
        # pyautogui.press('1')
        pyautogui.hotkey('ctrl','f')
        time.sleep(3)
        self.find_lure()
    
    def find_lure(self):
        if self.main_agent.current_image is not None:
            current_image = self.main_agent.current_image
            lure_location = cv.matchTemplate(
                current_image, 
                self.fishing_target,
                cv.TM_CCOEFF_NORMED)
            lure_location_arr = np.array(lure_location)
            cv.imshow("Match Template", lure_location_arr)
            cv.waitKey(0)
            min_val, max_val, min_loc, max_loc = cv.minMaxLoc(lure_location_arr)
            print(max_loc)
            
            self.move_to_lure(max_loc)
    
    def move_to_lure(self, max_loc):
        pyautogui.moveTo(max_loc[0], max_loc[1], duration = 1, tween = pyautogui.easeOutQuad)
        self.watch_lure(max_loc)
    
    def watch_lure(self, max_loc):
        watch_time = time.time()
        while True:
            pixel = self.main_agent.current_imageHSV[max_loc[1], max_loc[0]]
            print(pixel)
            
            if self.main_agent.zone == "Feralas" and self.main_agent.time == "night":
                if pixel[0] >= 60:
                    print("Bite detected!")
                    break
            
            if self.main_agent.zone == "Darkmoon Island" and self.main_agent.time == "midnight":
                if pixel[0] >= 80:
                    print("Bite detected!")
                    break
            
            if time.time() - watch_time >= 10:
                break
        self.pull_line()
    
    def pull_line(self):
        print("Pulling line")
        pyautogui.hotkey('ctrl','f')
        time.sleep(0.010)
    
    def run(self):
        while True:
            self.cast_lure()
            time.sleep(5)