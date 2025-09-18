import os
import cloudinary
import cloudinary.uploader
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, FileField
from wtforms.validators import DataRequired
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
load_dotenv()


app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'your-flask-secret-key')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Cloudinary configuration
cloudinary.config(
    cloud_name=os.environ.get('CLOUDINARY_CLOUD_NAME'),
    api_key=os.environ.get('CLOUDINARY_API_KEY'),
    api_secret=os.environ.get('CLOUDINARY_API_SECRET'),
    secure=True
)

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

print(f"Database URI: {app.config['SQLALCHEMY_DATABASE_URI']}")
db = SQLAlchemy(app)
SECRET_KEY = 'moo'

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    media_url = db.Column(db.String(200), nullable=True)  # Stores Cloudinary URL

class PostForm(FlaskForm):
    title = StringField('Title', validators=[DataRequired()])
    content = TextAreaField('Content', validators=[DataRequired()])
    media = FileField('Media (Image or Video)')

with app.app_context():
    db.create_all()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'webm'}

def check_secret_key():
    secret = request.form.get('secret_key')
    if secret != SECRET_KEY:
        flash('Invalid secret key!', 'error')
        print("Secret key check failed")
        return False
    return True

@app.route('/')
def index():
    try:
        posts = Post.query.all()
        return render_template('index.html', posts=posts)
    except Exception as e:
        flash(f'Error loading posts: {str(e)}', 'error')
        print(f"Error loading posts: {str(e)}")
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
                media_url = None
                if form.media.data and allowed_file(form.media.data.filename):
                    try:
                        filename = secure_filename(form.media.data.filename)
                        if os.environ.get('CLOUDINARY_CLOUD_NAME'):
                            # Upload to Cloudinary
                            upload_result = cloudinary.uploader.upload(
                                form.media.data,
                                public_id=filename.rsplit('.', 1)[0],  # Remove extension for public_id
                                resource_type='auto'  # Detects image or video
                            )
                            media_url = upload_result['secure_url']  # Persistent Cloudinary URL
                            print(f"Uploaded media to Cloudinary: {media_url}")
                        else:
                            # Fallback for local testing without Cloudinary
                            upload_dir = os.path.join(app.static_folder, 'Uploads')
                            os.makedirs(upload_dir, exist_ok=True)
                            upload_path = os.path.join(upload_dir, filename)
                            print(f"Saving media to: {upload_path}")
                            form.media.data.save(upload_path)
                            media_url = url_for('static', filename=f'uploads/{filename}', _external=True)
                            print(f"Generated media URL: {media_url}")
                    except Exception as e:
                        flash(f'Media upload failed: {str(e)}', 'error')
                        print(f"Media upload error: {str(e)}")
                        media_url = None
                elif form.media.data:
                    flash('Invalid file type! Only PNG, JPG, JPEG, GIF, MP4, WebM allowed', 'error')
                    print(f"Invalid file type: {form.media.data.filename}")
                new_post = Post(title=title, content=content, media_url=media_url)
                db.session.add(new_post)
                db.session.commit()
                flash('Post added successfully!', 'success')
                print(f"Post added: {title}, Media URL: {media_url}")
                return redirect(url_for('index'))
            except Exception as e:
                db.session.rollback()  # Rollback on DB error
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
        print(f"Error loading post {post_id}: {str(e)}")
        return redirect(url_for('index'))
    form = PostForm(obj=post)
    if request.method == 'POST':
        if not check_secret_key():
            return render_template('secret_key.html', action='edit', post_id=post_id, form=form)
        if form.validate_on_submit():
            try:
                post.title = form.title.data
                post.content = form.content.data
                if form.media.data and allowed_file(form.media.data.filename):
                    try:
                        filename = secure_filename(form.media.data.filename)
                        if os.environ.get('CLOUDINARY_CLOUD_NAME'):
                            # Upload to Cloudinary
                            upload_result = cloudinary.uploader.upload(
                                form.media.data,
                                public_id=filename.rsplit('.', 1)[0],  # Remove extension for public_id
                                resource_type='auto'  # Detects image or video
                            )
                            post.media_url = upload_result['secure_url']  # Persistent Cloudinary URL
                            print(f"Updated media to Cloudinary: {post.media_url}")
                        else:
                            # Fallback for local testing without Cloudinary
                            upload_dir = os.path.join(app.static_folder, 'Uploads')
                            os.makedirs(upload_dir, exist_ok=True)
                            upload_path = os.path.join(upload_dir, filename)
                            print(f"Saving media to: {upload_path}")
                            form.media.data.save(upload_path)
                            post.media_url = url_for('static', filename=f'uploads/{filename}', _external=True)
                            print(f"Updated media URL: {post.media_url}")
                    except Exception as e:
                        flash(f'Media upload failed: {str(e)}', 'error')
                        print(f"Media upload error: {str(e)}")
                elif form.media.data:
                    flash('Invalid file type! Only PNG, JPG, JPEG, GIF, MP4, WebM allowed', 'error')
                    print(f"Invalid file type: {form.media.data.filename}")
                db.session.commit()
                flash('Post updated successfully!', 'success')
                print(f"Post {post_id} updated")
                return redirect(url_for('index'))
            except Exception as e:
                db.session.rollback()  # Rollback on DB error
                flash(f'Error updating post: {str(e)}', 'error')
                print(f"Post update error: {str(e)}")
        else:
            flash(f'Form validation errors: {form.errors}', 'error')
            print(f"Form validation errors: {form.errors}")
    return render_template('edit_post.html', post=post, form=form)

@app.route('/delete/<int:post_id>', methods=['GET', 'POST'])
def delete_post(post_id):
    try:
        print(f"Attempting to access delete_post with post_id: {post_id}")
        post = Post.query.get_or_404(post_id)
        print(f"Found post: {post.title} (ID: {post_id})")
        if request.method == 'POST':
            print("Processing POST request for deletion")
            if not check_secret_key():
                print("Secret key check failed")
                return render_template('secret_key.html', action='delete', post_id=post_id)
            try:
                db.session.delete(post)
                db.session.commit()
                flash('Post deleted successfully!', 'success')
                print(f"Post {post_id} deleted successfully")
                return redirect(url_for('index'))
            except Exception as e:
                flash(f'Error deleting post: {str(e)}', 'error')
                print(f"Error deleting post: {str(e)}")
                return redirect(url_for('index'))
        print("Rendering secret_key.html for GET request")
        return render_template('secret_key.html', action='delete', post_id=post_id)
    except Exception as e:
        print(f"Internal Server Error in delete_post: {str(e)}")
        flash(f'Internal Server Error: {str(e)}', 'error')
        return redirect(url_for('index'))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)