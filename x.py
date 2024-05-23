import pathlib
from bottle import request, response
import re
import sqlite3
from icecream import ic
import requests
import json
import smtplib
from email.mime.text import MIMEText

ITEMS_PER_PAGE = 2
COOKIE_SECRET = "41ebeca46f3b-4d77-a8e2-554659075C6319a2fbfb-9a2D-4fb6-Afcad32abb26a5e0"


##############################
def dict_factory(cursor, row):
    col_names = [col[0] for col in cursor.description]
    return {key: value for key, value in zip(col_names, row)}

##############################

def db():
    db = sqlite3.connect(str(pathlib.Path(__file__).parent.resolve())+"/company.db")  
    db.row_factory = dict_factory
    return db


##############################
def arango(query, type = "cursor"):
    try:
        url = f"http://arangodb:8529/_api/{type}"
        res = requests.post( url, json = query )
        ic(res)
        ic(res.text)
        return res.json()
    except Exception as ex:
        print("#"*50)
        print(ex)
    finally:
        pass




##############################
def no_cache():
    response.add_header("Cache-Control", "no-cache, no-store, must-revalidate")
    response.add_header("Pragma", "no-cache")
    response.add_header("Expires", 0)    


##############################
def validate_user_logged():
    user = request.get_cookie("user", secret=COOKIE_SECRET)
    if user is None: raise Exception("user must login", 400)
    return user


##############################

def validate_logged():
    # Prevent logged pages from caching
    response.add_header("Cache-Control", "no-cache, no-store, must-revalidate")
    response.add_header("Pragma", "no-cache")
    response.add_header("Expires", "0")  
    user_id = request.get_cookie("id", secret = COOKIE_SECRET_KEY)
    if not user_id: raise Exception("***** user not logged *****", 400)
    return user_id


##############################

USER_ID_LEN = 32
USER_ID_REGEX = "^[a-f0-9]{32}$"

def validate_user_id():
	error = f"user_id invalid"
	user_id = request.forms.get("user_id", "").strip()      
	if not re.match(USER_ID_REGEX, user_id): raise Exception(error, 400)
	return user_id


##############################

EMAIL_MAX = 100
EMAIL_REGEX = "^(([^<>()[\]\\.,;:\s@\"]+(\.[^<>()[\]\\.,;:\s@\"]+)*)|(\".+\"))@((\[[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\])|(([a-zA-Z\-0-9]+\.)+[a-zA-Z]{2,}))$"

def validate_email():
    error = f"email invalid"
    user_email = request.forms.get("user_email", "").strip()
    if not re.match(EMAIL_REGEX, user_email): raise Exception(error, 400)
    return user_email

##############################

USER_USERNAME_MIN = 2
USER_USERNAME_MAX = 20
USER_USERNAME_REGEX = "^[a-z]{2,20}$"

def validate_user_username():
    error = f"username {USER_USERNAME_MIN} to {USER_USERNAME_MAX} lowercase english letters"
    user_username = request.forms.get("user_username", "").strip()
    if not re.match(USER_USERNAME_REGEX, user_username): raise Exception(error, 400)
    return user_username

##############################

USER_NAME_MIN = 2
USER_NAME_MAX = 20
USER_REGEX = "^.{2,20}$"
def validate_user_name():
    error = f"name {USER_NAME_MIN} to {USER_NAME_MAX} characters"
    user_name = request.forms.get("user_name", "").strip()
    if not re.match(USER_USERNAME_REGEX, user_name): raise Exception(error, 400)
    return request.forms.name

##############################

LAST_NAME_MIN = 2
LAST_NAME_MAX = 20

def last_name():
  error = f"last_name {LAST_NAME_MIN} to {LAST_NAME_MAX} characters"
  user_last_name = request.forms.get("user_last_name").strip()
  if not re.match(USER_USERNAME_REGEX, user_last_name): raise Exception(error, 400)
  return user_last_name

##############################

USER_PASSWORD_MIN = 6
USER_PASSWORD_MAX = 50
USER_PASSWORD_REGEX = "^.{6,50}$"

def validate_password():
    error = f"password {USER_PASSWORD_MIN} to {USER_PASSWORD_MAX} characters"
    user_password = request.forms.get("user_password", "").strip()
    if not re.match(USER_PASSWORD_REGEX, user_password): raise Exception(error, 400)
    return user_password

##############################

def confirm_password():
  error = f"password and confirm_password do not match"
  user_password = request.forms.get("user_password", "").strip()
  user_confirm_password = request.forms.get("user_confirm_password", "").strip()
  if user_password != user_confirm_password: raise Exception(error, 400)
  return user_confirm_password

##############################
def setup_collection():
    try:
        # Check if the 'items' collection exists using the HTTP API
        url = "http://arangodb:8529/_api/collection/items"
        res = requests.get(url)
        ic(res)
        ic(res.text)

        if res.status_code == 200:
            ic("Collection 'items' already exists.")
            return

        # Create the 'items' collection
        url = "http://arangodb:8529/_api/collection"
        collection_data = {"name": "items"}
        res = requests.post(url, json=collection_data)
        ic(res)
        ic(res.text)

        if res.status_code == 200:
            # Insert items.json data into the 'items' collection
            with open("items.json", "r") as f:
                items = json.load(f)

            for item in items:
                query = {
                    "query": "INSERT @item INTO items",
                    "bindVars": {"item": item}
                }
                arango(query)

            ic("Collection 'items' created and populated with data.")
        else:
            ic("Failed to create the 'items' collection.")
    except Exception as ex:
        print("#" * 50)
        print(ex)
    finally:
        pass

##############################
def send_reset_email(email, key):
    from_email = 'joeybidenisbased@gmail.com'
    from_password = 'tdvi euik qgsa bzdf'

    domain = request.urlparts.scheme + "://" + request.urlparts.netloc
    reset_link = f"{domain}/reset-password/{key}"
    msg = MIMEText(f"Click the link to reset your password: {reset_link}")
    msg["Subject"] = "Password Reset Request"
    msg["From"] = from_email
    msg["To"] = email

    server = smtplib.SMTP('smtp.gmail.com:587')
    server.ehlo('Gmail')
    server.starttls()
    server.login(from_email, from_password)
    server.sendmail(msg["From"], [msg["To"]], msg.as_string())

##############################