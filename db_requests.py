import psycopg2.sql as sql
from collections import namedtuple
from operator import itemgetter


Task = namedtuple("Task", ["id", "asks", "helper", "description", "code", "image"])


class DBRequests:
    def __init__(self, **kwargs):
        self.connection = kwargs['connection']
        self.cursor = kwargs['cursor']

    def get_task_id_to_needy(self, person_id):
        stmt = sql.SQL('SELECT {} FROM {} WHERE person_id={} LIMIT 1;').format(
            sql.Identifier('task_id'),
            sql.Identifier('persons_to_help'),
            sql.SQL(str(person_id))
        )
        self.cursor.execute(stmt)
        res = tuple(map(itemgetter(0), self.cursor))
        return res[0] if len(res) != 0 else None

    def get_task(self, task_id):
        def request(task, table, column):
            stmt = sql.SQL('SELECT {} FROM {} WHERE task_id={} LIMIT 1;').format(
                sql.Identifier(column),
                sql.Identifier(table),
                sql.SQL(str(task))
            )
            self.cursor.execute(stmt)
            res = tuple(self.cursor)
            return res[0][0] if len(res) != 0 else None
        return Task(
            id=task_id,
            asks=request(task_id, 'persons_to_help', 'person_id'),
            helper=request(task_id, 'helpers', 'person_id'),
            description=request(task_id, 'descriptions', 'task'),
            code=request(task_id, 'code', 'url'),
            image=request(task_id, 'images', 'url')
        )

    def get_task_id_to_helper(self, person_id):
        stmt = sql.SQL('SELECT {} FROM {} WHERE person_id={} LIMIT 1;').format(
            sql.Identifier('task_id'),
            sql.Identifier('helpers'),
            sql.SQL(str(person_id))
        )
        self.cursor.execute(stmt)
        res = tuple(map(itemgetter(0), self.cursor))
        return res[0] if len(res) != 0 else None

    def ask_help(self, task):
        """helper will be None"""
        def request(table, row):
            stmt = sql.SQL('INSERT INTO {} VALUES ({}, {});').format(
                sql.Identifier(table),
                sql.SQL(str(row[0])),
                sql.SQL(str(row[1]))
            )
            self.cursor.execute(stmt)
            self.connection.commit()

        tables = ('persons_to_help', 'descriptions', 'code', 'images')
        rows = map(lambda t: (task.id, t), (
            task.asks, "'" + task.description + "'", "'" + task.code + "'", "'" + task.image + "'"))
        for tab, rw in zip(tables, rows):
            request(tab, rw)

    def remove_task(self, task):
        def request(table, task_id):
            stmt = sql.SQL('DELETE FROM {} WHERE task_id={};').format(
                sql.Identifier(table),
                sql.SQL(str(task_id))
            )
            self.cursor.execute(stmt)
            self.connection.commit()

        tables = ('persons_to_help', 'descriptions', 'helpers', 'code', 'images')
        for tab in tables:
            request(tab, task.id)

    def get_next_task_to_helper(self):
        stmt = sql.SQL(
            '''
            SELECT persons_to_help.task_id FROM (
            persons_to_help LEFT OUTER JOIN helpers ON persons_to_help.task_id = helpers.task_id
            ) WHERE helpers.task_id is NULL LIMIT 1;
            ''')
        self.cursor.execute(stmt)
        res = tuple(map(itemgetter(0), self.cursor))
        return self.get_task(res[0]) if len(res) != 0 else None

    def take_task_by_helper(self, task_id, person_id):
        stmt = sql.SQL('INSERT INTO helpers VALUES ({}, {});').format(
            sql.SQL(str(task_id)),
            sql.SQL(str(person_id))
        )
        self.cursor.execute(stmt)
        self.connection.commit()

    def helper_drop_task(self, person_id):
        task_id = self.get_task_id_to_helper(person_id)
        if task_id is not None:
            task = self.get_task(task_id)
            self.remove_task(task)
            self.ask_help(task)

    def needy_drop_task(self, person_id):
        task_id = self.get_task_id_to_needy(person_id)
        if task_id is not None:
            self.remove_task(self.get_task(task_id))

    def get_number_of_unsolved(self):
        stmt = sql.SQL(
            '''
            SELECT persons_to_help.task_id FROM (
            persons_to_help LEFT OUTER JOIN helpers ON persons_to_help.task_id = helpers.task_id
            ) WHERE helpers.task_id is NULL;
            ''')
        self.cursor.execute(stmt)
        res = tuple(map(itemgetter(0), self.cursor))
        return len(res)

    def get_number_of_being_solved(self):
        stmt = sql.SQL(
            '''
            SELECT persons_to_help.task_id FROM (
            persons_to_help JOIN helpers ON persons_to_help.task_id = helpers.task_id
            );
            ''')
        self.cursor.execute(stmt)
        res = tuple(map(itemgetter(0), self.cursor))
        return len(res)

    def save_image(self, name, content):
        self.cursor.execute(
            "INSERT INTO imagestorage VALUES (%s,%s);",
            (name, content))
        self.connection.commit()

    def load_image(self, name):
        stmt = sql.SQL("SELECT img FROM imagestorage WHERE c_no='{}' LIMIT 1").format(
            sql.SQL(str(name)),
        )
        self.cursor.execute(stmt)
        res = tuple(map(itemgetter(0), self.cursor))
        return res[0] if len(res) != 0 else None
