from sqlalchemy import select, update, delete
from sqlalchemy.sql import func
from sqlalchemy.sql.expression import cast
import app.model as m


def sample_text():
    return select(m.Example.name)
 
