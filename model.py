from peewee import *

db = SqliteDatabase('db.sqlite3')


class Query(Model):
    user_id = IntegerField()
    username = CharField()
    creation_date = DateTimeField()
    origin = CharField(null=True)
    destination = CharField(null=True)
    start_date = DateField(null=True)
    round_trip = BooleanField(default=False)
    end_date = DateField(null=True)
    min_days = IntegerField(null=True)
    max_days = IntegerField(null=True)
    cancelled = BooleanField(default=False)

    class Meta:
        database = db


db.connect()
if not db.table_exists('Query'):
    db.create_tables([Query])
db.close()
