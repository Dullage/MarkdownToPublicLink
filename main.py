from flask import Flask, Markup, render_template, url_for, redirect, request,\
    jsonify, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from os import environ, path
from markdown2 import markdown
from uuid import uuid4
from bs4 import BeautifulSoup
import language

BASE_PATH = environ["MDTPL_BASE_PATH"]
PUBLISH_PASSWORD = environ["MDTPL_PUBLISH_PASSWORD"]

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] \
    = "sqlite:///database.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

VALID_EXTENSIONS = [
    ".md",
    ".markdown",
    ".mdown",
    ".mkdn",
    ".mkd"
]


# region Helper Functions
def password_invalid(password):
    if password is None:
        return True
    if password != PUBLISH_PASSWORD:
        return True
    return False


def msg(message, code, api_call):
    """If api_call is True the message is returned as a JSON string under the
    key of message. If False the user is presented with the message on a
    formatted HTML page. Note: The code is only used if api_call is True."""
    if api_call:
        return jsonify({
            "message": message
        }), code
    else:
        return render_template(
            "message.html",
            message=message
        ), code
# endregion


# region Database
class PublishedFile(db.Model):
    __tablename__ = 'published_file'

    id = db.Column(db.String(36), primary_key=True)
    filename = db.Column(db.String(255), unique=True, nullable=False)
    parent_id = db.Column(db.String(36), db.ForeignKey('published_file.id'))

    def __init__(self, filename, parent_id=None):
        self.id = str(uuid4())
        self.filename = filename
        self.parent_id = parent_id

    parent = db.relationship(
        "PublishedFile",
        backref="attachments",
        remote_side=[id]
    )

    @property
    def filename_ex_ext(self):
        return path.splitext(self.filename)[0]

    @property
    def url(self):
        return url_for("content", id=self.id, _external=True)

    @property
    def file_path(self):
        return path.join(BASE_PATH, self.filename)

    def unpublish_attachments(self):
        for attachment in self.attachments:
            db.session.delete(attachment)
        db.session.commit()

    def publish_attachments(self, html):
        self.unpublish_attachments()

        soup = BeautifulSoup(html, 'html.parser')

        images = soup.find_all("img")
        for image in images:
            if "/" not in image["src"]:
                db.session.add(PublishedFile(image["src"], parent_id=self.id))
                image["src"] = f"/{self.id}/{image['src']}"

        file_links = soup.find_all("a")
        for file in file_links:
            if "/" not in file["href"]:
                db.session.add(PublishedFile(file["href"], parent_id=self.id))
                file["href"] = f"/{self.id}/{file['href']}"

        db.session.commit()

        return Markup(soup)

    @property
    def html(self):
        with open(self.file_path, "r") as file:
            html = markdown(
                file.read(),
                extras=[
                    "fenced-code-blocks",
                    "tag-friendly",
                    "tables",
                    "header-ids"
                ]
            )

        html = self.publish_attachments(html)

        return html

    @property
    def is_missing(self):
        if path.isfile(self.file_path):
            return False
        else:
            return True


db.create_all()
# endregion


# region Routes
@app.route("/")
def index():
    return render_template(
        "message.html",
        message=language.INDEX_MESSAGE
    )


@app.route("/publish/<filename>")
@app.route("/api/publish/<filename>")
def publish(filename):
    api_call = (request.url_rule.rule == "/api/publish/<filename>")

    # Password Check
    declared_password = request.headers.get(
        "password",
        request.args.get("password")
    )
    if password_invalid(declared_password):
        return msg(language.INVALID_PASSWORD, 401, api_call)

    # Check the extension
    if path.splitext(filename)[1] not in VALID_EXTENSIONS:
        return msg(language.BAD_EXTENSION, 400, api_call)

    # Check the file exists
    if not path.isfile(path.join(BASE_PATH, filename)):
        return msg(language.FILE_NOT_FOUND, 400, api_call)

    # Already published?
    published_file = PublishedFile.query.filter_by(
        filename=filename
    ).first()

    # Publish
    if published_file is None:
        published_file = PublishedFile(filename)
        db.session.add(published_file)
        db.session.commit()

    if api_call:
        return jsonify({
            "url": published_file.url
        })
    else:
        return redirect(published_file.url)


@app.route("/unpublish/<filename>")
@app.route("/api/unpublish/<filename>")
def unpublish(filename):
    api_call = (request.url_rule.rule == "/api/unpublish/<filename>")

    # Password Check
    declared_password = request.headers.get(
        "password",
        request.args.get("password")
    )
    if password_invalid(declared_password):
        return msg(language.INVALID_PASSWORD, 401, api_call)

    published_file = PublishedFile.query.filter_by(
        filename=filename
    ).first()

    if published_file is None:
        return msg(language.NOT_PUBLISHED, 400, api_call)

    published_file.unpublish_attachments()
    db.session.delete(published_file)
    db.session.commit()

    return msg(language.UNPUBLISHED_CONFIRMATION, 200, api_call)


@app.route("/<id>")
def content(id):
    published_file = PublishedFile.query.filter_by(
        id=id,
        parent_id=None
    ).first()

    if published_file is None:
        return render_template(
            "message.html",
            message=language.LINK_NOT_FOUND
        )

    # Check the file still exists
    if published_file.is_missing:
        return render_template(
            "message.html",
            message=language.FILE_NOT_FOUND
        )

    return render_template(
        "content.html",
        published_file=published_file
    )


@app.route("/<id>/<filename>")
def attachment(id, filename):
    file = PublishedFile.query.filter_by(
        parent_id=id,
        filename=filename
    ).first()

    if file is None:
        return None, 404

    return send_from_directory(BASE_PATH, file.filename)
# endregion
