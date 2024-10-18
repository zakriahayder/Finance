import requests

from cs50 import SQL
from flask import redirect, render_template, session
from functools import wraps

db = SQL("sqlite:///finance.db")

def apology(message, code=400):
    """Render message as an apology to user."""

    def escape(s):
        """
        Escape special characters.

        https://github.com/jacebrowning/memegen#special-characters
        """
        for old, new in [
            ("-", "--"),
            (" ", "-"),
            ("_", "__"),
            ("?", "~q"),
            ("%", "~p"),
            ("#", "~h"),
            ("/", "~s"),
            ('"', "''"),
        ]:
            s = s.replace(old, new)
        return s

    return render_template("apology.html", top=code, bottom=escape(message)), code


def login_required(f):
    """
    Decorate routes to require login.

    https://flask.palletsprojects.com/en/latest/patterns/viewdecorators/
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)

    return decorated_function


def lookup(symbol):
    """Look up quote for symbol."""
    url = f"https://finance.cs50.io/quote?symbol={symbol.upper()}"
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise an error for HTTP error responses
        quote_data = response.json()
        return {
            "name": quote_data["companyName"],
            "price": quote_data["latestPrice"],
            "symbol": symbol.upper()
        }
    except requests.RequestException as e:
        print(f"Request error: {e}")
    except (KeyError, ValueError) as e:
        print(f"Data parsing error: {e}")
    return None


def usd(value):
    """Format value as USD."""
    return f"${value:,.2f}"


def get_user_cash(username):
    """Get the user's cash balance."""
    rows = db.execute("SELECT cash FROM users WHERE username = ?", username)
    if not rows:
        return None
    return rows[0]["cash"]

def get_user_holdings(username):
    """Get the user's current stock holdings."""
    holdings = db.execute("""
        SELECT stock_symbol,
            SUM(n_stocks) AS total_stocks
        FROM transactions
        WHERE username = ?
        GROUP BY stock_symbol
        HAVING total_stocks > 0;
    """, username)
    return holdings

def get_user_stock_shares(username, symbol):
    """Get the total number of shares the user owns of a specific stock."""
    result = db.execute("""
        SELECT SUM(n_stocks) AS total_stocks
        FROM transactions
        WHERE username = ? AND stock_symbol = ?
        GROUP BY stock_symbol
    """, username, symbol.upper())
    if result:
        return result[0]["total_stocks"]
    else:
        return 0

def validate_shares(shares):
    """Validate that shares is a positive integer."""
    if not shares.isdigit() or int(shares) <= 0:
        return False
    return True