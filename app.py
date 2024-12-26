from flask import Flask, render_template, request, redirect, url_for, session, flash,jsonify 
import requests
from flask_sqlalchemy import SQLAlchemy 
import datetime
import pandas as pd
from matplotlib.figure import Figure
import io
import base64 
import matplotlib.pyplot as plt 
    
from flask_wtf import FlaskForm
from wtforms import FloatField, SubmitField
from wtforms.validators import DataRequired 

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'  
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'secret_key' 

db = SQLAlchemy(app) 
 
 
openweatherMapApiKey ="7d9d91e8a10b95b8d8f7a2c5656e5bf9" 
#API_KEY = '7d9d91e8a10b95b8d8f7a2c5656e5bf9'   

@app.route('/api/weather', methods=['GET'])
def get_weather():
    city = request.args.get('city')  # Get city name from query parameter
    if not city:
        return jsonify({'error': 'City name is required'}), 400

    # OpenWeather API URL
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
     
AQI_API_KEY = '904164073b279b07ff95c1ead5e07cd58eedf0c0'

@app.route('/api/aqi', methods=['GET'])
def get_aqi():
    city = request.args.get('city')  # Get city name from query parameter
    if not city:
        return jsonify({'error': 'City name is required'}), 400

    # AQI API URL
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
    
from flask import Flask, request, jsonify
import requests
from urllib.parse import quote  # Ensure this import is included 


NEWS_API_KEY = 'pub_605312e53e8da917a4a1228232572b28a4267'
@app.route('/api/news', methods=['GET'])
def get_aqi_news():
    city = request.args.get('city')  # Get city name from query parameter
    if not city:
        return jsonify({'error': 'City name is required'}), 400

    # URL-encode the city name to handle spaces and special characters
    encoded_city = quote(city)
    url = f'https://newsdata.io/api/1/news?apikey={NEWS_API_KEY}&q=air quality {encoded_city}'

    try:
        # Make the request to News API
        response = requests.get(url)
        print("Response Status Code:", response.status_code)  # Debugging: log status code
        print("Response Data:", response.text)  # Debugging: log raw response text
        data = response.json()

        if response.status_code == 200:
            articles = data.get('results', [])  # Use 'results' if that's the key for articles in the response
            return jsonify({'articles': articles[:10]})  # Limit to 10 articles
        else:
            error_message = data.get('message', 'Failed to retrieve news')
            print("Error Message:", error_message)  # Debugging: log error message
            return jsonify({'error': error_message}), response.status_code
    except Exception as e:
        # Log any exceptions for debugging
        print("Exception occurred:", str(e))
        return jsonify({'error': str(e)}), 500
   
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    city = db.Column(db.String(100), nullable=True)

    def __init__(self, name, email, password, city):
        self.name = name
        self.email = email
        self.password = password
        self.city = city 
         
           
class CarbonFootprint(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date = db.Column(db.Date, nullable=False, default=datetime.date.today)
    transport = db.Column(db.Float, nullable=False, default=0.0)
    electricity = db.Column(db.Float, nullable=False, default=0.0)
    waste = db.Column(db.Float, nullable=False, default=0.0)
    total = db.Column(db.Float, nullable=False, default=0.0)


@app.route('/', methods=['GET'])
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
            flash("Login successful! Welcome.")
            return redirect(url_for('home'))
        
        flash("Invalid email or password.")
        return redirect(url_for('login'))

    return render_template('login.html')   
@app.route('/leaderboard', methods=['GET'])
def leaderboard():
    # Query for the top users, including their city, ordered by total carbon footprint (descending)
    leaderboard = db.session.query(
        User.name,
        User.city,  # Include city
        db.func.sum(CarbonFootprint.total).label('total_footprint')
    ).join(CarbonFootprint).group_by(User.id).order_by(db.func.sum(CarbonFootprint.total).desc()).all()

    # Add rank to the leaderboard data
    leaderboard_with_rank = [
        {"rank": idx + 1, "name": name, "city": city, "total_footprint": total_footprint}
        for idx, (name, city, total_footprint) in enumerate(leaderboard)
    ]

    return render_template('leaderboard.html', leaderboard=leaderboard_with_rank)


@app.route('/home')
def home():
    if not session.get('logged_in'):
        return redirect(url_for('login'),message="Incorrect Details")
    return render_template('home.html', username=session['username'])


@app.route('/logout')
def logout():
    session.clear()  
    flash("You have logged out successfully.")
    return redirect(url_for('index')) 

    
# WTForm for Carbon Footprint Input
class CarbonFootprintForm(FlaskForm):
    transport = FloatField('Transport (km)', validators=[DataRequired()])
    electricity = FloatField('Electricity (kWh)', validators=[DataRequired()])
    waste = FloatField('Waste (kg)', validators=[DataRequired()])
    submit = SubmitField('Submit')
# Main route for carbon tracker
@app.route('/carbon_tracker', methods=['GET', 'POST'])
def carbon_tracker():
    if not session.get('logged_in'):
        return redirect(url_for('login'))  # Redirect to login if the user is not logged in

    carbon_footprint_result = None  # Variable to store the carbon footprint result

    # Instantiate the form
    form = CarbonFootprintForm()

    if form.validate_on_submit():
        try:
            # Get data from the form
            transport = form.transport.data
            electricity = form.electricity.data
            waste = form.waste.data
            user_id = session['user_id']

            # Calculate the total carbon footprint
            total = transport * 0.25 + electricity * 0.75 + waste * 1.2

            # Create a new CarbonFootprint entry
            entry = CarbonFootprint(user_id=user_id, transport=transport, electricity=electricity, waste=waste, total=total)
            db.session.add(entry)
            db.session.commit()
            flash("Carbon footprint logged successfully!")

            # Set the result for display after form submission
            carbon_footprint_result = total  # Store the result to show it on the page

        except Exception as e:
            flash(f"Error: {str(e)}")

    # Fetch previous entries for graph plotting
    user_id = session['user_id']
    entries = CarbonFootprint.query.filter_by(user_id=user_id).order_by(CarbonFootprint.date).all()

    # Prepare the data for plotting
    dates = [entry.date.strftime('%Y-%m-%d') for entry in entries]
    totals = [entry.total for entry in entries]

    # Create a plot of carbon footprint over time
    fig = plt.figure(figsize=(8, 6))
    ax = fig.add_subplot(111)
    ax.plot(dates, totals, marker='o', color='green', label='Total CO2')
    ax.set_title('Your Carbon Footprint Over Time')
    ax.set_xlabel('Date')
    ax.set_ylabel('Total CO2 (kg)')
    ax.grid(True)
    ax.legend()

    # Customize date labels for better readability
    fig.autofmt_xdate(rotation=45)

    # Convert the plot to a base64 encoded PNG image for embedding in HTML
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    buf.seek(0)
    plot_data = base64.b64encode(buf.getvalue()).decode('utf-8')
    buf.close()

    # Render the HTML template and pass the necessary data
    return render_template('carbon_tracker.html', form=form, entries=entries, plot_data=plot_data, carbon_footprint_result=carbon_footprint_result)

# In-memory storage for posts and comments
posts = []
comments = []
post_id_counter = 1  # To simulate unique post IDs


@app.route('/community', methods=['GET', 'POST'])
def community():
    global posts, post_id_counter
    if request.method == 'POST':
        # Add a new post
        title = request.form.get('title')
        if title:
            username = session.get('username', 'Anonymous')  # Get username from session or default to 'Anonymous'
            new_post = {
                'id': post_id_counter,
                'title': title,
                'username': username,  # Set username from session
                'created_at': 'Just Now',
                'likes': 0,
                'comments': []
            }
            posts.append(new_post)
            post_id_counter += 1
        return redirect(url_for('community'))
    # GET request: Render community page
    return render_template('community.html', posts=posts)



@app.route('/like_post/<int:post_id>', methods=['POST'])
def like_post(post_id):
    # Find the post by ID and increment its likes
    for post in posts:
        if post['id'] == post_id:
            post['likes'] += 1
            break
    return redirect(url_for('community'))

@app.route('/add_comment/<int:post_id>', methods=['POST'])
def add_comment(post_id):
    content = request.form.get('content')
    if content:
        # Retrieve the logged-in user's username from session
        username = session.get('username', 'Anonymous')  # Default to 'Anonymous' if not logged in
        for post in posts:
            if post['id'] == post_id:
                post['comments'].append({
                    'username': username,  # Use the logged-in user's username
                    'content': content
                })
                break
    return redirect(url_for('community'))


if __name__ == '__main__':
    with app.app_context():
        db.create_all()  
    app.run(debug=True)