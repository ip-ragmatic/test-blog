from flask import Flask, render_template, redirect, url_for, flash
from flask_bootstrap import Bootstrap5
from flask_ckeditor import CKEditor
from datetime import date
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import ForeignKey
from sqlalchemy.exc import NoResultFound
from flask_login import (
    UserMixin,
    login_user,
    LoginManager,
    login_required,
    current_user,
    logout_user,
)
from flask_gravatar import Gravatar
from forms import CreatePostForm, RegisterForm, LoginForm, CommentForm
from deco import admin_required

app = Flask(__name__)
app.config[
    "SECRET_KEY"
] = "4847481bf4275f0199d4ffa0009d5045cd44957a52a3f7ed6ab2fcf38a5700e0"
ckeditor = CKEditor(app)
gravatar = Gravatar(app)
Bootstrap5(app)

##CONNECT TO DB
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///blog.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)


##CONFIGURE TABLES
class User(UserMixin, db.Model):
    __tablename__ = "user"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), nullable=False, unique=True)
    pwhash = db.Column(db.String(100), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    posts = db.relationship("BlogPost", back_populates="author")
    comments = db.relationship("Comment", back_populates="author")

    @property
    def is_admin(self):
        return self.id == 1


class BlogPost(db.Model):
    __tablename__ = "blog_post"

    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(db.Integer, ForeignKey("user.id"))
    author = db.relationship("User", back_populates="posts")
    title = db.Column(db.String(100), unique=True, nullable=False)
    subtitle = db.Column(db.String(100), nullable=False)
    date = db.Column(db.String(100), nullable=False)
    body = db.Column(db.Text, nullable=False)
    img_url = db.Column(db.String(100), nullable=False)
    comments = db.relationship("Comment", back_populates="parent_post")


class Comment(db.Model):
    __tablename__ = "comments"

    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)
    author_id = db.Column(db.Integer, ForeignKey("user.id"))
    author = db.relationship("User", back_populates="comments")
    post_id = db.Column(db.Integer, ForeignKey("blog_post.id"))
    parent_post = db.relationship("BlogPost", back_populates="comments")


with app.app_context():
    db.create_all()

##LOGIN MANAGER
login_manager = LoginManager()
login_manager.init_app(app)


@login_manager.user_loader
def load_user(user_id):
    return db.session.scalar(db.select(User).where(User.id == user_id))


##ROUTING FUNCTIONS
@app.route("/")
def get_all_posts():
    posts = db.session.scalars(db.select(BlogPost))
    return render_template("index.html", all_posts=posts)


@app.route("/register", methods=["GET", "POST"])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        try:
            search_db = db.session.scalars(
                db.select(User).where(User.email == form.email.data)
            ).one()
        except NoResultFound:
            new_user = User(
                email=form.email.data,
                pwhash=generate_password_hash(
                    password=form.pswd.data,
                    method="pbkdf2:sha256:1000000",
                    salt_length=16,
                ),
                name=form.name.data,
            )
            db.session.add(new_user)
            db.session.commit()
            login_user(new_user)
            return redirect(url_for("get_all_posts"))
        else:
            flash("The email entered has already been registered. Try again.", "error")

    return render_template("register.html", form=form)


@app.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        try:
            search_db = db.session.scalars(
                db.select(User).where(User.email == form.email.data)
            ).one()
        except NoResultFound:
            flash("The email you entered doesn't exist. Try again or register this email.", "error")
        else:
            if check_password_hash(search_db.pwhash, form.pswd.data):
                login_user(search_db)
                print(current_user.is_admin)
                return redirect(url_for("get_all_posts"))
            else:
                flash("The password you entered is invalid. Try again.", "error")
    return render_template("login.html", form=form)


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("get_all_posts"))


@app.route("/post/<int:post_id>", methods=["GET", "POST"])
def show_post(post_id):
    requested_post = db.session.scalar(
        db.select(BlogPost).where(BlogPost.id == post_id)
    )
    form = CommentForm()
    if form.validate_on_submit():
        if current_user.is_anonymous:
            flash("You need to be signed up to comment. Login or Register.", "error")
            return redirect(url_for("login"))

        new_comment = Comment(
            text=form.comment.data, 
            author=current_user, 
            parent_post=requested_post
        )
        db.session.add(new_comment)
        db.session.commit()
        return redirect(url_for("show_post", post_id=requested_post.id))

    return render_template("post.html", post=requested_post, form=form)


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/contact")
def contact():
    return render_template("contact.html")


@app.route("/new-post", methods=["GET", "POST"])
@login_required
@admin_required
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author=current_user,
            date=date.today().strftime("%B %-d, %Y"),
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form)


@app.route("/edit-post/<int:post_id>", methods=["GET", "POST"])
@login_required
@admin_required
def edit_post(post_id):
    post = db.session.scalar(db.select(BlogPost).where(BlogPost.id == post_id))
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        # author=post.author,
        body=post.body,
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        # post.author = "Ian" # this can stay the same because only user of post can edit
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))

    return render_template("make-post.html", form=edit_form, is_edit=True)


@app.route("/delete/<int:post_id>")
@login_required
@admin_required
def delete_post(post_id):
    del_post = db.session.scalar(db.select(BlogPost).where(BlogPost.id == post_id))
    db.session.delete(del_post)
    db.session.commit()
    return redirect(url_for("get_all_posts"))


if __name__ == "__main__":
    app.run(debug=True)
