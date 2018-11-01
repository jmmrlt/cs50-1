import os
from hashlib import sha256

from datetime import datetime, timedelta

from flask import Flask, session, render_template, request
from flask import jsonify
from flask_session import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

import requests

DEBUG = True

# seconds of inactivity after which the session is automatically closed
SESSION_TIMEOUT = 600

# minimum number of characters to input in a review to have it 
# saved
REVIEW_MIN_LEN = 20

RATINGS = ['1','2', '3', '4', '5']

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

@app.teardown_appcontext
def close_db(error):
    """Closes the database again at the end of the request."""
    db.close()

def xlog(s):
    if DEBUG:
        app.logger.info(s)

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

def get_user_id():
	
	return session['user_id']
	
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
        message = ''
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
    Get a list of books matching the given criteria

    makes a "generic match" criteria by surrounding the string input
    by the user with '%' and search it using the case insensitive 
    "ilike" operator in title, author and isbn, returns the list of 
    matching books and the number of books returned
    """
    
    logged_in_user = validate_user_session()
    if logged_in_user is None:
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
                           count=count,
                           logged_in_user=logged_in_user
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

def find_book(isbn=None, book_id=None):
    """
    Get book information from our local database and Bookread
    """
    if isbn is None and book_id is None:
        return None, None

    criteria={'book_id':book_id, 'isbn':isbn}
	
    book, reviews, bookread_reviews = None, None, None
	
    book = db.execute(
             "select * from books \
              where isbn = :isbn or id=:book_id",
             criteria
           ).fetchone()
    
    if book is not None:
        bookread_reviews = get_bookread_info(book.isbn)
		
        reviews = db.execute("select u.name, r.review, r.rating \
                              from \
                                  reviews r join users u \
                                     on u.id = r.user_id \
                              where book_id=:book_id",
                              {'book_id':book_id}
                  ).fetchall()

    return book, reviews, bookread_reviews
            
@app.route("/api/<string:isbn>", methods=['GET'])
def api_isbn(isbn):
    """"
    returns info about the book identified by its isbn code, as a json string
    returns a 404 error if isbn is not found in local database
    """
    book, reviews, bookread_reviews = find_book(isbn=isbn)

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
		
def exist_review(book_id, user_id):
	
	
    r      = db.execute("select id from reviews \
                where book_id=:book_id \
                  and user_id = :user_id",
                {'book_id':book_id, 'user_id':user_id})
    
    z=r.fetchall()
    xlog(f"Exist_review : {book_id} {user_id} => {r} {z}")

    r = r.rowcount
                        
    return r > 0
	           
@app.route("/viewbook/<int:book_id>", methods=['POST','GET'])
def viewbook(isbn=None, book_id=None, message=''):

    user = validate_user_session()
    
    if user is None:
        return not_logged()
                 
    book, reviews, bookread_reviews = find_book(isbn=isbn, book_id=book_id)

    already_reviewed = exist_review(book.id, get_user_id())
    
    return render_template("viewbook.html",
                           book=book,message=message,
                           bookread_reviews=bookread_reviews,
                           reviews=reviews,
                           logged_in_user=user,
                           already_reviewed=already_reviewed,
                           ratings = RATINGS
           )

@app.route("/add_review/<int:book_id>", methods=['POST','GET'])
def add_review(book_id):

    user = validate_user_session()
    
    if user is None:
        return not_logged()
            
    message = ''
    
    review = request.form.get('review')
    rating = request.form.get('rating')
    
    user_id = get_user_id()
    
    if len(review) < REVIEW_MIN_LEN:
        message = "Your review cannot be shorter than 50 characters"
    else:
        
        if exist_review(book_id, user_id):
            message = "You already submitted a review for this book"
        else:
            try:
                db.execute("insert into reviews(book_id, user_id, review, rating) \
                            values(:book_id, :user_id, :review, :rating)",
                            {'book_id':book_id, 'user_id':user_id, 
                             'review':review, 'rating':rating
                            }
                          )
                db.commit()
            except Exception as e:
                message = "An error happened during insertion of your \
review, please try again later {}".format(str(e))

    return viewbook(isbn=None,book_id=book_id,message=message)
