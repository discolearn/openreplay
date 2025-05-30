import logging

import redis
import requests

# from confluent_kafka.admin import AdminClient
from decouple import config

from chalicelib.utils import pg_client, ch_client
from chalicelib.utils.TimeUTC import TimeUTC

logger = logging.getLogger(__name__)


def app_connection_string(name, port, path):
    namespace = config("POD_NAMESPACE", default="app")
    conn_string = config("CLUSTER_URL", default="svc.cluster.local")
    return f"http://{name}.{namespace}.{conn_string}:{port}/{path}"


HEALTH_ENDPOINTS = {
    "alerts": app_connection_string("alerts-openreplay", 8888, "health"),
    "assets": app_connection_string("assets-openreplay", 8888, "metrics"),
    "assist": app_connection_string("assist-openreplay", 8888, "health"),
    "chalice": app_connection_string("chalice-openreplay", 8888, "metrics"),
    "db": app_connection_string("db-openreplay", 8888, "metrics"),
    "ender": app_connection_string("ender-openreplay", 8888, "metrics"),
    "heuristics": app_connection_string("heuristics-openreplay", 8888, "metrics"),
    "http": app_connection_string("http-openreplay", 8888, "metrics"),
    "ingress-nginx": app_connection_string("ingress-nginx-openreplay", 80, "healthz"),
    "integrations": app_connection_string("integrations-openreplay", 8888, "metrics"),
    "sink": app_connection_string("sink-openreplay", 8888, "metrics"),
    "sourcemapreader": app_connection_string(
        "sourcemapreader-openreplay", 8888, "health"
    ),
    "storage": app_connection_string("storage-openreplay", 8888, "metrics"),
}


def __check_database_pg(*_):
    fail_response = {
        "health": False,
        "details": {"errors": ["Postgres health-check failed"]},
    }
    with pg_client.PostgresClient() as cur:
        try:
            cur.execute("SHOW server_version;")
            # server_version = cur.fetchone()
        except Exception as e:
            logger.error("!! health failed: postgres not responding")
            logger.exception(e)
            return fail_response
        try:
            cur.execute("SELECT openreplay_version() AS version;")
            # schema_version = cur.fetchone()
        except Exception as e:
            logger.error("!! health failed: openreplay_version not defined")
            logger.exception(e)
            return fail_response
    return {
        "health": True,
        "details": {
            # "version": server_version["server_version"],
            # "schema": schema_version["version"]
        },
    }


def __always_healthy(*_):
    return {"health": True, "details": {}}


def __check_be_service(service_name):
    def fn(*_):
        fail_response = {
            "health": False,
            "details": {"errors": ["server health-check failed"]},
        }
        try:
            results = requests.get(HEALTH_ENDPOINTS.get(service_name), timeout=2)
            if results.status_code != 200:
                logger.error(
                    f"!! issue with the {service_name}-health code:{results.status_code}"
                )
                logger.error(results.text)
                # fail_response["details"]["errors"].append(results.text)
                return fail_response
        except requests.exceptions.Timeout:
            logger.error(f"!! Timeout getting {service_name}-health")
            # fail_response["details"]["errors"].append("timeout")
            return fail_response
        except Exception as e:
            logger.error(f"!! Issue getting {service_name}-health response")
            logger.exception(e)
            try:
                logger.error(results.text)
                # fail_response["details"]["errors"].append(results.text)
            except Exception:
                logger.error("couldn't get response")
                # fail_response["details"]["errors"].append(str(e))
            return fail_response
        return {"health": True, "details": {}}

    return fn


def __check_redis(*_):
    fail_response = {
        "health": False,
        "details": {"errors": ["server health-check failed"]},
    }
    if config("REDIS_STRING", default=None) is None:
        # fail_response["details"]["errors"].append("REDIS_STRING not defined in env-vars")
        return fail_response

    try:
        r = redis.from_url(config("REDIS_STRING"), socket_timeout=2)
        r.ping()
    except Exception as e:
        logger.error("!! Issue getting redis-health response")
        logger.exception(e)
        # fail_response["details"]["errors"].append(str(e))
        return fail_response

    return {
        "health": True,
        "details": {
            # "version": r.execute_command('INFO')['redis_version']
        },
    }


def __check_SSL(*_):
    fail_response = {
        "health": False,
        "details": {"errors": ["SSL Certificate health-check failed"]},
    }
    try:
        requests.get(config("SITE_URL"), verify=True, allow_redirects=True)
    except Exception as e:
        logger.error("!! health failed: SSL Certificate")
        logger.exception(e)
        return fail_response
    return {"health": True, "details": {}}


def __get_sessions_stats(tenant_id, *_):
    with pg_client.PostgresClient() as cur:
        constraints = ["projects.deleted_at IS NULL"]
        if tenant_id:
            constraints.append("tenant_id=%(tenant_id)s")
        query = cur.mogrify(
            f"""SELECT COALESCE(SUM(sessions_count),0) AS s_c, 
                                       COALESCE(SUM(events_count),0) AS e_c
                                FROM public.projects_stats
                                     INNER JOIN public.projects USING(project_id)
                                WHERE {" AND ".join(constraints)};""",
            {"tenant_id": tenant_id},
        )
        cur.execute(query)
        row = cur.fetchone()
    return {"numberOfSessionsCaptured": row["s_c"], "numberOfEventCaptured": row["e_c"]}


def get_health(tenant_id=None):
    health_map = {
        "databases": {
            "postgres": __check_database_pg,
            "clickhouse": __check_database_ch,
        },
        "ingestionPipeline": {
            **(
                {"redis": __check_redis}
                if config("REDIS_STRING", default=None)
                and len(config("REDIS_STRING")) > 0
                else {}
            ),
            # "kafka": __check_kafka
            "kafka": __always_healthy,
        },
        "backendServices": {
            "alerts": __check_be_service("alerts"),
            "assets": __check_be_service("assets"),
            "assist": __check_be_service("assist"),
            "chalice": __always_healthy,
            "db": __check_be_service("db"),
            "ender": __check_be_service("ender"),
            "frontend": __always_healthy,
            "heuristics": __check_be_service("heuristics"),
            "http": __check_be_service("http"),
            "ingress-nginx": __always_healthy,
            "integrations": __check_be_service("integrations"),
            # "quickwit": __check_be_service("quickwit"),
            "sink": __check_be_service("sink"),
            "sourcemapreader": __check_be_service("sourcemapreader"),
            "storage": __check_be_service("storage"),
        },
        "details": __get_sessions_stats,
        "ssl": __check_SSL,
    }
    return __process_health(tenant_id=tenant_id, health_map=health_map)


def __process_health(tenant_id, health_map):
    response = dict(health_map)
    for parent_key in health_map.keys():
        if config(f"SKIP_H_{parent_key.upper()}", cast=bool, default=False):
            response.pop(parent_key)
        elif isinstance(health_map[parent_key], dict):
            for element_key in health_map[parent_key]:
                if config(
                    f"SKIP_H_{parent_key.upper()}_{element_key.upper()}",
                    cast=bool,
                    default=False,
                ):
                    response[parent_key].pop(element_key)
                else:
                    response[parent_key][element_key] = health_map[parent_key][
                        element_key
                    ](tenant_id)
        else:
            response[parent_key] = health_map[parent_key](tenant_id)
    return response


def cron():
    with pg_client.PostgresClient() as cur:
        query = cur.mogrify(
            """SELECT projects.project_id,
                                      projects.created_at,
                                      projects.sessions_last_check_at,
                                      projects.first_recorded_session_at,
                                      projects_stats.last_update_at
                                FROM public.projects
                                     LEFT JOIN public.projects_stats USING (project_id)
                                WHERE projects.deleted_at IS NULL
                                ORDER BY project_id;"""
        )
        cur.execute(query)
        rows = cur.fetchall()
        for r in rows:
            insert = False
            if r["last_update_at"] is None:
                # never counted before, must insert
                insert = True
                if r["first_recorded_session_at"] is None:
                    if r["sessions_last_check_at"] is None:
                        count_start_from = r["created_at"]
                    else:
                        count_start_from = r["sessions_last_check_at"]
                else:
                    count_start_from = r["first_recorded_session_at"]

            else:
                # counted before, must update
                count_start_from = r["last_update_at"]

            count_start_from = TimeUTC.datetime_to_timestamp(count_start_from)
            params = {
                "project_id": r["project_id"],
                "start_ts": count_start_from,
                "end_ts": TimeUTC.now(),
                "sessions_count": 0,
                "events_count": 0,
            }

            query = cur.mogrify(
                """SELECT COUNT(1) AS sessions_count,
                                          COALESCE(SUM(events_count),0) AS events_count
                                   FROM public.sessions
                                   WHERE project_id=%(project_id)s
                                      AND start_ts>=%(start_ts)s
                                      AND start_ts<=%(end_ts)s
                                      AND duration IS NOT NULL;""",
                params,
            )
            cur.execute(query)
            row = cur.fetchone()
            if row is not None:
                params["sessions_count"] = row["sessions_count"]
                params["events_count"] = row["events_count"]

            if insert:
                query = cur.mogrify(
                    """INSERT INTO public.projects_stats(project_id, sessions_count, events_count, last_update_at)
                                       VALUES (%(project_id)s, %(sessions_count)s, %(events_count)s, (now() AT TIME ZONE 'utc'::text));""",
                    params,
                )
            else:
                query = cur.mogrify(
                    """UPDATE public.projects_stats
                                       SET sessions_count=sessions_count+%(sessions_count)s,
                                           events_count=events_count+%(events_count)s,
                                           last_update_at=(now() AT TIME ZONE 'utc'::text)
                                       WHERE project_id=%(project_id)s;""",
                    params,
                )
            cur.execute(query)


# this cron is used to correct the sessions&events count every week
def weekly_cron():
    with pg_client.PostgresClient(long_query=True) as cur:
        query = cur.mogrify(
            """SELECT project_id,
                                      projects_stats.last_update_at
                               FROM public.projects
                                    LEFT JOIN public.projects_stats USING (project_id)
                               WHERE projects.deleted_at IS NULL
                               ORDER BY project_id;"""
        )
        cur.execute(query)
        rows = cur.fetchall()
        for r in rows:
            if r["last_update_at"] is None:
                continue

            params = {
                "project_id": r["project_id"],
                "end_ts": TimeUTC.now(),
                "sessions_count": 0,
                "events_count": 0,
            }

            query = cur.mogrify(
                """SELECT COUNT(1) AS sessions_count,
                                          COALESCE(SUM(events_count),0) AS events_count
                                   FROM public.sessions
                                   WHERE project_id=%(project_id)s
                                      AND start_ts<=%(end_ts)s
                                      AND duration IS NOT NULL;""",
                params,
            )
            cur.execute(query)
            row = cur.fetchone()
            if row is not None:
                params["sessions_count"] = row["sessions_count"]
                params["events_count"] = row["events_count"]

            query = cur.mogrify(
                """UPDATE public.projects_stats
                                   SET sessions_count=%(sessions_count)s,
                                       events_count=%(events_count)s,
                                       last_update_at=(now() AT TIME ZONE 'utc'::text)
                                   WHERE project_id=%(project_id)s;""",
                params,
            )
            cur.execute(query)


def __check_database_ch(*_):
    fail_response = {
        "health": False,
        "details": {"errors": ["server health-check failed"]},
    }
    with ch_client.ClickHouseClient() as ch:
        try:
            server_version = ch.execute("SELECT version() AS server_version;")
        except Exception as e:
            logger.error("!! health failed: clickhouse not responding")
            logger.exception(e)
            return fail_response

        schema_version = ch.execute(
            """SELECT 1
                                       FROM system.functions
                                       WHERE name = 'openreplay_version';"""
        )
        if len(schema_version) > 0:
            schema_version = ch.execute("SELECT openreplay_version() AS version;")
            schema_version = schema_version[0]["version"]
        else:
            logger.error("!! health failed: clickhouse schema is outdated")
            schema_version = "unknown"
            # fail_response["details"]["errors"].append("clickhouse schema is outdated")
            return fail_response
    return {
        "health": True,
        "details": {
            # "version": server_version[0]["server_version"],
            # "schema": schema_version,
            # **errors
        },
    }


# def __check_kafka(*_):
#     fail_response = {
#         "health": False,
#         "details": {"errors": ["server health-check failed"]}
#     }
#     if config("KAFKA_SERVERS", default=None) is None:
#         fail_response["details"]["errors"].append("KAFKA_SERVERS not defined in env-vars")
#         return fail_response
#
#     try:
#         a = AdminClient({'bootstrap.servers': config("KAFKA_SERVERS"), "socket.connection.setup.timeout.ms": 3000})
#         topics = a.list_topics().topics
#         if not topics:
#             raise Exception('topics not found')
#
#     except Exception as e:
#         logger.error("!! Issue getting kafka-health response")
#         logger.exception(e)
#         fail_response["details"]["errors"].append(str(e))
#         return fail_response
#
#     return {
#         "health": True,
#         "details": {}
#     }
