import os
from hashlib import sha256

from datetime import datetime

from flask import Flask, session, render_template, request
from flask_session import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker


SESSION_TIMEOUT = 600 # seconds

app = Flask(__name__)

# Check for environment variable
if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Set up database
engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))

logged_in_user = None

def is_valid_user_session():
    """
    Checks if :
       - User is logged ( session ['user'] is not empty )
       - Time didn't run out ( now() < session['timeout']
       - return user if OK, None otherwise
    """
    
    if session.get('user') is None:
        session['user_id'] = None
        return None
    
    if session.get('timeout') is None:
        session['user'] = None # Force logout
        session['user_id'] = None 
        return None
    
    if datatime.now() < session.get['timeout']:
        # Timeout
        session['user'] = None # Force logout
        session['user_id'] = None       
        return None

    # Extends timeout
    session['timeout'] = datetime.now()+timedelta(seconds = SESSION_TIMEOUT)
       
    return session.get('user')
    
    
@app.route("/")
def index():
    """
    If user is logged in ( logged_in_user is not None ), renders application index
    Renders login form if not logged in
    """
    
    logged_in_user = is_valid_user_session()
    
    return render_template('index.html',logged_in_user=logged_in_user)


@app.route("/login", methods=['POST'])
def login():
    """
    User tries to log in
    Once logged, a timeout of 10 minutes is set for the session (i.e. logout
    is forced after 10 minutes of inactivity
    """
    
    email = request.form.get('email')
    password = request.form.get('password')
    
    password_hash = sha256(password.encode()).hexdigest()
    
    user = db.execute(
          "select id,name from users where email=:email and password_hash=:password_hash"
        , {'email':email, 'password_hash':password_hash}
        ).fetchone()

    if user is None:
        message = "Invalid credentials"
        logged_in_user = None
    else:
        session['user_id'] = user.id
        session['user'] = user.name
        logged_in_user = user.name
        message = f"Logged in as user '{user.name}'"
        
    return render_template('index.html',message=message, logged_in_user=logged_in_user)

@app.route("/create_account", methods=['POST', 'GET'])
def create_account():
    """
    Creates user account
    
    Uniqueness is checked on email 
    """
    
    name = request.form.get('name')
    email = request.form.get('email')
    password = request.form.get('password')
    password_check = request.form.get('password_check')
    
    # ok will become true if all checks are good and the user can be created
    ok = False

    next_form = 'account.html' #  the form we'll drive the user to after the checks
    
    if request.method != 'POST':
        #  A link ("Create an account") sent us here, no error to disply because of empty fields
        message = 'Please input your name, email and password to create an account'
        
    elif name is None or len(name) <=0 or email is None or len(email) <= 0 or password is None or len(password) <=0:
        message = "Name, email or password cannot be empty"
    elif password != password_check:
        message = "Password mismatch"
    else:    

        # Check for email already in Database
        user = db.execute(
              "select id,name from users where email=:email"
            , {'email':email}
            ).fetchone()

        if user is not None:
            message = 'This email is already present in the database'
        else:
            ok = True
            password_hash = sha256(password.encode()).hexdigest()
    
            user = db.execute(
              "insert into users(name,email,password_hash,role) values (:name, :email, :password_hash, 'user')"
            , {'name':name, 'email':email, 'password_hash':password_hash}
            )
            
            db.commit()
            
            message = "User added, you can log in the application"
            
            next_form = 'index.html'


    return render_template(next_form ,message=message, name=name, email=email, password=password)



@app.route("/logout")
def logout():
    
    session['user'] = None # Force logout
    session['user_id'] = None
    session['timeout'] = None
    
    return render_template('index.html', message='You have been logged out')


@app.route("/books")
def books():
    return "Project 1: TODO list books"
