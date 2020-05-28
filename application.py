import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/", methods=["GET", "POST"])
@login_required
def index():
    if request.method == "GET":
        """Show portfolio of stocks"""
        account = db.execute("SELECT cash FROM users WHERE id = :userid", userid=session["user_id"])
        shares= db.execute("SELECT symbol, SUM(shares) as total_shares FROM transactions WHERE user_id= :userid GROUP BY symbol HAVING total_shares > 0", userid=session["user_id"])
        quotes = {}

        for share in shares:
            quotes[share["symbol"]]=lookup(share["symbol"])
        balance = account[0]["cash"]

        return render_template("statement.html", quotes=quotes, shares=shares, balance=balance)
    else:
        addfund = float(request.form.get("addfund"))
        db.execute("UPDATE users SET cash = cash + :addfund WHERE id = :userid", addfund=addfund, userid=session["user_id"])
        return redirect("/")

@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    if request.method == "POST":
        quote = lookup(request.form.get("symbol"))
        """ if no stoke symbol, return message"""
        if quote == None:
            # Display a flash message
            flash("Not valid symbol! Please retry with correct one !!")
            # Redirect user to buy page
            return redirect("/buy")
        stokes = int(request.form.get("stokes"))
        rows = db.execute("SELECT cash FROM users WHERE id = :userid", userid=session["user_id"])
        balance = rows[0]["cash"]
        price = quote["price"]
        quote_amount = price * stokes
        if quote_amount > balance:
            flash("Not enough balance! Please add funds or quote again.")
            # Redirect user to quote page
            return redirect ("/")
        db.execute("UPDATE users SET cash = cash - :price WHERE id = :user_id", price=quote_amount, user_id=session["user_id"])
        db.execute("INSERT INTO transactions (user_id, symbol, shares, price_per_share) VALUES(:user_id, :symbol, :shares, :price)",
                   user_id=session["user_id"],
                   symbol=request.form.get("symbol").upper(),
                   shares=stokes,
                   price=price)
        flash("Congratulations ! Stokes purchased")
        # redirect to index page
        return redirect("/")
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    transactions = db.execute("SELECT symbol, shares, price_per_share, created_at FROM transactions WHERE user_id = :userid ORDER BY created_at ASC", userid=session["user_id"])

    return render_template("history.html", transactions=transactions)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "GET":
        return render_template("quote.html")
    else:
        quote = lookup(request.form.get("symbol"))
        """ if no stoke symbol, return message"""
        if quote == None:
            # Display a flash message
            flash("Not valid symbol! Please retry with correct one !!")
            # Redirect user to quote page
            return redirect ("/quote")
        account = db.execute("SELECT cash FROM users WHERE id = :userid", userid=session["user_id"])
        balance = account[0]["cash"]
        # redirect to quated page  with passing quote parameter
        return render_template("quoted.html", quote=quote, balance=balance)



@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        rows = db.execute("SELECT * FROM users WHERE username = :username",
                            username=request.form.get("username"))
        if len(rows) > 0:
            flash("Username Already taken! Please Select different username.")

            # Redirect user to register page
            return redirect ("/register")
        else:
            # hash the password and insert a new user in the database
            hash = generate_password_hash(request.form.get("password"))
            new_user_id = db.execute("INSERT INTO users (username, hash) VALUES(:username, :hash)",
                                     username=request.form.get("username"),
                                     hash=hash)

        # Remember which user has logged in
            session["user_id"] = new_user_id

        # Display a flash message
            flash("Registered!")

        # Redirect user to home page
            return redirect ("/login")

    # User reached route via GET (as by submitting a form via GET)
    else:
        """diplay registration form"""
        return render_template("register.html")





@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    if request.method == "POST":
        quote = lookup(request.form.get("symbol"))

        # check correcness of symbol
        if quote == None:
            # Display a flash message
            flash("Not valid symbol! Please retry with correct one !!")
            # Redirect user to quote page
            return redirect ("/sell")
        share_sell = request.form.get("stokes")
        # check available no of share for particular company for user id
        share_no = db.execute("SELECT SUM(Shares) as total_shares FROM transactions WHERE user_id = :userid AND symbol = :symbol GROUP BY symbol", userid=session["user_id"], symbol=request.form.get("symbol").upper())
        availabe_shares = share_no[0]["total_shares"]
        # query database for username
        account = db.execute("SELECT cash FROM users WHERE id = :userid", userid=session["user_id"])
        balance = account[0]["cash"]
        current_quote = quote["price"] * int(share_sell)
        if availabe_shares < int(share_sell):
            flash("You cannot sell that you donot own !!")
            # Redirect user to sell page
            return redirect ("/")
        #correct book for tansaction
        db.execute("UPDATE users SET cash = cash + :trans WHERE id = :userid", trans=current_quote, userid=session["user_id"])
        db.execute("INSERT INTO transactions (user_id, symbol, shares, price_per_share) VALUES(:userid, :symbol, :shares, :price)",
                   userid=session["user_id"],
                   symbol=request.form.get("symbol").upper(),
                   shares=-int(share_sell),
                   price=quote["price"])

        flash("Sold!")
        return redirect ("/")

    else:

        return render_template("sell.html")


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
