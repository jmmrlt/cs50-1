import os
from hashlib import sha256

from datetime import datetime, timedelta

from flask import Flask, session, render_template, request
from flask import jsonify
from flask_session import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

import requests

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

def xlog(s):
    return
    # app.logger.info(s)

def validate_user_session():
    """
    Checks if :
       - User is logged ( session ['user'] is not empty )
       - Time didn't run out ( now() < session['timeout']
       - return user if OK, None otherwise
    """
    
    xlog(f"session : {session}")
    
    logged_in_user = None
    
    if session is None:
        logged_in_user = None
        app.logger.info("No session")
        return 

    logged_in_user = None
    
    if session.get('user') is None:
        session['user_id'] = None
        xlog("No user")
        return None
    
    if session.get('timeout') is None:
        session['user'] = None # Force logout
        session['user_id'] = None 
        xlog("No timeout")        
        return None
    
    if datetime.now() > session.get('timeout'):
        # Timeout
        session['user'] = None # Force logout
        session['user_id'] = None
        xlog("Timeout gone")             
        return None

    # Extends timeout
    session['timeout'] = datetime.now()+timedelta(seconds = SESSION_TIMEOUT)
       
    logged_in_user = session.get('user')
    
    xlog(f"Login ok {logged_in_user}, {session['timeout']}")
    
    return logged_in_user

def not_logged():
    """
    Used when user is not logged in to go back to index page
    """
    return render_template('index.html',
                               message="Your are not logged in!")
                               
@app.route("/")
def index():
    """
    If user is logged in ( logged_in_user is not None ), renders application index
    Renders login form if not logged in
    """  
    logged_in_user = validate_user_session()
    return render_template('index.html',logged_in_user=logged_in_user)


@app.route("/login", methods=['POST'])
def login():
    """
    User tries to log in
    Once logged, a timeout of 10 minutes is set for the session, i.e. logout
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
        session['timeout'] = datetime.now()+timedelta(seconds = SESSION_TIMEOUT)
        
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
    
    return render_template('index.html', 
                           message='You have been logged out')


@app.route("/books", methods=['POST','GET'])
def books():
    """
    Get a list of books mathcing the given criteria

    makes a "generic match" criteria by surrounding the string input
    by the user with '%' and search it using the case insensitive 
    "ilike" operator in title, author and isbn, returns the list of 
    matching books and the number of books returned
    """
    
    if validate_user_session() is None:
        return not_logged()

    criteria = request.form.get('criteria')
    
    books = None
    count = 0
    
    if criteria is None:
        message = ''
    elif criteria == '':
        message = "Search criteria cannot be empty"
    else:
        search_criteria=f"%{criteria}%"

        books = db.execute(
                  "select * from books \
                      where \
                         author ilike :criteria \
                      or isbn ilike :criteria \
                      or title ilike :criteria",
                  {'criteria':search_criteria}
                ).fetchall()
        
        count = len(books)

        message = f"Found {count} books matching '{criteria}'"      
                        
        xlog(f"Found books : {books}")
    
    return render_template("books.html", 
                           message=message, 
                           criteria=criteria, 
                           books=books,
                           count=count
           )


def get_bookread_info(isbn):
    """
    Get book information from Bookread API
    """    
    key = os.getenv('BOOKREAD_API_KEY') or None
    
    if key is None:
        return None
        
    try:    
        res = requests.get('https://www.goodreads.com/book/review_counts.json', params={'key':key, 'isbns': isbn })
    
        res = res.json()['books'][0]

        xlog(f"Res={res}")
        
    except Exception as e:
        xlog("Exception happened when using bookread API {}".format(str(e)))
        res = None
    	
    return res

def find_book(isbn):
    """
    Get book information from our local database and Bookread
    """
    if isbn is None:
        return None, None

    book = db.execute(
             "select author,title,isbn,year from books \
              where isbn = :isbn",
             {'isbn':isbn}
           ).fetchone()
    
    bookread_reviews = get_bookread_info(isbn)

    return book, bookread_reviews
            
@app.route("/api/<string:isbn>", methods=['GET'])
def api_isbn(isbn):
    """"
    returns info about the book identified by its isbn code, as a json string
    returns a 404 error if isbn is not found in local database
    """
    book, bookread_reviews = find_book(isbn)

    if book is None:
        return jsonify({'error':f"Nothing found for isbn '{isbn}'"}),404

    if bookread_reviews is not None:
        count = bookread_reviews['reviews_count']
        rating = bookread_reviews['average_rating']
    else:
        count, rating = 0, 0
		 		
    return jsonify({'title' : book.title, 'author' : book.author,
                    'year' : book.year, 'isbn' : book.isbn,
                    'review_count' : count,
                    'average_score' : rating
           }), 200
		
	           
@app.route("/viewbook/<isbn>", methods=['POST','GET'])
def viewbook(isbn):

    user = validate_user_session()
    
    if user is None:
        return not_logged()
            
    message = ''
                 
    book, bookread_reviews = find_book(isbn)
                           
    reviews = None
    
    bookread_reviews = get_bookread_info(isbn)
    
    return render_template("viewbook.html",book=book,message=message,bookread_reviews=bookread_reviews,reviews=reviews, logged_in_user=user)
