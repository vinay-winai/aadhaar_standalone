import easyocr
import pytesseract
from PIL import Image,ImageFilter
from cv2 import cv2
import os
import re
import json
import datetime

year = datetime.date.today().year
pytesseract.pytesseract.tesseract_cmd = r'C:\\Program Files\\Tesseract-OCR\\tesseract.exe'
    
def aadhaar_read_data(text,side):
    """text: str \n
    side: str ,allowed values: ('front','back') \n
    return type: DICT
    """
    # res=text.split()
    name = None
    dob = None
    yob = None
    aadhaar_number=None
    gender = None
    address = None
    text1 = []
    # used to get name when is above this line, if dob is missing it is assigned to yob
    dob_line = None 
    lines = text.split('\n')
    idx = 0
    aadhaar_pattern = r".*(\d{4}).(\d{4}).(\d{4}).*"
    aadhaar_match = None
    
    for line in lines:
        # line.replace('\n','')
        line.strip()
        # aadhaar identifying
        if not aadhaar_match:
            aadhaar_match = re.search(aadhaar_pattern, line)

        if line:
            for char in line:
                if char.isalnum():
                    text1.append(line)
                    idx+=1
                    break

        # dob and yob
        if not dob_line:
            dob_match = re.search(r"(\d{2}\D{1}\d{2}\D{1}\d{4})", line)
            if dob_match:
                temp = dob_match.group(1)
                year_of_birth = int(temp[-4:])
                if year-year_of_birth>=18:
                    yob = year_of_birth
                    dob = temp
                    dob_line = idx-1
        
        #yob only
        if not (dob_line or yob):
            line = line[-10:]
            year_of_birth = ""
            for i in line:
                if i.isdigit():
                    year_of_birth+=i
            if len(year_of_birth) == 4 and year-int(year_of_birth)>=18 and int(year_of_birth)>1947:
                yob = year_of_birth
                dob_line = idx-1 

    # gender
    if 'female' in text.lower():
        gender = "FEMALE"
    elif 'male' in text.lower():
        gender = "MALE"
    else:
        gender = "OTHER"
    
    
    try:
        if dob_line:
            # name 
            name = re.sub(r"[^A-Za-z\s]+", "",text1[dob_line-1]).strip() 
        # Cleaning Adhaar number details        
        if aadhaar_match:
            aadhaar_number = f"{aadhaar_match.group(1)}_{aadhaar_match.group(2)}_{aadhaar_match.group(3)}"
        # address
        # cropping issue date has significant impact
        if "Address:" in text1:
            pin = 0
            address = text.split("Address:")[1]
            for cnt,i in enumerate(address):
                if i.isdigit():
                    pin+=1
                if pin==6:
                    address = address[:cnt+1]
                    break
                if not i.isdigit():
                    pin=0                    
            # address = address.replace("\n",'')
            if pin != 6:
                address = "not clear"
    
    except Exception as e:
        print(e)

    # make diff json for front and back
    data = {}
    if side == "front":
        data["Name"] = name
        data["Date of Birth"] = dob
        data["Year of Birth"] = yob
        data["Gender"] = gender
        data["Aadhaar Number"] = aadhaar_number
    if side == "back":
        data["Address"] = address
    return data

def aadhaar_extraction(front,back):
    def aadhaar_side(image,side):
        # image processing and enhancement
        img =  Image.open(image)
        img.save("./img.png")
        img = cv2.imread("./img.png")
        img = cv2.resize(img, None, fx=2, fy=2,interpolation=cv2.INTER_CUBIC)
        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        img  = Image.fromarray(img)
        width, height = img.size
        img = img.crop((width*.02, height*0.1, width, height))

        # back with qr
        if side == 'back':
            img = img.crop((width*.02, height*0.1, width, height)) # width .01 to .04
        # only back eng right
        # img = img.crop((width*0.49, height*.15, width, height))
        # full front double
        # img = img.crop((width*.5, 0, width, height))

        # image sharpening
        img = img.filter(ImageFilter.UnsharpMask(radius=2, percent=250, threshold=3))
        
        # ocr
        text = pytesseract.image_to_string(img)
        data = aadhaar_read_data(text,side)

        #neural_net
        def call_easy_ocr():
            print("Entered easy_ocr")
            reader = easyocr.Reader(['en'])
            text = reader.readtext("./img.png",detail=0,batch_size = 4,allowlist="0123456789 ")
            adn = ""
            for line in text:
                if len(adn)==15:
                    return adn[:-1]
                if len(line)==4:
                    adn+=line+'_'
                    continue
                if adn:
                    adn = ""
                data = re.search(r".*(\d{4}).(\d{4}).(\d{4}).*", line)
                if data:
                    return f"{data.group(1)}_{data.group(2)}_{data.group(3)}"
            print("Easy_ocr failed to extract Aadhaar number")
        
        if side=='front' and not data["Aadhaar Number"]:
            data["Aadhaar Number"] = call_easy_ocr()
        
        # delete img
        os.remove("./img.png")
        return data
    
    side = 'front'
    errors = ''
    front_result = {}
    back_result = {}
    try:
        front_result = aadhaar_side(front,side)
    except Exception as e:
        print(str(e))
        errors+= "front image failed. "
    side = 'back'
    try:
        back_result = aadhaar_side(back,side)
    except Exception as e:
        print(str(e))
        errors+= "back image failed. "
    front_result.update(back_result)
    return {"data":json.dumps(front_result),"errors":errors}

def extract_aadhaar(front,back):
    """
    Extracts aadhaar.

    Parameters:
    param1 (str): front image path.
    param2 (str): back image path.

    Returns:
    str: json of extracted data.
    """
    front = front
    back = back
    result = aadhaar_extraction(front,back)
    if result.get("errors"):
        return str(result["data"])+str(result["errors"]) 
    return str(result["data"])

print(extract_aadhaar("front.jpg","back.jpg"))