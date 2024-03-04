from flask import Flask,render_template
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import IntegrityError
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
from werkzeug.utils import secure_filename
import os
import pandas as pd
import numpy as np
import tensorflow as tf
from tensorflow.keras.preprocessing import image
from tensorflow.keras.preprocessing.image import ImageDataGenerator, img_to_array, load_img
from tensorflow.keras import Model
from sklearn.utils import shuffle
from tqdm import tqdm
import requests
import plotly.graph_objects as go
import urllib.request
import json

app = Flask(__name__)

app.secret_key = 'MYSECRETKEY'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False                

db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), nullable=False)
    password = db.Column(db.String(120), nullable=False)
    
def create_tables():
    with app.app_context():
        db.create_all()
        
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'jpg', 'jpeg', 'png'}

def train_val_generators(TRAINING_DIR, VALIDATION_DIR, TEST_DIR):

    train_datagen = ImageDataGenerator(rescale=1./127.5, rotation_range=30, width_shift_range=0.2,height_shift_range=0.2, shear_range=0.2, zoom_range=0.2,horizontal_flip=True, fill_mode='nearest')

    train_generator = train_datagen.flow_from_directory(directory=TRAINING_DIR, batch_size=32,class_mode='binary', target_size=(150, 150))

    valid_or_test_datagen = ImageDataGenerator(rescale=1./127.5)

    validation_generator = valid_or_test_datagen.flow_from_directory(directory=VALIDATION_DIR, batch_size=32,class_mode='binary', target_size=(150, 150))

    test_generator = valid_or_test_datagen.flow_from_directory(directory=TEST_DIR, batch_size=32,class_mode='binary', target_size=(150, 150))
    return train_generator, validation_generator, test_generator

base_dir = 'MODELLING/'
training_dir = os.path.join(base_dir, 'training')
validation_dir = os.path.join(base_dir, 'validation')
testing_dir = os.path.join(base_dir, 'testing')

train_generator, validation_generator, test_generator = train_val_generators(training_dir, validation_dir, testing_dir)

model = tf.keras.models.load_model('brain_tumor.h5')

def prediction(YOUR_IMAGE_PATH):
    img = image.load_img(YOUR_IMAGE_PATH, target_size=(150, 150))
    x = image.img_to_array(img)
    x /= 127.5
    x = np.expand_dims(x, axis=0)

    images = np.vstack([x])
    classes = model.predict(images, batch_size=10)
    score = tf.nn.sigmoid(classes[0])

    class_name = train_generator.class_indices
    class_name_inverted = {y: x for x, y in class_name.items()}

    if classes[0] > 0.5:
        return class_name_inverted[1], 100 * np.max(score)
    else:
        return class_name_inverted[0], 100 * np.max(score)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        
        try:
            user = User(username=username, email=email, password=password)
            db.session.add(user)
            db.session.commit()
            session['user_id'] = user.id
            return redirect(url_for('login'))
        except IntegrityError:
            db.session.rollback()
            flash('Username already exists. Please choose a different username.', 'error')

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username, password=password).first()
        if user:
            session['user_id'] = user.id
            return redirect(url_for('dashboard'))
        else:
            flash('Wrong username or password. Please try again.', 'error')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('index'))

# @app.route('/dashboard')
# def dashboard():
#     return render_template("dashboard.html")

@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    username = None
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
        username = user.username
        if 'file' not in request.files:
            return render_template('dashboard.html', error='No file part')
        file = request.files['file']

        if file.filename == '':
            return render_template('dashboard.html', error='No selected file')

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)

            # Call the prediction function
            result, confidence = prediction(filepath)
            
            # Create a JSON representation of the confidence data
            confidence_data = [{'Metric': 'Confidence', 'Value': confidence}]
            confidence_json = json.dumps(confidence_data)

            return render_template('dashboard.html', result=result, confidence=confidence, image=filename,username=username,plot_data=confidence_json)

        else:
            return render_template('dashboard.html', error='Invalid file format')
        # return render_template('dashboard.html',username=username)
    return render_template('login.html')

if __name__ == '__main__':
    create_tables()
    app.run(debug=True)