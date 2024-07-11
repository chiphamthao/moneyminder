from app import app, db
from flask_migrate import Migrate

migrate = Migrate(db)


from flask.cli import main
main(as_module=True)