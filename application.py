import os

from flask import Flask, session, render_template
from flask_session import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

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

@app.route("/")
def index():
    """
    If user is logged in ( logged_in_user is not None ), renders application index
    Renders login form if not logged in
    """
    return render_template('index.html',logged_in_user=logged_in_user)


@app.route("/login")
def login():
    return "Project 1: TODO loin"


@app.route("/logout")
def logout():
    return "Project 1: TODO logout"


@app.route("/books")
def books():
    return "Project 1: TODO list books"
