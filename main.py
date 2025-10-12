from flask import Flask, render_template, request, url_for, redirect, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, String, Float, or_, func
from flask_login import UserMixin, login_user, LoginManager, current_user, logout_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
import os
import smtplib

my_email = "serdar.akova5@gmail.com"
password = "nyod qdhc xkov hhis"

DISCOUNT_CODE = "WELCOME10"

app = Flask(__name__)
app.config["SECRET_KEY"] = "şwlmefsgdptme4r23pqo"

#Login
login_manager = LoginManager()
login_manager.init_app(app)

login_manager.login_view = "login"
    
@login_manager.user_loader
def load_user(user_id):
    return db.get_or_404(DRL_USER, user_id)

#Create DB
class Base(DeclarativeBase):
    pass

def get_db_uri():
    uri = os.getenv("DATABASE_URL")
    if uri:
        if uri.startswith("postgres://"):
            uri = uri.replace("postgres://", "postgresql://", 1)
        return uri
    return "sqlite:///products.db"

#Connect Database
app.config["SQLALCHEMY_DATABASE_URI"] = get_db_uri()
db = SQLAlchemy(model_class=Base)
db.init_app(app)

#TABLES
class Product(db.Model):
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(250), unique=False, nullable=False)
    description: Mapped[str] = mapped_column(String(250), unique=False)
    category: Mapped[str] = mapped_column(String(250), nullable=False)
    gender: Mapped[str] = mapped_column(String(250), nullable=False)
    slug: Mapped[str] = mapped_column(String(250), nullable=False)
    img: Mapped[str] = mapped_column(String(500), nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    size: Mapped[str] = mapped_column(String(250), nullable=False)

    @property
    def sizes_list(self) -> list[str]:
        raw = self.size.replace(",", "/")
        return [s.strip() for s in raw.split("/") if s.strip()]
    

class DRL_USER(UserMixin, db.Model):
    __tablename__ = "drl_users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(250), unique=True, nullable=False)
    password: Mapped[str] = mapped_column(String(250), nullable=False)

with app.app_context():
    db.create_all()

@app.route('/')
def index():
    return render_template('./index.html')

@app.route('/products')
def products():
    result = db.session.execute(db.select(Product))
    all_products = result.scalars().all()
    if all_products:
        return render_template('./products.html', product_list=all_products)
    else:
        return render_template("./products.html")
    
@app.route('/product_card')
def product_card():
    result = db.session.execute(db.select(Product))
    all_products = result.scalars().all()
    if all_products:
        return render_template('./products.html', product_list=all_products)
    else:
        return render_template("./products.html")

@app.route('/products/<int:product_id>', methods=["POST", "GET"])
def product_showcase(product_id):
    product = db.get_or_404(Product, product_id)
    return render_template('./product_showcase.html', product=product)


@app.route('/add-to-cart/<int:product_id>', methods=["POST", "GET"])
def add_to_cart(product_id):
    product = db.get_or_404(Product, product_id)
    qty = int(request.form.get("qty", 1))
    size = (request.form.get("size") or "").strip().lower()

    if size not in [s.lower() for s in product.sizes_list]:
        return redirect(url_for("product_showcase", product_id=product.id))
    
    cart = session.get("cart") or {"items": []}

    for it in cart["items"]:
        if it["product_id"] == product.id and it.get("size") == size:
            it["qty"] = int(it["qty"]) + qty
            break

    else:
        cart["items"].append({
            "id": f"{product.id}:{size}",
            "product_id": product.id,
            "name": product.name,
            "price": float(product.price),
            "qty": qty,
            "size": size,
            "image_url": product.img,
        })
    session["cart"] = cart
    return redirect(url_for("cart"))

@app.post('/update-cart/<item_id>')
def update_cart(item_id):
    cart = _get_cart()
    qty = max(1, int(request.form.get('qty', 1)))
    for it in cart["items"]:
        if it["id"] == item_id:
            it["qty"] = qty
            break
    _save_cart(cart)
    return redirect(url_for('cart'))

@app.post('/remove-from-cart/<item_id>')
def remove_from_cart(item_id):
    cart = _get_cart()
    cart["items"] = [it for it in cart["items"] if it["id"] != item_id]
    _save_cart(cart)
    return redirect(url_for('cart'))



@app.route('/cart', methods=["POST", "GET"])
def cart():
    cart = _get_cart()
    _save_cart(cart)
    return render_template('./cart.html', cart=cart)

def _get_cart():
    cart = session.get("cart")
    if not cart:
        cart = {"items": [], "coupon": None, "discount": 0.0}
    return cart

def _save_cart(cart):
    for it in cart["items"]:
        it["total_price"] = round(float(it["price"]) * int(it["qty"]), 2)

    subtotal = round(sum(it["total_price"] for it in cart["items"]), 2)
    discount = float(cart.get("discount", 0.0))
    shipping = 0.0 if subtotal >= 100 else 9.99
    taxable = max(subtotal - discount, 0.0)
    tax = round(taxable * 0.18, 2)
    total = round(taxable + shipping + tax, 2)
    
    if request.method == "POST":
        d = request.form.get('discount')
        print(d)
        if d == DISCOUNT_CODE:
            total = total - (total * 10 / 100)

    cart.update({"subtotal": subtotal, "shipping": shipping, "tax": tax, "total": total})
    session["cart"] = cart
    session["cart_count"] = sum(int(it["qty"]) for it in cart["items"])


@app.route('/login', methods=["POST", "GET"])
def login():
    if request.method == "GET":
        return render_template('./login.html')
    else:
        email = request.form.get("email")
        password = request.form.get("password")
        hashed = generate_password_hash(password, salt_length=8)

        user = db.session.execute(
            db.select(DRL_USER).filter_by(email=email)
        ).scalar_one_or_none()
        
        if not user:
            return "<h2>User not found.</h2>", 401
        
        if not check_password_hash(user.password, password):
            return "<h2>Incorrect password.</h2>", 401
        
        login_user(user)
        session.permanent = True

        return redirect(url_for('index'))

        

@app.route('/register', methods=["POST", "GET"])
def register():
    if request.method == "GET":
        return render_template('./register.html')
    else:
        email = request.form.get("email")
        password = request.form.get("password1")
        password2 = request.form.get("password2")
        hashed = generate_password_hash(password, salt_length=8)


        all_emails = db.session.execute(db.select(DRL_USER.email)).scalars().all()
        if email in all_emails:
            return "<h2>This user already exists.</h2>"
        elif password != password2:
            return "<h2>Passwords do not match.</h2>"
        else:
            new_user = DRL_USER(
                email=email,
                password=hashed
            )
            db.session.add(new_user)
            db.session.commit()
            return redirect('/login')

@app.route('/account')
def user_account():
    orders = []
    addresses = []
    return render_template('./account.html',
                           user=current_user,
                           orders=orders,
                           addresses=addresses)

@app.post('/account/profile')
@login_required
def update_profile():
    email = (request.form.get('email') or '').strip().lower()
    if not email:
        return redirect(url_for('account'))
    current_user.email = email
    db.session.commit()
    return redirect(url_for('account'))

@app.post('/account/password')
@login_required
def change_password():
    current_pw = request.form.get('current_password') or ''
    new_pw = request.form.get('new_password') or ''
    confirm_pw = request.form.get('confirm_password') or ''

    if not check_password_hash(current_user.password, current_pw):
        return redirect(url_for('account'))
    if len(new_pw) < 8:
        return redirect(url_for('account'))
    if new_pw != confirm_pw:
        return redirect(url_for('account'))

    current_user.password = generate_password_hash(new_pw, method='pbkdf2:sha256', salt_length=16)
    db.session.commit()
    return redirect(url_for('account'))

@app.post('/newsletter')
def accept_newsletter():
    email = request.form.get('email')
    if not email:
        return "<h2>Please write an email.</h2>"
    else:
        with smtplib.SMTP("smtp.gmail.com", 587) as connection:
            connection.starttls()
            connection.login(user=my_email, password=password)
            connection.sendmail(
                from_addr=my_email,
                to_addrs=email,
                msg=f"Subject: Welcome to newsletter! \n\n Welcome to DRL Newsletter. Here's your 10% discount code: {DISCOUNT_CODE}."
            )
        return redirect('/')

@app.route('/sweatshirts')
def sweatshirts():
    result = db.session.execute(db.select(Product).where(Product.category == "sweatshirts"))
    all_sweathsirts = result.scalars().all()
    if all_sweathsirts:
        return render_template('./sweatshirts.html', product_list=all_sweathsirts)
    else:
        return render_template("./sweatshirts.html")
    
@app.route('/jeans')
def jeans():
    result = db.session.execute(db.select(Product).where(Product.category == "jeans"))
    all_jeans = result.scalars().all()
    if all_jeans:
        return render_template('./jeans.html', product_list=all_jeans)
    else:
        return render_template("./jeans.html") 
    
@app.route('/trousers')
def trousers():
    result = db.session.execute(db.select(Product).where(Product.category == "trousers"))
    all_trousers = result.scalars().all()
    if all_trousers:
        return render_template('./trousers.html', product_list=all_trousers)
    else:
        return render_template("./trousers.html") 
    
@app.route('/search')
def search():
    q = (request.args.get("q") or "").strip()
    if not q:
        return redirect(url_for("products"))
    like = f"%{q}%"

    result = db.session.execute(db.select(Product).where( or_(Product.name.ilike(like),Product.description.ilike(like),Product.category.ilike(like),)).order_by(func.lower(Product.name))).scalars().all()
    return render_template("products.html", product_list=result , query=q)



if __name__ == "__main__":
    app.run(debug=True)
