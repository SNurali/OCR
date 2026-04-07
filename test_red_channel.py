import cv2
import numpy as np

img = cv2.imread("debug_input_image.jpg")
if img is not None:
    b, g, r = cv2.split(img)
    # R channel makes red background white, but keeps black text black
    # This might wipe out green background headers though if they are pure green, but let's see
    cv2.imwrite("debug_r_channel.jpg", r)
    
    # We can also do a mix: take the brightest channel for background, but text is black in all
    # min_channels = np.min(img, axis=2) 
    # max_channels = np.max(img, axis=2) # red is bright here, green is bright here, black is dark here
    
    cv2.imwrite("debug_max_channels.jpg", np.max(img, axis=2))
