import logging
import time
from threading import Semaphore

import psycopg2
import psycopg2.extras
from decouple import config
from psycopg2 import pool

logger = logging.getLogger(__name__)

_PG_CONFIG = {"host": config("pg_host"),
              "database": config("pg_dbname"),
              "user": config("pg_user"),
              "password": config("pg_password"),
              "port": config("pg_port", cast=int),
              "application_name": config("APP_NAME", default="PY")}
PG_CONFIG = dict(_PG_CONFIG)
if config("PG_TIMEOUT", cast=int, default=0) > 0:
    PG_CONFIG["options"] = f"-c statement_timeout={config('PG_TIMEOUT', cast=int) * 1000}"

if config('PG_POOL', cast=bool, default=True):
    PG_CONFIG = {
        **PG_CONFIG,
        # Keepalive settings
        "keepalives": 1,  # Enable keepalives
        "keepalives_idle": 300,  # Seconds before sending keepalive
        "keepalives_interval": 10,  # Seconds between keepalives
        "keepalives_count": 3  # Number of keepalives before giving up
    }


class ORThreadedConnectionPool(psycopg2.pool.ThreadedConnectionPool):
    def __init__(self, minconn, maxconn, *args, **kwargs):
        self._semaphore = Semaphore(maxconn)
        super().__init__(minconn, maxconn, *args, **kwargs)

    def getconn(self, *args, **kwargs):
        self._semaphore.acquire()
        try:
            return super().getconn(*args, **kwargs)
        except psycopg2.pool.PoolError as e:
            if str(e) == "connection pool is closed":
                make_pool()
            raise e

    def putconn(self, *args, **kwargs):
        try:
            super().putconn(*args, **kwargs)
            self._semaphore.release()
        except psycopg2.pool.PoolError as e:
            if str(e) == "trying to put unkeyed connection":
                logger.warning("!!! trying to put unkeyed connection")
                logger.warning(f"env-PG_POOL:{config('PG_POOL', default=None)}")
                return
            raise e


postgreSQL_pool: ORThreadedConnectionPool = None

RETRY_MAX = config("PG_RETRY_MAX", cast=int, default=50)
RETRY_INTERVAL = config("PG_RETRY_INTERVAL", cast=int, default=2)
RETRY = 0


def make_pool():
    if not config('PG_POOL', cast=bool, default=True):
        logger.info("PG_POOL is disabled, not creating a new one")
        return
    global postgreSQL_pool
    global RETRY
    if postgreSQL_pool is not None:
        try:
            postgreSQL_pool.closeall()
        except (Exception, psycopg2.DatabaseError) as error:
            logger.error("Error while closing all connexions to PostgreSQL", exc_info=error)
    try:
        postgreSQL_pool = ORThreadedConnectionPool(config("PG_MINCONN", cast=int, default=4),
                                                   config("PG_MAXCONN", cast=int, default=8),
                                                   **PG_CONFIG)
        if postgreSQL_pool is not None:
            logger.info("Connection pool created successfully")
    except (Exception, psycopg2.DatabaseError) as error:
        logger.error("Error while connecting to PostgreSQL", exc_info=error)
        if RETRY < RETRY_MAX:
            RETRY += 1
            logger.info(f"Waiting for {RETRY_INTERVAL}s before retry n°{RETRY}")
            time.sleep(RETRY_INTERVAL)
            make_pool()
        else:
            raise error


class PostgresClient:
    connection = None
    cursor = None
    long_query = False
    unlimited_query = False

    def __init__(self, long_query=False, unlimited_query=False, use_pool=True):
        self.long_query = long_query
        self.unlimited_query = unlimited_query
        self.use_pool = use_pool
        if unlimited_query:
            long_config = dict(_PG_CONFIG)
            long_config["application_name"] += "-UNLIMITED"
            self.connection = psycopg2.connect(**long_config)
        elif long_query:
            long_config = dict(_PG_CONFIG)
            long_config["application_name"] += "-LONG"
            if config('PG_TIMEOUT_LONG', cast=int, default=1) > 0:
                long_config["options"] = f"-c statement_timeout=" \
                                         f"{config('PG_TIMEOUT_LONG', cast=int, default=5 * 60) * 1000}"
            else:
                logger.info("Disabled timeout for long query")
            self.connection = psycopg2.connect(**long_config)
        elif not use_pool or not config('PG_POOL', cast=bool, default=True):
            single_config = dict(_PG_CONFIG)
            single_config["application_name"] += "-NOPOOL"
            if config('PG_TIMEOUT', cast=int, default=1) > 0:
                single_config["options"] = f"-c statement_timeout={config('PG_TIMEOUT', cast=int, default=30) * 1000}"
            self.connection = psycopg2.connect(**single_config)
        else:
            self.connection = postgreSQL_pool.getconn()

    def __enter__(self):
        if self.cursor is None:
            self.cursor = self.connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            self.cursor.cursor_execute = self.cursor.execute
            self.cursor.execute = self.__execute
            self.cursor.recreate = self.recreate_cursor
        return self.cursor

    def __exit__(self, *args):
        try:
            self.connection.commit()
            self.cursor.close()
            if not self.use_pool or self.long_query or self.unlimited_query:
                self.connection.close()
        except Exception as error:
            logger.error("Error while committing/closing PG-connection", exc_info=error)
            if str(error) == "connection already closed" \
                    and self.use_pool \
                    and not self.long_query \
                    and not self.unlimited_query \
                    and config('PG_POOL', cast=bool, default=True):
                logger.info("Recreating the connexion pool")
                make_pool()
            else:
                raise error
        finally:
            if config('PG_POOL', cast=bool, default=True) \
                    and self.use_pool \
                    and not self.long_query \
                    and not self.unlimited_query:
                postgreSQL_pool.putconn(self.connection)

    def __execute(self, query, vars=None):
        try:
            result = self.cursor.cursor_execute(query=query, vars=vars)
        except psycopg2.Error as error:
            logger.error(f"!!! Error of type:{type(error)} while executing query:")
            logger.error(query)
            logger.info("starting rollback to allow future execution")
            try:
                self.connection.rollback()
            except psycopg2.InterfaceError as e:
                logger.error("!!! Error while rollbacking connection", exc_info=e)
                logger.error("!!! Trying to recreate the cursor")
                self.recreate_cursor()
            raise error
        return result

    def recreate_cursor(self, rollback=False):
        if rollback:
            try:
                self.connection.rollback()
            except Exception as error:
                logger.error("Error while rollbacking connection for recreation", exc_info=error)
        try:
            self.cursor.close()
        except Exception as error:
            logger.error("Error while closing cursor for recreation", exc_info=error)
        self.cursor = None
        return self.__enter__()


async def init():
    logger.info(f">use PG_POOL:{config('PG_POOL', default=True)}")
    make_pool()


async def terminate():
    global postgreSQL_pool
    if postgreSQL_pool is not None:
        try:
            postgreSQL_pool.closeall()
            logger.info("Closed all connexions to PostgreSQL")
        except (Exception, psycopg2.DatabaseError) as error:
            logger.error("Error while closing all connexions to PostgreSQL", exc_info=error)
