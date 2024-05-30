import smtplib, ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from bottle import default_app, put, delete, get, post, request, response, run, static_file, template
import x, re
from icecream import ic
import bcrypt
import json
import credentials
import uuid
import random
import string
from send_email import send_verification_email
import os
import time

def generate_verification_code():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=6))

sessions = {}

def validate_user_logged():
    user_session_id = request.get_cookie("user_session_id")
    if user_session_id in sessions:
        return True
    else:
        return False
    
def validate_user_role():
    user_role = request.get_cookie("role")
    if user_role == "partner":
        return True
    else:
        return False

##############################
@get("/app.css")
def _():
    return static_file("app.css", ".")


##############################
@get("/<file_name>.js")
def _(file_name):
    return static_file(file_name+".js", ".")


##############################
@get("/test")
def _():
    return [{"name":"one"}]

##############################
@get("/images/<item_splash_image>")
def serve_image(item_splash_image):
    # Check if the requested image exists in the current directory
    if os.path.exists(os.path.join("images", item_splash_image)):
        # Serve the requested image from the current directory
        return static_file(item_splash_image, "images")
    else:
        # Serve the image from the uploads directory if it's not found in the current directory
        return static_file(item_splash_image, root="uploads/images")

##############################
@get("/")
def home():
    try:
        x.setup_users()
        x.setup_collection()
        # Fetch items from the ArangoDB collection 'items'
        query = {
            "query": "FOR item IN items LET isBlocked = HAS(item, 'blocked') ? item.blocked : false UPDATE item WITH { blocked: isBlocked } IN items SORT item.item_created_at LIMIT @limit RETURN item",
            "bindVars": {"limit": x.ITEMS_PER_PAGE}
        }
        result = x.arango(query)
        items = result.get("result", [])
        ic(items)
        is_logged = validate_user_logged()
        print("user is logged in?: ")
        print(is_logged)
        is_role = validate_user_role()
        print("is user a partner?: ")
        print(is_role)

        return template("index.html", items=items, mapbox_token=credentials.mapbox_token, is_logged=is_logged, is_role=is_role)
    except Exception as ex:
        ic(ex)
        return str(ex)
    finally:
        pass

@get("/signup")
def _():
    try:
        is_role = validate_user_role()
        return template("signup_wu_mixhtml.html", is_role=is_role)
    except Exception as ex:
        print("there was a problem loading the page")
        print(ex)
        return ex

@post("/signup")
def _():
    try:
        username = x.validate_user_username() # validation of username using method from x.py file
        print("username received: " + username)
        email = x.validate_email() # validation of email using method from x.py file
        print("email received: " + email)
        password = x.validate_password()
        print("password received: " + password)
        verification_code = generate_verification_code()
        selected_option = request.forms.get("option")
        print(selected_option)
        ic(username) # this is ice cream it displays error codes when something goes wrong
        ic(password)
        ic(email) # this is ice cream it displays error codes when something goes wrong
        
        res = {
            "query": "FOR user IN users FILTER user.user_email == @user_email RETURN user",
            "bindVars": {"user_email": email}
        }
        query_result = x.arango(res)
        users = query_result.get("result", [])

        if users:
            for user in users:
                user_email = user.get("user_email")

                if user_email == email:
                    return "user already exists"
        
        
        # Hash the password using bcrypt
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        user = {"username": username, 
                "user_email": email, 
                "user_password": hashed_password.decode('utf-8'), 
                "role": selected_option, 
                "verification_code": verification_code, 
                "verified": False,
                "is_deleted": False} # Save the hashed password
        res = {"query": "INSERT @doc IN users RETURN NEW", "bindVars": {"doc": user}} # inserts a user via AQL query language, via the db method in the x.py file 
        item = x.arango(res)
        send_verification_email(email, verification_code)
        response.status = 303
        response.set_header('Location', '/login')
        return
    except Exception as ex:
        ic(ex)
        if "user_name" in str(ex):
            return f"""
            <template mix-target="#message">
                {ex.args[1]}
            </template>
            """            
    finally:
        pass

@get("/verify")
def verify():
    try:
        verification_code = request.query.code
        res = {
            "query": "FOR user IN users FILTER user.verification_code == @code RETURN user",
            "bindVars": {"code": verification_code}
        }
        query_result = x.arango(res)
        users = query_result.get("result", [])

        if not users:
            return "Invalid verification code"
        
        user = users[0]
        user["verified"] = True
        update_res = {
            "query": "UPDATE @user WITH {verified: true} IN users RETURN NEW",
            "bindVars": {"user": user}
        }
        x.arango(update_res)

        return "You email has been verified. You can now log in at <a href='/login'>Login</a>."
    except Exception as ex:
        print("An error occurred:", ex)
        return "An error occurred while verifying your email."
    finally:
        pass
    
@post("/users")
def _():
    try:
        username = x.validate_user_username() # validation of username using method from x.py file
        email = x.validate_email() # validation of user_last_name using method from x.py file
        ic(username) # this is ice cream it displays error codes when something goes wrong
        ic(email) # this is ice cream it displays error codes when something goes wrong
        user = {"username":username, "email":email} # defines a user by saving user as a document
        res = {"query":"INSERT @doc IN users RETURN NEW", "bindVars":{"doc":user}} # inserts a user via AQL query language, via the db method in the x.py file
        item = x.arango(res)
        return item
    except Exception as ex:
        ic(ex)
        if "username" in str(ex):
            return f"""
            <template mix-target="#message">
                {ex.args[1]}
            </template>
            """            
    finally:
        pass


##############################
@get("/items/page/<page_number>")
def _(page_number):
    try:
        page_number = int(page_number)
        if page_number < 1:
            raise ValueError("Page number must be greater than 0")
        
        offset = (page_number - 1) * x.ITEMS_PER_PAGE
        query = {
            "query": "FOR item IN items SORT item.item_created_at LIMIT @offset, @limit RETURN item",
            "bindVars": {
                "offset": offset,
                "limit": x.ITEMS_PER_PAGE
            }
        }
        result = x.arango(query)
        items = result.get("result", [])
        ic(items)

        html = ""
        is_logged = False
        try:
            x.validate_user_logged()
            is_logged = True
        except:
            pass

        for item in items:
            html += template("_item", item=item, is_logged=is_logged)
        
        next_page = page_number + 1
        btn_more = template("__btn_more", page_number=next_page)
        if len(items) < x.ITEMS_PER_PAGE:
            btn_more = ""

        return f"""
        <template mix-target="#items" mix-bottom>
            {html}
        </template>
        <template mix-target="#more" mix-replace>
            {btn_more}
        </template>
        <template mix-function="test">{json.dumps(items)}</template>
        """
    except Exception as ex:
        ic(ex)
        return "ups..."
    finally:
        pass


##############################
@get("/login")
def login():
    x.no_cache()
    is_role = validate_user_role()
    return template("login_wu_mixhtml.html", is_role=is_role)

sessions = {}

@post("/login")
def login_post():
    try:
        user_email = request.forms.get("user_email")
        print(user_email)
        user_password = request.forms.get("user_password")
        print(user_password)

        res = {
            "query": "FOR user IN users FILTER user.user_email == @user_email RETURN user",
            "bindVars": {"user_email": user_email}
        }
        query_result = x.arango(res)
        users = query_result.get("result", [])

        if users:
            for user in users:
                user_verified_status = user.get("verified")
                print(user_verified_status)

                if user_verified_status == True:
                    stored_hashed_password = user.get("user_password")
                    user_role = user.get("role")
                    user_id = user.get("_key")
                    
                    # Verify the provided password with the stored hashed password
                    if bcrypt.checkpw(user_password.encode('utf-8'), stored_hashed_password.encode('utf-8')):
                        user_session_id = str(uuid.uuid4())
                        sessions[user_session_id] = user
                        print("#"*30)
                        print(sessions)
                        response.set_cookie("user_session_id", user_session_id)
                        response.set_cookie("role", user_role)
                        response.set_cookie("user_id", user_id)
                        response.status = 303
                        response.set_header('Location', '/')
                        return
                else:
                    return "Only Verified users can login"
        response.status = 303
        response.set_header('Location', '/login')
        return
        # return "login failed - incorrect email or password"
    except Exception as ex:
        print("An error occurred:", ex)
        return "An error occurred while processing your request"


##############################
@get("/profile")
def _():
    try:
        user_session_id = request.get_cookie("user_session_id")
        if user_session_id not in sessions:
            return "You are not logged in"
            response.set_header('Location', '/login')
            return
        
        user = sessions[user_session_id]
        is_role = validate_user_role()
        return template("user_profile", user=user, is_role=is_role)
    except Exception as ex:
        ic(ex)
        return {"error": str(ex)}

##############################

@post("/update_profile")
def update_profile():
    try:
        user_session_id = request.get_cookie("user_session_id")
        if user_session_id not in sessions:
            response.status = 303
            response.set_header('Location', '/login')
            return
        
        user = sessions[user_session_id]

        username = request.forms.get("user_name")    
        user_email = request.forms.get("user_email")
        user_password = request.forms.get("user_password")

        if user_password:
            hashed_password = bcrypt.hashpw(user_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        else:
            hashed_password = user["user_password"]

        user["username"] = username
        user["user_email"] = user_email
        user["user_password"] = hashed_password

        update_query = {
            "query": """
                FOR user IN users
                FILTER user._key == @key
                UPDATE user WITH { 
                    username: @username, 
                    user_email: @user_email, 
                    user_password: @user_password 
                } IN users    
                RETURN NEW
            """,
            "bindVars": {
                "key": user["_key"],
                "username": username,
                "user_email": user_email,
                "user_password": hashed_password
            }
        }

        result = x.arango(update_query)
        updated_user = result.get("result", [])[0]
        sessions[user_session_id] = updated_user
        response.status = 303
        response.set_header('Location', '/profile')
        return
    except Exception as ex:
        ic(ex)
        return str(ex)
    
@get("/partner_properties")
def _():
    return template("_youreproperty.html")

##############################
@post("/verification_email_delete")
def send_verification_email_delete():
    user_email = request.forms.get("user_email")
    print(user_email)
    user_password = request.forms.get("user_password")
    print(user_password)
    sender_email = "skroyer09@gmail.com"
    password = "vkxq xwhj yaxn rqjs"

    message = MIMEMultipart("alternative")
    message["Subject"] = "Verify your email address"
    message["From"] = sender_email
    message["To"] = user_email


    text = f"""\
    Hi,
    Please verify deletion of your account by clicking the link
    """
    html = f"""\
    <html>
      <body>
        <p>Hi,<br>
          Please verify deletion of your account by clicking the link below:<br>
          <a href="http://127.0.0.1/Verify_delete?code={user_email}">Verify Email</a>
        </p>
      </body>
    </html>
    """

    # Turn these into plain/html MIMEText objects
    part1 = MIMEText(text, "plain")
    part2 = MIMEText(html, "html")

    # Add HTML/plain-text parts to MIMEMultipart message
    # The email client will try to render the last part first
    message.attach(part1)
    message.attach(part2)

    # Create secure connection with server and send email
    context = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
        server.login(sender_email, password)
        server.sendmail(sender_email, user_email, message.as_string())
    return home()

@get("/Verify_delete")
def login_post():
    try:
        user_email = request.query.code

        res = {
            "query": "FOR user IN users FILTER user.user_email == @user_email UPDATE user WITH { is_deleted: true } IN users",
            "bindVars": {"user_email": user_email}
        }
        query_result = x.arango(res)
        users = query_result.get("result", [])

        return "You account has been deleted. You can go back to the homepage now <a href='/'>Homepage</a>."
        # return "login failed - incorrect email or password"
    except Exception as ex:
        print("An error occurred:", ex)
        return "An error occurred while processing your request"

# ##############################
# @get("/profile")
# def _():
#     try:
#         x.no_cache()
#         x.validate_user_logged()
#         db = x.db()
#         q = db.execute("SELECT * FROM items ORDER BY item_created_at LIMIT 0, ?", (x.ITEMS_PER_PAGE,))
#         items = q.fetchall()
#         ic(items)    
#         return template("profile.html", is_logged=True, items=items)
#     except Exception as ex:
#         ic(ex)
#         response.status = 303 
#         response.set_header('Location', '/login')
#         return
#     finally:
#         if "db" in locals(): db.close()


##############################
@get("/logout")
def _():
    user_session_id = request.get_cookie("user_session_id")
    if user_session_id in sessions:
        del sessions[user_session_id]
    response.delete_cookie("user_session_id")
    return home()


##############################
@get("/api")
def _():
    return x.test()

##############################
@post("/toogle_item_block")
def _():
    try:
        item_id = request.forms.get("item_id", '')
        return f"""
        <template mix-target="[id='{item_id}']" mix-replace>
            xxxxx
        </template>
        """
    except Exception as ex:
        ic(ex)
        return ex
    finally:
        pass
    
##############################
@get("/arango/items")
def _():
    try:
        q = {"query":"FOR item IN items LIMIT 1 RETURN item"}
        items = x.arango(q)
        return items
    except Exception as ex:
        ic(ex)
        return ex
    finally:
        pass

##############################
@delete("/arango/items/<key>")
def _(key):
    try:
        dynamic = {"_key": key}
        q = {"query":"REMOVE @dynamic IN items RETURN OLD", 
             "bindVars":{
                            "dynamic": dynamic
                        }
            }
        items = x.arango(q)
        return items
    except Exception as ex:
        ic(ex)
        return ex
    finally:
        pass

##############################
@post("/arango/items")
def _():
    try:
        # TODO: validate
        item_name = request.forms.get("item_name", "")
        item = {"name":item_name}
        q = {   "query": "INSERT @item INTO items RETURN NEW",
                "bindVars":{"item":item}
             }
        item = x.arango(q)
        return item
    except Exception as ex:
        ic(ex)
        return ex
    finally:
        pass


##############################
@put("/arango/items/<key>")
def _(key):
    try:
        # TODO: validate
        item_name = request.forms.get("item_name", "")
        item_key = { "_key" : key }
        item_data = { "name" : item_name }
        q = {   "query": "UPDATE @item_key WITH @item_data IN items RETURN NEW",
                "bindVars":{"item_key":item_key, "item_data":item_data}
             }
        item = x.arango(q)
        return item
    except Exception as ex:
        ic(ex)
        return ex
    finally:
        pass

@get("/rooms/<id>")
def _(id):
    try:
        item_key_data = id
        item_key_name = "_key"
        query = {
            "query": "FOR item IN items FILTER item[@key_name] == @key_data RETURN item",
            "bindVars": {"key_name": item_key_name, "key_data": item_key_data}
        }
        result = x.arango(query)
        items = result.get("result", [])
        if not items:
            response.status = 404
            return {"error": "Item not found"}
        
        item = items[0]  # There should be only one item with the specified ID
        title = f"Item {id}"
        ic(item)
        is_logged = validate_user_logged()
        print(is_logged)
        is_role = validate_user_role()
        return template("rooms",
                        id=id, 
                        title=title,
                        item=item, is_logged=is_logged, is_role=is_role)
    except Exception as ex:
        ic(ex)
        return {"error": str(ex)}
    
##############################
@get("/users")
def _():
    try:
        active_query = {"query": """
                                    FOR user IN users 
                                    LET isBlocked = HAS(user, 'blocked') ? user.blocked : false
                                    FILTER isBlocked != true 
                                    UPDATE user WITH { blocked: isBlocked } IN users 
                                    RETURN NEW
                            """}
        blocked_query = {"query": "FOR user IN users FILTER user.blocked == true RETURN user"}
        
        active_users = x.arango(active_query)
        blocked_users = x.arango(blocked_query)
        
        ic(active_users)
        ic(blocked_users)
        
        return template("users", active_users=active_users["result"], blocked_users=blocked_users["result"])
    except Exception as ex:
        ic(ex)
        return {"error": str(ex)}

##############################
@get("/users/<key>")
def get_user(key):
    try:
        q = {"query": "FOR user IN users FILTER user._key == @key RETURN user", "bindVars": {"key": key}}
        users = x.arango(q)
        if not users:
            response.status = 404
            return {"error": "User not found"}
        user = users[0]  # ArangoDB returns a list of results
        ic(user)
        return template("index", users=users["result"])
    except Exception as ex:
        ic(ex)
        return {"error": str(ex)}
##############################
@delete("/users/<key>")
def _(key):
    try:
        # Regex validation for key
        if not re.match(r'^[1-9]\d*$', key):
            return "Invalid key format"

        ic(key)
        res = x.arango({
            "query": """
                FOR user IN users
                FILTER user._key == @key
                UPDATE user WITH { blocked: true } IN users RETURN NEW
            """, 
            "bindVars": {"key": key}
        })
        ic(res)

        user_query = {"query": "FOR user IN users FILTER user._key == @key RETURN user", "bindVars": {"key": key}}
        user_result = x.arango(user_query)
        if user_result["result"]:
            user_email = user_result["result"][0]["user_email"]
            x.send_block_email(user_email)

        return f"""
        <template mix-target="[id='{key}']" mix-replace>
            <div class="mix-fade-out user_deleted" mix-ttl="2000">User blocked</div>
        </template>
        """
    except Exception as ex:
        ic(ex)
        return "An error occurred"
    finally:
        pass

##############################
@put("/users/<key>")
def _(key):
    try:
        username = x.validate_user_username()
        user_email = x.validate_email()
        res = x.arango({
            "query": """
                FOR user IN users
                FILTER user._key == @key
                UPDATE user WITH { username: @username, user_email: @user_email } IN users
                RETURN NEW
            """,
            "bindVars": {
                "key": key,
                "username": username,
                "user_email": user_email
            }
        })
        ic(res)
        return f"""
        <template mix-target="[id='{key}']" mix-before>
            <div class="mix-fade-out user_updated" mix-ttl="2000">User updated</div>
        </template>
        """
    except Exception as ex:
        ic(ex)
        if "username" in str(ex):
            return f"""
            <template mix-target="#message">
                {ex.args[1]}
            </template>
            """
    finally:
        pass
##############################

@get("/forgot-password")
def forgot_password():
    return template("forgot-password.html")

##############################
@post("/forgot-password")
def handle_forgot_password():
    try:
        email = request.forms.get("email")
        user_query = {
            "query": "FOR user IN users FILTER user.user_email == @user_email RETURN user",
            "bindVars": {"user_email": email}
        }
        user = x.arango(user_query)
        if not user["result"]:
            raise Exception("Email not found")

        user = user["result"][0]
        x.send_reset_email(email, user["_key"])

        return "Password reset email sent"
    except Exception as ex:
        ic(ex)
        return str(ex)
    
##############################
@get("/reset-password/<key>")
def reset_password(key):
    try:
        query = {
            "query": "FOR user IN users FILTER user._key == @key RETURN user",
            "bindVars": {"key": key}
        }
        result = x.arango(query)
        users = result.get("result", [])
        if not users:
            response.status = 404
            return {"error": "User not found"}
        
        user = users[0]  # There should be only one item with the specified ID
        ic(user)
        
        return template("reset-password.html", key=key, user=user)
    except Exception as ex:
        ic(ex)
        return str(ex)

##############################
@put("/reset-password/<key>")
def handle_reset_password(key):
    try:
        password = request.forms.get("password")
        confirm_password = request.forms.get("confirm_password")

        if password != confirm_password:
            return "Passwords do not match"
        
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

        update_query = {
            "query": """
                UPDATE { _key: @key, user_password: @password }
                IN users
            """,
            "bindVars": {
                "key": key,
                "password": hashed_password
            }
        }
        x.arango(update_query)

        return "Password reset successfully"
    except Exception as ex:
        ic(ex)
        return str(ex)

##############################
@put("/users/unblock/<key>")
def _(key):
    try:
        # Regex validation for key
        if not re.match(r'^[1-9]\d*$', key):
            return "Invalid key format"

        ic(key)
        res = x.arango({
            "query": """
                FOR user IN users
                FILTER user._key == @key
                UPDATE user WITH { blocked: false } IN users RETURN NEW
            """, 
            "bindVars": {"key": key}
        })
        ic(res)

        user_query = {"query": "FOR user IN users FILTER user._key == @key RETURN user", "bindVars": {"key": key}}
        user_result = x.arango(user_query)
        if user_result["result"]:
            user_email = user_result["result"][0]["user_email"]
            x.send_unblock_email(user_email)

        return f"""
        <template mix-target="[id='{key}']" mix-replace>
            <div class="mix-fade-out user_deleted" mix-ttl="2000">User blocked</div>
        </template>
        """
    except Exception as ex:
        ic(ex)
        return "An error occurred"
    finally:
        pass
##############################
UPLOAD_DIR = "uploads/images"
##############################
@get("/add_item")
def add_item_form():
    try:
        return template("add_item.html")
    except Exception as ex:
        print("There was a problem loading the page:", ex)
        return str(ex)
##############################
@post("/add_item")
def add_item():
    try:
        # Get form data
        item_name = request.forms.get("item_name")
        
        # Generate random values for latitude, longitude, and stars
        item_lat = round(random.uniform(55.65, 55.7), 4)
        item_lon = round(random.uniform(12.55, 12.6), 4)
        item_stars = round(random.uniform(3.0, 5.0), 1)
        
        item_price_per_night = request.forms.get("item_price_per_night")

        # Process splash image
        item_splash_image = request.files.get("item_splash_image")

        if not os.path.exists(UPLOAD_DIR):
            os.makedirs(UPLOAD_DIR)

        # Generate random filename for splash image
        splash_image_filename = f"{x.generate_random_string()}_{item_splash_image.filename}"
    
        splash_image_path = os.path.join(UPLOAD_DIR, splash_image_filename)
        item_splash_image.save(splash_image_path)

        # Process additional images
        image2 = request.files.get("image2")
        image2_filename = f"{x.generate_random_string()}_{image2.filename}"
        image2_path = os.path.join(UPLOAD_DIR, image2_filename)
        image2.save(image2_path)
        
        image3 = request.files.get("image3")
        image3_filename = f"{x.generate_random_string()}_{image3.filename}"
        image3_path = os.path.join(UPLOAD_DIR, image3_filename)
        image3.save(image3_path)

        # Create item data
        item = {
            "item_name": item_name,
            "item_splash_image": splash_image_filename,
            "item_lat": item_lat,
            "item_lon": item_lon,
            "item_stars": item_stars,
            "item_price_per_night": int(item_price_per_night),
            "item_created_at": int(time.time()),
            "item_updated_at": 0,
            "item_image2": image2_filename,
            "item_image3": image3_filename

        }

        # Save item to the database
        query = {
            "query": "INSERT @item INTO items RETURN NEW",
            "bindVars": {"item": item}
        }
        x.arango(query)

        return "Item added successfully"
    except Exception as ex:
        print("An error occurred:", ex)
        return f"An error occurred: {str(ex)}"
    finally:
        pass
##############################
@get('/edit_item/<key>')
def _(key):
    try:
        item_key_data = key
        item_key_name = "_key"
        query = {
            "query": "FOR item IN items FILTER item[@key_name] == @key_data RETURN item",
            "bindVars": {"key_name": item_key_name, "key_data": item_key_data}
        }
        result = x.arango(query)
        items = result.get("result", [])
        if not items:
            response.status = 404
            return {"error": "Item not found"}
        
        item = items[0]  # There should be only one item with the specified ID
        title = f"Edit your property"
        ic(item)
        is_logged = validate_user_logged()
        print(is_logged)
        return template("edit_item",
                        key=key, 
                        title=title,
                        item=item, is_logged=is_logged)
    except Exception as ex:
        ic(ex)
        return {"error": str(ex)}

##############################
@post('/edit_item/<key>')
def update_item(key):    
    try:
        item_name = request.forms.get('item_name')
        item_price_per_night = request.forms.get('item_price_per_night')
        
        item_splash_image = request.files.get('item_splash_image')
        image2 = request.files.get('image2')
        image3 = request.files.get('image3')

        # Process splash image
        if item_splash_image and item_splash_image.filename:
            splash_image_filename = f"{x.generate_random_string()}_{item_splash_image.filename}"
            splash_image_path = os.path.join(UPLOAD_DIR, splash_image_filename)
            item_splash_image.save(splash_image_path)
        else:
            splash_image_filename = None

        # Process additional images
        image2_filename = None
        if image2 and image2.filename:
            image2_filename = f"{x.generate_random_string()}_{image2.filename}"
            image2_path = os.path.join(UPLOAD_DIR, image2_filename)
            image2.save(image2_path)

        image3_filename = None
        if image3 and image3.filename:
            image3_filename = f"{x.generate_random_string()}_{image3.filename}"
            image3_path = os.path.join(UPLOAD_DIR, image3_filename)
            image3.save(image3_path)

        # Fetch the existing item to delete old images if necessary
        query = {
            "query": "FOR item IN items FILTER item._key == @key RETURN item",
            "bindVars": {"key": key}
        }
        result = x.arango(query)
        items = result.get("result", [])
        if not items:
            response.status = 404
            return {"error": "Item not found"}
        
        item = items[0]  # There should be only one item with the specified ID

        # Delete old images if new ones are uploaded
        if splash_image_filename and item.get('item_splash_image'):
            old_image_path = os.path.join(UPLOAD_DIR, item['item_splash_image'])
            if os.path.exists(old_image_path):
                os.remove(old_image_path)
        
        if image2_filename and item.get('image2'):
            old_image_path = os.path.join(UPLOAD_DIR, item['image2'])
            if os.path.exists(old_image_path):
                os.remove(old_image_path)
        
        if image3_filename and item.get('image3'):
            old_image_path = os.path.join(UPLOAD_DIR, item['image3'])
            if os.path.exists(old_image_path):
                os.remove(old_image_path)

        # Update the item in the database
        update_query = {
            "query": """
            UPDATE { 
                _key: @key, 
                item_name: @item_name, 
                item_price_per_night: @item_price_per_night,
                item_splash_image: @item_splash_image,
                item_lat: @item_lat,
                item_lon: @item_lon,
                item_stars: @item_stars,
                item_updated_at: @item_updated_at,
                item_image2: @image2,
                item_image3: @image3
            } IN items
            """,
            "bindVars": {
                "key": key,
                "item_name": item_name,
                "item_price_per_night": int(item_price_per_night),
                "item_splash_image": splash_image_filename or item.get('item_splash_image'),
                "item_lat": round(random.uniform(55.65, 55.7), 4),
                "item_lon": round(random.uniform(12.55, 12.6), 4),
                "item_stars": round(random.uniform(3.0, 5.0), 1),
                "item_updated_at": int(time.time()),
                "item_image2": image2_filename or item.get('image2'),
                "item_image3": image3_filename or item.get('image3')
            }
        }

        x.arango(update_query)
        
        return "Item updated successfully"
    except Exception as ex:
        return {"error": str(ex)}
    finally:
        pass
##############################
@post("/block_item/<key>")
def _(key):
    try:

        ic(key)
        res = x.arango({
            "query": """
                FOR item IN items
                FILTER item._key == @key
                UPDATE item WITH { blocked: item.blocked == true ? false : true } IN items
            """, 
            "bindVars": {"key": key}
        })
        ic(res)

        response.status = 303 
        response.set_header('Location', '/')
    except Exception as ex:
        ic(ex)
        return "An error occurred"
    finally:
        pass

##############################
try:
    import production
    application = default_app()
except:
    run(host="0.0.0.0", port=80, debug=True, reloader=True, interval=0)