import os
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, FileField
from wtforms.validators import DataRequired
from werkzeug.utils import secure_filename
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
import vercel  # For Vercel runtime utilities (kept for compatibility)

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'your-flask-secret-key')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Database configuration
database_url = os.environ.get('DATABASE_URL')
if database_url:
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
else:
    if os.environ.get('VERCEL'):
        instance_path = "/tmp/instance"
    else:
        instance_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance')
    
    try:
        os.makedirs(instance_path, exist_ok=True)
        print(f"Created directory: {instance_path}")
    except OSError as e:
        print(f"Error creating directory {instance_path}: {e}")
        if e.errno != 30 and e.errno != 13:
            raise
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(instance_path, "blog.db")}'

# Initialize SQLAlchemy
db = SQLAlchemy(app)

# Secret key
SECRET_KEY = 'moo'

# Blog post model
class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    image_url = db.Column(db.String(200), nullable=True)

# Form
class PostForm(FlaskForm):
    title = StringField('Title', validators=[DataRequired()])
    content = TextAreaField('Content', validators=[DataRequired()])
    image = FileField('Image')

# Create database tables
with app.app_context():
    db.create_all()

# Allowed file check
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'gif'}

# Secret key check
def check_secret_key():
    secret = request.form.get('secret_key')
    if secret != SECRET_KEY:
        flash('Invalid secret key!', 'error')
        return False
    return True

@app.route('/')
def index():
    try:
        posts = Post.query.all()
        return render_template('index.html', posts=posts)
    except Exception as e:
        flash(f'Error loading posts: {str(e)}', 'error')
        return render_template('index.html', posts=[])

@app.route('/add', methods=['GET', 'POST'])
def add_post():
    form = PostForm()
    if request.method == 'POST':
        if not check_secret_key():
            return render_template('secret_key.html', action='add', form=form)
        if form.validate_on_submit():
            try:
                title = form.title.data
                content = form.content.data
                image_url = None
                if form.image.data and allowed_file(form.image.data.filename):
                    try:
                        filename = secure_filename(form.image.data.filename)
                        # Use /tmp/uploads for Vercel, static/uploads for local
                        upload_dir = '/tmp/uploads' if os.environ.get('VERCEL') else os.path.join(app.static_folder, 'uploads')
                        os.makedirs(upload_dir, exist_ok=True)
                        upload_path = os.path.join(upload_dir, filename)
                        print(f"Saving image to: {upload_path}")
                        form.image.data.save(upload_path)
                        # Generate absolute URL for the image
                        image_url = url_for('static', filename=f'uploads/{filename}', _external=True) if not os.environ.get('VERCEL') else f"{request.url_root}static/uploads/{filename}"
                        print(f"Generated image URL: {image_url}")
                    except Exception as e:
                        flash(f'Image upload failed: {str(e)}', 'error')
                        print(f"Image save error: {str(e)}")
                        image_url = None
                elif form.image.data:
                    flash('Invalid file type! Only PNG, JPG, JPEG, GIF allowed', 'error')
                    print(f"Invalid file type: {form.image.data.filename}")
                new_post = Post(title=title, content=content, image_url=image_url)
                db.session.add(new_post)
                db.session.commit()
                flash('Post added successfully!', 'success')
                return redirect(url_for('index'))
            except Exception as e:
                flash(f'Error adding post: {str(e)}', 'error')
                print(f"Post creation error: {str(e)}")
        else:
            flash(f'Form validation errors: {form.errors}', 'error')
            print(f"Form validation errors: {form.errors}")
    return render_template('add_post.html', form=form)

@app.route('/edit/<int:post_id>', methods=['GET', 'POST'])
def edit_post(post_id):
    try:
        post = Post.query.get_or_404(post_id)
    except Exception as e:
        flash(f'Error loading post: {str(e)}', 'error')
        return redirect(url_for('index'))
    form = PostForm(obj=post)
    if request.method == 'POST':
        if not check_secret_key():
            return render_template('secret_key.html', action='edit', post_id=post_id, form=form)
        if form.validate_on_submit():
            try:
                post.title = form.title.data
                post.content = form.content.data
                if form.image.data and allowed_file(form.image.data.filename):
                    try:
                        filename = secure_filename(form.image.data.filename)
                        upload_dir = '/tmp/uploads' if os.environ.get('VERCEL') else os.path.join(app.static_folder, 'uploads')
                        os.makedirs(upload_dir, exist_ok=True)
                        upload_path = os.path.join(upload_dir, filename)
                        print(f"Saving image to: {upload_path}")
                        form.image.data.save(upload_path)
                        post.image_url = url_for('static', filename=f'uploads/{filename}', _external=True) if not os.environ.get('VERCEL') else f"{request.url_root}static/uploads/{filename}"
                        print(f"Updated image URL: {post.image_url}")
                    except Exception as e:
                        flash(f'Image upload failed: {str(e)}', 'error')
                        print(f"Image save error: {str(e)}")
                elif form.image.data:
                    flash('Invalid file type! Only PNG, JPG, JPEG, GIF allowed', 'error')
                    print(f"Invalid file type: {form.image.data.filename}")
                db.session.commit()
                flash('Post updated successfully!', 'success')
                return redirect(url_for('index'))
            except Exception as e:
                flash(f'Error updating post: {str(e)}', 'error')
                print(f"Post update error: {str(e)}")
        else:
            flash(f'Form validation errors: {form.errors}', 'error')
            print(f"Form validation errors: {form.errors}")
    return render_template('edit_post.html', post=post, form=form)

@app.route('/delete/<int:post_id>', methods=['POST'])
def delete_post(post_id):
    if not check_secret_key():
        return render_template('secret_key.html', action='delete', post_id=post_id)
    try:
        post = Post.query.get_or_404(post_id)
        db.session.delete(post)
        db.session.commit()
        flash('Post deleted successfully!', 'success')
    except Exception as e:
        flash(f'Error deleting post: {str(e)}', 'error')
    return redirect(url_for('index'))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)