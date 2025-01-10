from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import requests
from flask_sqlalchemy import SQLAlchemy
import datetime
import pandas as pd
from matplotlib.figure import Figure
import io
import base64 
from urllib.parse import quote

import matplotlib.pyplot as plt

from flask_wtf import FlaskForm
from wtforms import FloatField, SubmitField
from wtforms.validators import DataRequired
from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users4.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'secret_key'

db = SQLAlchemy(app)

admin = Admin(app, name='Admin Panel', template_mode='bootstrap3')


# Define your models

# Define models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    city = db.Column(db.String(100), nullable=True)

class CarbonFootprint(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date = db.Column(db.Date, nullable=False, default=datetime.date.today)
    transport = db.Column(db.Float, nullable=False, default=0.0)
    electricity = db.Column(db.Float, nullable=False, default=0.0)
    waste = db.Column(db.Float, nullable=False, default=0.0)
    total = db.Column(db.Float, nullable=False, default=0.0)

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    username = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    likes = db.Column(db.Integer, default=0) 
    
class Like(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)

    def __init__(self, user_id, post_id):
        self.user_id = user_id
        self.post_id = post_id


class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    username = db.Column(db.String(100), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)


# API Keys (for weather, AQI, etc.)
openweatherMapApiKey = "7d9d91e8a10b95b8d8f7a2c5656e5bf9"
AQI_API_KEY = '904164073b279b07ff95c1ead5e07cd58eedf0c0'
NEWS_API_KEY = 'pub_605312e53e8da917a4a1228232572b28a4267'


# API Routes (Weather, AQI, and News)

@app.route('/api/weather', methods=['GET'])
def get_weather():
    city = request.args.get('city')
    if not city:
        return jsonify({'error': 'City name is required'}), 400
    url = f'http://api.openweathermap.org/data/2.5/weather?q={city}&appid={openweatherMapApiKey}&units=metric'
    try:
        response = requests.get(url)
        data = response.json()
        if response.status_code == 200:
            return jsonify(data)
        else:
            return jsonify({'error': data.get('message', 'Failed to retrieve data')}), response.status_code
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/aqi', methods=['GET'])
def get_aqi():
    city = request.args.get('city')
    if not city:
        return jsonify({'error': 'City name is required'}), 400
    url = f'http://api.waqi.info/feed/{city}/?token={AQI_API_KEY}'
    try:
        response = requests.get(url)
        data = response.json()
        if response.status_code == 200 and data['status'] == 'ok':
            aqi = data['data']['aqi']
            return jsonify({'aqi': aqi, 'city': city})
        else:
            return jsonify({'error': data.get('data', 'Failed to retrieve AQI')}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/news', methods=['GET'])
def get_aqi_news():
    city = request.args.get('city')
    if not city:
        return jsonify({'error': 'City name is required'}), 400
    encoded_city = quote(city)
    url = f'https://newsdata.io/api/1/news?apikey={NEWS_API_KEY}&q=air quality {encoded_city}'
    try:
        response = requests.get(url)
        data = response.json()
        if response.status_code == 200:
            articles = data.get('results', [])
            # Return the articles with image URL, title, and link
            articles_with_images = [
                {
                    'title': article['title'],
                    'link': article['link'],
                    'image': article.get('image_url', '')  # Assuming 'image_url' is the key
                }
                for article in articles[:10]
            ]
            return jsonify({'articles': articles_with_images})
        else:
            return jsonify({'error': 'Failed to retrieve news'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# Leaderboard Route
@app.route('/leaderboard', methods=['GET'])
def leaderboard():
    leaderboard = db.session.query(
        User.name,
        User.city,
        db.func.sum(CarbonFootprint.total).label('total_footprint')
    ).join(CarbonFootprint).group_by(User.id).order_by(db.func.sum(CarbonFootprint.total).desc()).all()
    leaderboard_with_rank = [
        {"rank": idx + 1, "name": name, "city": city, "total_footprint": total_footprint}
        for idx, (name, city, total_footprint) in enumerate(leaderboard)
    ]
    return render_template('leaderboard.html', leaderboard=leaderboard_with_rank)


# Carbon Tracker Route
class CarbonFootprintForm(FlaskForm):
    transport = FloatField('Transport (km)', validators=[DataRequired()])
    electricity = FloatField('Electricity (kWh)', validators=[DataRequired()])
    waste = FloatField('Waste (kg)', validators=[DataRequired()])
    submit = SubmitField('Submit')


@app.route('/carbon_tracker', methods=['GET', 'POST'])
def carbon_tracker():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    carbon_footprint_result = None
    form = CarbonFootprintForm()

    if form.validate_on_submit():
        try:
            transport = form.transport.data
            electricity = form.electricity.data
            waste = form.waste.data
            user_id = session['user_id']
            total = transport * 0.25 + electricity * 0.75 + waste * 1.2
            entry = CarbonFootprint(user_id=user_id, transport=transport, electricity=electricity, waste=waste, total=total)
            db.session.add(entry)
            db.session.commit()
            flash("Carbon footprint logged successfully!")
            carbon_footprint_result = total
        except Exception as e:
            flash(f"Error: {str(e)}")

    user_id = session['user_id']
    entries = CarbonFootprint.query.filter_by(user_id=user_id).order_by(CarbonFootprint.date).all()
    dates = [entry.date.strftime('%Y-%m-%d') for entry in entries]
    totals = [entry.total for entry in entries]

    fig = plt.figure(figsize=(8, 6))
    ax = fig.add_subplot(111)
    ax.plot(dates, totals, marker='o', color='green', label='Total CO2')
    ax.set_title('Your Carbon Footprint Over Time')
    ax.set_xlabel('Date')
    ax.set_ylabel('Total CO2 (kg)')
    ax.grid(True)
    ax.legend()

    fig.autofmt_xdate(rotation=45)
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    buf.seek(0)
    plot_data = base64.b64encode(buf.getvalue()).decode('utf-8')
    buf.close()

    return render_template('carbon_tracker.html', form=form, entries=entries, plot_data=plot_data, carbon_footprint_result=carbon_footprint_result)

# Community Post Routes
@app.route('/community', methods=['GET', 'POST'])
def community():
    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        if title and content:
            username = session.get('username', 'Anonymous')
            new_post = Post(title=title, content=content, username=username)
            db.session.add(new_post)
            db.session.commit()
        return redirect(url_for('community'))

    posts = Post.query.order_by(Post.created_at.desc()).all()

    # Preload comments for each post
    for post in posts:
        post.comments = Comment.query.filter_by(post_id=post.id).all()

    return render_template('community.html', posts=posts)


@app.route('/like_post/<int:post_id>', methods=['POST'])
def like_post(post_id):
    post = Post.query.get(post_id)
    if not post:
        flash("Post not found.")
        return redirect(url_for('community'))
    
    user_id = session.get('user_id')

    # Check if the user has already liked the post
    existing_like = Like.query.filter_by(user_id=user_id, post_id=post_id).first()
    if existing_like:
        flash("You have already liked this post.")
        return redirect(url_for('community'))

    # Create a new like record
    new_like = Like(user_id=user_id, post_id=post_id)
    db.session.add(new_like)
    db.session.commit()

    # Increment the post's like count
    post.likes += 1
    db.session.commit()

    flash("Post liked!")
    return redirect(url_for('community'))



@app.route('/add_comment/<int:post_id>', methods=['POST'])
def add_comment(post_id):
    content = request.form.get('content')
    if content:
        username = session.get('username', 'Anonymous')
        new_comment = Comment(content=content, username=username, post_id=post_id)
        db.session.add(new_comment)
        db.session.commit()
    return redirect(url_for('community')) 
 

@app.route('/')
def index():
    return render_template('index.html')     


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirmpassword']
        city = request.form['city']
        if password != confirm_password:
            flash("Passwords do not match!")
            return render_template('register.html')
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash("User with this email already exists.")
            return render_template('register.html')
        new_user = User(name=name, email=email, password=password, city=city)
        db.session.add(new_user)
        db.session.commit()
        flash("Registration successful! Please login.")
        return redirect(url_for('login'))
    return render_template('register.html') 



@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email, password=password).first()
        if user:
            session['logged_in'] = True
            session['user_id'] = user.id
            session['username'] = user.name
            session['is_admin'] = (user.email == "pintu@gmail.com")
            if session['is_admin']:
                flash("Admin login successful!")
                return redirect(url_for('admin_dashboard'))
            flash("Login successful! Welcome.")
            return redirect(url_for('home'))
        flash("Invalid email or password.")
        return redirect(url_for('login'))
    return render_template('login.html') 



@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        if email == 'pintu@gmail.com' and password == '123':
            session['admin_logged_in'] = True
            flash("Admin login successful!")
            return redirect(url_for('admin_dashboard'))  # We change this to redirect to a new page
        flash("Invalid admin credentials!")
        return redirect(url_for('admin_login'))
    return render_template('admin_login.html')



@app.route('/admin_homepage')
def admin_homepage():
    if not session.get('admin_logged_in'):
        flash("Unauthorized access!")
        return redirect(url_for('admin_login'))
    
    return render_template('admin_homepage.html') 



@app.route('/admin_dashboard')
def admin_dashboard():
    if not session.get('is_admin'):
        flash("Unauthorized access!")
        return redirect(url_for('login'))

    # Fetch all the users and posts
    users = User.query.all()
    posts = Post.query.all()

    # Join Comment with Post and then with User
    comments = db.session.query(Comment, Post, User).join(Post, Comment.post_id == Post.id).join(User, Post.username == User.name).all()

    # Join CarbonFootprint with User
   # Join CarbonFootprint with User
    carbon_footprints = db.session.query(CarbonFootprint, User).join(User, CarbonFootprint.user_id == User.id).all()


    return render_template('admin_dashboard.html', users=users, posts=posts, comments=comments, carbon_footprints=carbon_footprints) 



@app.route('/home')
def home():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    return render_template('home.html', username=session['username']) 



@app.route('/logout')
def logout():
    session.clear()
    flash("You have logged out successfully.")
    return redirect(url_for('index')) 


@app.route('/delete_user/<int:user_id>', methods=['POST'])
def delete_user(user_id):
    if not session.get('is_admin'):
        flash("Unauthorized access!")
        return redirect(url_for('login'))

    # Fetch the user to delete
    user = User.query.get(user_id)
    if not user:
        flash("User not found!")
        return redirect(url_for('admin_dashboard'))

    # Check if the user is the admin user with email 'pintu@gmail.com' and password '3734'
    if user.email == 'pintu@gmail.com' and user.password == '3734':
        flash("You cannot delete the admin account!")
        return redirect(url_for('admin_dashboard'))

    # Delete associated data before deleting user
    CarbonFootprint.query.filter_by(user_id=user.id).delete()
    Post.query.filter_by(username=user.name).delete()
    Comment.query.filter_by(username=user.name).delete()
    Like.query.filter_by(user_id=user.id).delete()

    db.session.delete(user)
    db.session.commit()

    flash("User and related data deleted successfully!")
    return redirect(url_for('admin_dashboard')) 




@app.route('/delete_post/<int:post_id>', methods=['POST'])
def delete_post(post_id):
    if not session.get('is_admin'):
        flash("Unauthorized access!")
        return redirect(url_for('login'))

    post = Post.query.get(post_id)
    if not post:
        flash("Post not found!")
        return redirect(url_for('admin_dashboard'))

    # Delete related comments and likes
    Comment.query.filter_by(post_id=post.id).delete()
    Like.query.filter_by(post_id=post.id).delete()

    db.session.delete(post)
    db.session.commit()

    flash("Post and related data deleted successfully!")
    return redirect(url_for('admin_dashboard')) 



@app.route('/delete_comment/<int:comment_id>', methods=['POST'])
def delete_comment(comment_id):
    if not session.get('is_admin'):
        flash("Unauthorized access!")
        return redirect(url_for('login'))

    comment = Comment.query.get(comment_id)
    if not comment:
        flash("Comment not found!")
        return redirect(url_for('admin_dashboard'))

    db.session.delete(comment)
    db.session.commit()

    flash("Comment deleted successfully!")
    return redirect(url_for('admin_dashboard'))



@app.route('/delete_carbon_footprint/<int:footprint_id>', methods=['POST'])
def delete_carbon_footprint(footprint_id):
    if not session.get('is_admin'):
        flash("Unauthorized access!")
        return redirect(url_for('login'))

    footprint = CarbonFootprint.query.get(footprint_id)
    if not footprint:
        flash("Carbon footprint not found!")
        return redirect(url_for('admin_dashboard'))

    db.session.delete(footprint)
    db.session.commit()

    flash("Carbon footprint data deleted successfully!")
    return redirect(url_for('admin_dashboard'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
