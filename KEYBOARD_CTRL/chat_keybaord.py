import keyboard
import time 

count = 10
for i in range(count):
    time.sleep(1/count)
    print(f'Waiting ... {(i/count)*100}%')

keyboard.press_and_release('space')