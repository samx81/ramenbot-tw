import psycopg2,sqlite3,psycopg2.extras
import os
uri = "postgres://fbmnkbtvzzzcyj:bd94f7412bded46a97eaee7a1b7c8b8ff096871735d78608deb9f5932f450243@ec2-54-83-196-179.compute-1.amazonaws.com:5432/d39tbgvraon9tp"

mode = os.getenv("env")
basic_query_str = "select name,loc,weekday,opening,soup,type,price,gmapid from ramenya "

def checkenv():
    # if mode == "dev":
    #     conn = sqlite3.connect('test.db')
    #     conn.row_factory = sqlite3.Row
    #     cur = conn.cursor()
    # elif mode == "prod":
    #     DATABASE_URL = os.environ['DATABASE_URL']
    conn = psycopg2.connect(uri, sslmode='require')
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    return cur

def check_dub(gmapkey):
    cur = checkenv()
    s = "select * from ramenya where gmapid ='%s';" % gmapkey

    cur.execute(s)
    return cur.fetchone()

def query_random_id():
    cur = checkenv()
    query_str = "select id from ramenya " \
                "ORDER BY RANDOM() LIMIT 1"
    cur.execute(query_str)
    return cur.fetchone()


def query_begin_with():
    cur = checkenv()
    query_str = basic_query_str + " WHERE loc LIKE 'tp.%' ORDER BY RANDOM();"
    cur.execute(query_str)
    return cur.fetchone()

def query_like(col,key):
    cur = checkenv()
    try:
        query_str = basic_query_str + "where {} LIKE '%{}%' ORDER BY RANDOM()"\
                    .format(col,key)
        cur.execute(query_str)
    except sqlite3.OperationalError:
        print(query_str)
    return cur.fetchone()

def query_specify(col_list, key_list):
    cur = checkenv()
    # ORDER BY RANDOM() LIMIT 1
    try:
        query_str = basic_query_str + "where {} ORDER BY RANDOM()"
        query_str = query_str.format(" and ".join("{0} = '{1}'".format(x, y)
                                          for x, y in zip(col_list, key_list)))
        cur.execute(query_str)
    except sqlite3.OperationalError:
        print(query_str)

    # TODO: empty return handling
    return cur.fetchone()
def query_time(weekday,time):
    cur = checkenv()
    try:
        print(weekday,time)
        if weekday is not None:
            query_str = "SELECT * FROM ramenya where (weekday = {weekday} or weekday = -1) and" \
                        " ((opening[1]<'{time}' and opening[2] > '{time}') or" \
                        " (opening[3]<'{time}' and opening[4] > '{time}')) ORDER BY RANDOM();"\
                        .format(weekday = weekday,time=time)
        else:
            query_str = "SELECT * FROM ramenya where" \
                        " ((opening[1]<'{time}' and opening[2] > '{time}') or" \
                        " (opening[3]<'{time}' and opening[4] > '{time}')) ORDER BY RANDOM();" \
                .format(time=time)
        cur.execute(query_str)
    except sqlite3.OperationalError:
        print(query_str)
    return cur.fetchone()

def insert_new(list):
    s = "insert into ramenya (name, gmapid,loc,weekday,opening,soup,type,price,note) " \
        "values ('%s','%s','%s',%s,'{%s}','%s','%s','%s','%s');" \
        % (list[0],list[1],list[2],list[3],list[4],list[5],list[6],list[7],list[8])
    cur = checkenv()
    print(s)
    cur.execute(s)
    cur.connection.commit()
    cur.close()
