import sqlite3
from sqlite3 import Error
import json
import time

class NodesDb:

    COL_NUM = 0
    COL_FROMID = 1
    COL_SHORTNAME = 2
    COL_LONGNAME = 3
    COL_LASTHEARD = 4
    COL_LASTUPDATED = 5
    COL_LASTUPDATEDTEXT = 6
    COL_LATITUDE = 7
    COL_LONGITUDE = 8
    COL_LASTACKTIME = 9
    COL_LASTACKISDIRECT = 10
    COL_LASTACKTEXT = 11

    _sql_create_table = """ CREATE TABLE "nodes" (
                                "num"	INTEGER,
                                "fromId"	text(20),
                                "shortName"	text(20),
                                "longName"	text,
                                "lastHeard"	INTEGER,
                                "lastUpdated"	INTEGER,
                                "lastUpdatedText"	TEXT(30),
                                "latitude"	REAL,
                                "longitude"	REAL,
                                "lastAckTime"	INTEGER,
                                "lastAckIsDirect"	TEXT,
                                "lastAckText"	TEXT,
                                "encrypted"	INTEGER,
                                "comment"	TEXT,
                                PRIMARY KEY("num")
                            );                            
                        """

    def __init__(self, db_file):
        self.db_file = db_file
        self.conn = None
        try:
            self.conn = sqlite3.connect(db_file, check_same_thread=False, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
            print(sqlite3.version)
            self.execute_sql(self._sql_create_table)
        except Error as e:
            print(e)

    def close(self):
        self.conn.close()

    def execute_sql_args(self, sql, args):
        cur = self.conn.cursor()
        try:
            cur.execute(sql, args)
            self.conn.commit()
        except:
            print("sql :", sql)
            print("args:", args)
            raise
        finally:
            cur.close()
        return cur.rowcount          

    def execute_sql(self, sql_query):
        rows = None
        c = self.conn.cursor()
        try:
            c.execute(sql_query)
            rows = c.fetchall()
        except Error as e:
            print(e)
        finally:
            c.close()
        return rows

    def update_nodeNames_by_object(self, nodeObject):
        num = nodeObject['num']
        lastHeard = nodeObject.get('lastHeard', 0)
        lastUpdated = int(time.time())
        if 'user' in nodeObject:
            fromId = nodeObject['user']['id']
            shortName = nodeObject['user']['shortName']
            longName = nodeObject['user']['longName']
        else:    
            fromId = "?"
            shortName = "?"
            longName = "?"
        return self.update_nodeNames(num, fromId, shortName, longName, lastHeard)
    
    def update_nodeNames(self, num, fromId, shortName, longName, lastHeard):
        args = (num, fromId, shortName, longName, lastHeard, fromId, shortName, longName, lastHeard)
        sql = "INSERT INTO nodes(num, fromId, shortName, longName, lastHeard) VALUES(?,?,?,?,?) ON CONFLICT (num) DO UPDATE SET fromId=?, shortName=?, longName=?, lastHeard=?;"
        return self.execute_sql_args(sql, args)

    def update_lastUpdated(self, num, lastUpdatedEpoch):
        args = (num, lastUpdatedEpoch, lastUpdatedEpoch, lastUpdatedEpoch, lastUpdatedEpoch)
        sql = "INSERT INTO nodes(num, lastUpdated, lastUpdatedText) VALUES(?,?, datetime(?, 'unixepoch', 'localtime')) ON CONFLICT (num) DO UPDATE SET lastUpdated=?, lastUpdatedText=datetime(?, 'unixepoch', 'localtime');"
        return self.execute_sql_args(sql, args)

    def update_position(self, num, latitudeDouble, longitudeDouble):
        args = (num, latitudeDouble, longitudeDouble, latitudeDouble, longitudeDouble)
        sql = "INSERT INTO nodes(num, latitude, longitude) VALUES(?,?,?) ON CONFLICT (num) DO UPDATE SET latitude=?, longitude=?;"
        return self.execute_sql_args(sql, args)

    def update_ack(self, num, ackTimeEpoch, ackText, ackIsDirect):
        args = (num, ackTimeEpoch, ackText, ackIsDirect, ackTimeEpoch, ackText, ackIsDirect)
        sql = "INSERT OR REPLACE INTO nodes(num, lastAckTime, lastAckText, lastAckIsDirect) VALUES(?,?,?,?) ON CONFLICT (num) DO UPDATE SET lastAckTime=?, lastAckText=?, lastAckIsDirect=?;"
        return self.execute_sql_args(sql, args)

    def update_encrypted(self, num, isEncrypted):
        args = (num, isEncrypted,isEncrypted)
        sql = "INSERT OR REPLACE INTO nodes(num, encrypted) VALUES(?,?) ON CONFLICT (num) DO UPDATE SET encrypted=?;"
        return self.execute_sql_args(sql, args)

    def get_node(self, num):
        """ Returns the first tuple
        """
        sql = f"SELECT * FROM nodes WHERE num='{num}';"
        rows = self.execute_sql(sql)
        # rows will be a (row#)(col#)
        if rows and len(rows):
            #only return the 1st tuple
            return rows[0]
        else:
            return None

