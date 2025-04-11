import time
import random

def upload_review(sb,data):
    try:
        sb.click("img[alt='select to rate item five star.']",timeout=10)
        time.sleep(random.uniform(3, 6))
        sb.click("#reviewText",timeout=10)
        time.sleep(random.uniform(3, 6))   
        sb.type("#reviewText",data["Review"])
        time.sleep(random.uniform(3, 6))
        sb.click("#reviewTitle",timeout=10)
        time.sleep(random.uniform(3, 6))
        sb.type("#reviewTitle",data["Headline"])
        time.sleep(random.uniform(3, 6))
        sb.click('input[type="submit"].a-button-input',timeout=10)
        time.sleep(random.uniform(3, 6))
        return True
    except Exception as e:
        print(e)
        return False

