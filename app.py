# path to bottle main package to replace with own bottle
# /home/mysite/.local/lib/python3.10/site-packages/bottle.py

# from bottle import default_app, put, delete, get, post, response, run, static_file, template
# import pathlib
# import sys
# sys.path.insert(0, str(pathlib.Path(__file__).parent.resolve())+"/bottle")
from bottle import default_app, put, delete, get, post, request, response, run, static_file, template
import x, re
from icecream import ic
import bcrypt
import json
import credentials

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
def _(item_splash_image):
    return static_file(item_splash_image, "images")

##############################
@get("/")
def _():
    try:
        x.setup_collection()
        # Fetch items from the ArangoDB collection 'items'
        query = {
            "query": "FOR item IN items SORT item.item_created_at LIMIT @limit RETURN item",
            "bindVars": {"limit": x.ITEMS_PER_PAGE}
        }
        result = x.arango(query)
        items = result.get("result", [])
        ic(items)
        is_logged = False
        try:
            x.validate_user_logged()
            is_logged = True
        except:
            pass

        return template("index.html", items=items, mapbox_token=credentials.mapbox_token, is_logged=is_logged)
    except Exception as ex:
        ic(ex)
        return str(ex)
    finally:
        pass
@get("/signup")
def _():
    try:
        return template("signup_wu_mixhtml.html")
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
        selected_option = request.forms.get("option")
        print(selected_option)
        
        ic(username) # this is ice cream it displays error codes when something goes wrong
        ic(password)
        ic(email) # this is ice cream it displays error codes when something goes wrong
        
        # Hash the password using bcrypt
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        
        user = {"username": username, "user_email": email, "user_password": hashed_password.decode('utf-8'), "role": selected_option} # Save the hashed password
        res = {"query": "INSERT @doc IN users RETURN NEW", "bindVars": {"doc": user}} # inserts a user via AQL query language, via the db method in the x.py file
        item = x.arango(res)
        
        return template("login.html")
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
        # html = template("_user.html", user=res["result"][0]) # not sure, a HTML template that is used for displaying a user?
        # form_create_user =  template("_form_create_user.html") # template again
        # return f"""
        # <template mix-target="#users" mix-top>
        #     {html}
        # </template>
        # <template mix-target="#frm_user" mix-replace>
        #     {form_create_user}
        # </template>
        # """
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
def _():
    x.no_cache()
    return template("login_wu_mixhtml.html")

@post("/login_arango")
def login():
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
                stored_hashed_password = user.get("user_password")

                # Verify the provided password with the stored hashed password
                if bcrypt.checkpw(user_password.encode('utf-8'), stored_hashed_password.encode('utf-8')):
                    return "login success"

        return "login failed - incorrect email or password"
    except Exception as ex:
        print("An error occurred:", ex)
        return "An error occurred while processing your request"
    finally:
        pass


##############################
@get("/profile")
def _():
    try:
        x.no_cache()
        x.validate_user_logged()
        db = x.db()
        q = db.execute("SELECT * FROM items ORDER BY item_created_at LIMIT 0, ?", (x.ITEMS_PER_PAGE,))
        items = q.fetchall()
        ic(items)    
        return template("profile.html", is_logged=True, items=items)
    except Exception as ex:
        ic(ex)
        response.status = 303 
        response.set_header('Location', '/login')
        return
    finally:
        if "db" in locals(): db.close()


##############################
@get("/logout")
def _():
    response.delete_cookie("user")
    response.status = 303
    response.set_header('Location', '/login')
    return


##############################
@get("/api")
def _():
    return x.test()


##############################
##############################
##############################
# @post("/signup")
# def _():
#     # password = b'password'
#     # # Adding the salt to password
#     # salt = bcrypt.gensalt()
#     # # Hashing the password
#     # hashed = bcrypt.hashpw(password, salt)
#     # # printing the salt
#     # print("Salt :")
#     # print(salt)
    
#     # # printing the hashed
#     # print("Hashed")
#     # print(hashed)    
#     return "signup"


# ##############################
# @post("/login")
# def _():
#     try:
#         user_email = x.validate_email()
#         user_password = x.validate_password()
#         db = x.db()
#         q = db.execute("SELECT * FROM users WHERE user_email = ? LIMIT 1", (user_email,))
#         user = q.fetchone()
#         if not user: raise Exception("user not found", 400)
#         if not bcrypt.checkpw(user_password.encode(), user["user_password"].encode()): raise Exception("Invalid credentials", 400)
#         user.pop("user_password") # Do not put the user's password in the cookie
#         ic(user)
#         try:
#             import production
#             is_cookie_https = True
#         except:
#             is_cookie_https = False        
#         response.set_cookie("user", user, secret=x.COOKIE_SECRET, httponly=True, secure=is_cookie_https)
        
#         frm_login = template("__frm_login")
#         return f"""
#         <template mix-target="frm_login" mix-replace>
#             {frm_login}
#         </template>
#         <template mix-redirect="/profile">
#         </template>
#         """
#     except Exception as ex:
#         try:
#             response.status = ex.args[1]
#             return f"""
#             <template mix-target="#toast">
#                 <div mix-ttl="3000" class="error">
#                     {ex.args[0]}
#                 </div>
#             </template>
#             """
#         except Exception as ex:
#             ic(ex)
#             response.status = 500
#             return f"""
#             <template mix-target="#toast">
#                 <div mix-ttl="3000" class="error">
#                    System under maintainance
#                 </div>
#             </template>
#             """
        

#     finally:
#         if "db" in locals(): db.close()


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

##############################
@get("/rooms/<id>")
def _(id):
    try:
        db = x.db()
        q = db.execute("SELECT * FROM items WHERE item_pk = ?", (id,))
        item = q.fetchone()
        title = "Item "+id
        ic(item)
        return template("rooms",
                        id=id, 
                        title=title,
                        item=item)
    except Exception as ex:
        print(ex)
        return "error"
    finally:
        pass

##############################
@get("/users")
def _():
    try:
        q = {"query": "FOR user IN users FILTER user.blocked != true RETURN user"}
        users = x.arango(q)
        ic(users)
        return template("users", users=users["result"])
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
        if not re.match(r"^[1-9]\d*$", key):
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
        email = x.validate_email()
        res = x.arango({"query":"""
                        UPDATE { _key: @key, username: @username, email: @email} 
                        IN users 
                        RETURN NEW""",
                    "bindVars":{
                        "key": f"{key}",
                        "username":f"{username}",
                        "email":f"{email}"
                    }})
        print(res)
        return f"""
        <template mix-target="[id='{key}']" mix-before>
            <div class="mix-fade-out user_deleted" mix-ttl="2000">User updated</div>            
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
            "query": "FOR user IN users FILTER user.email == @user_email RETURN user",
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
        
        hashed_password = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

        update_query = {
            "query": """
                UPDATE { _key: @key, password: @password }
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

try:
    import production
    application = default_app()
except:
    run(host="0.0.0.0", port=80, debug=True, reloader=True, interval=0)