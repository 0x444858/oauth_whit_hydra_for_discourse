import psycopg2
from psycopg2 import pool

# db oauth, table change log
ACTION_CODES = {
    'unknown': 0,
    'create_client': 1,
    'delete_client': 2,
    'change_owner': 10,
    'change_client_name': 11,
    'change_redirect_uris': 12,
    'change_scope': 13,
    'reset_client_secret': 14,
    'change_settings': 30
}
TARGET_TYPES = {
    'unknown': 0,
    'client': 1,
    'system_settings': 2
}

# db oauth, table sys_config
DEFAULT_SYSTEM_CONFIGS = {
    "allow_new_client_apply": "t",
    "new_apply_allowed_group_ids": "",
    "doc_url": ""
}


class DbManager:
    page_size = 20

    def __init__(self, config: dict) -> None:
        db_conf = config['db']
        try:
            self._pool_oauth = psycopg2.pool.SimpleConnectionPool(
                1, db_conf['max_conns'],
                database=db_conf['dbname'],
                user=db_conf['user'],
                password=db_conf['password'],
                host=db_conf['host'],
                port=db_conf['port']
            )
            self._pool_hydra = psycopg2.pool.SimpleConnectionPool(
                1, db_conf['max_conns'],
                database=db_conf['hydra_dbname'],
                user=db_conf['user'],
                password=db_conf['password'],
                host=db_conf['host'],
                port=db_conf['port']
            )
            self._run_init()
        except Exception as e:
            raise e

    def _get_pool(self, db_type: str) -> pool.SimpleConnectionPool:
        if db_type == 'oauth':
            assert self._pool_oauth is not None
            return self._pool_oauth
        elif db_type == 'hydra':
            assert self._pool_hydra is not None
            return self._pool_hydra
        else:
            raise ValueError(f"Unknown db type: {db_type}")

    def _execute_internal(self, db_type: str, query: str, params: tuple = None,
                          fetch: bool = False, fetch_one: bool = False):
        conn = None
        cur = None
        pool_obj = self._get_pool(db_type)
        try:
            conn = pool_obj.getconn()
            cur = conn.cursor()
            cur.execute(query, params or ())
            result = None
            if fetch:
                result = cur.fetchall()
            elif fetch_one:
                result = cur.fetchone()
            else:
                conn.commit()
            return result
        except Exception as e:
            if conn:
                try:
                    conn.rollback()
                except:
                    pass
            raise
        finally:
            if cur:
                cur.close()
            if conn:
                pool_obj.putconn(conn)

    def _run_init(self):
        create_table_sql = """
            CREATE TABLE IF NOT EXISTS access_logs (
                id                  SERIAL PRIMARY KEY,
                client_id           TEXT NOT NULL,
                uid                 INTEGER NOT NULL,
                accessed_at         TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                scope_used          TEXT
            );
            CREATE TABLE IF NOT EXISTS change_log (
                record_id           SERIAL PRIMARY KEY,
                target_type         INTEGER NOT NULL,
                target_id           TEXT NOT NULL,
                action_time         TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                action_code         INTEGER NOT NULL,
                operator_uid        INTEGER NOT NULL,
                operator_username   TEXT NOT NULL,
                old_value           TEXT,
                new_value           TEXT,
                reason              TEXT
            );
            CREATE TABLE IF NOT EXISTS sys_config (
                key                 TEXT PRIMARY KEY,
                value               TEXT
            );
        """
        create_index_sql = """
            CREATE INDEX IF NOT EXISTS idx_logs_client_time 
            ON access_logs (client_id, accessed_at DESC)
        """
        self._execute_internal('oauth', create_table_sql)
        self._execute_internal('oauth', create_index_sql)
        for key, value in DEFAULT_SYSTEM_CONFIGS.items():
            self._execute_internal(
                'oauth',
                'INSERT INTO sys_config (key, value) VALUES (%s, %s) ON CONFLICT DO NOTHING',
                (key, value)
            )

    def close_all(self):
        if self._pool_oauth:
            self._pool_oauth.closeall()
        if self._pool_hydra:
            self._pool_hydra.closeall()

    def log_access(self, client_id: str, uid: int, scope_used: list | set) -> None:
        scope_used = ' '.join(scope_used)
        sql = "INSERT INTO access_logs (client_id, uid, scope_used) VALUES (%s, %s, %s)"
        self._execute_internal('oauth', sql, (client_id, uid, scope_used))

    def get_client_by_uid(self, uid_str: str, page: int = 1, uid_all: bool = False) -> list[dict]:
        if page < 1:
            page = 1
        offset = (page - 1) * self.page_size
        if uid_all is True:
            p = (self.page_size, offset)
            where_sql = ""
        else:
            p = (uid_str, self.page_size, offset)
            where_sql = "WHERE owner = %s"
        sql = f"""
            SELECT
                id,
                client_name,
                scope,
                owner,
                EXTRACT(EPOCH FROM created_at)::BIGINT as created_at_ts,
                EXTRACT(EPOCH FROM updated_at)::BIGINT as updated_at_ts,
                redirect_uris
            FROM hydra_client
            {where_sql}
            ORDER BY updated_at DESC
            LIMIT %s OFFSET %s
        """
        result = self._execute_internal('hydra', sql, p, fetch=True)
        return [
            {
                "id": row[0],
                "client_name": row[1],
                "scope": row[2],
                "owner": row[3],
                "created_at": row[4],
                "updated_at": row[5],
                "redirect_uris": row[6]
            }
            for row in result
        ]

    def get_recent_logs(self, uid: int, time_limit: int = None, uid_all: bool = False) -> list[dict]:
        if uid_all is True:
            where_clauses = []
            params_list = []
        else:
            where_clauses = ["uid = %s"]
            params_list = [uid]
        if time_limit is not None:
            where_clauses.append("accessed_at < TO_TIMESTAMP(%s)")
            params_list.append(time_limit)
        where_sql = ('WHERE ' + " AND ".join(where_clauses)) if where_clauses else ''
        sql = f"""
            SELECT
                client_id,
                uid,
                EXTRACT(EPOCH FROM accessed_at)::BIGINT as accessed_at_ts,
                scope_used
            FROM access_logs
            {where_sql}
            ORDER BY accessed_at DESC
            LIMIT %s
        """
        params_list.append(self.page_size)
        result = self._execute_internal('oauth', sql, tuple(params_list), fetch=True)
        return [
            {
                "client_id": row[0],
                "uid": row[1],
                "accessed_at": row[2],
                "scope_used": row[3]
            }
            for row in result
        ]

    def get_client_names(self, client_ids: list) -> dict:
        if not client_ids:
            return {}
        sql = """
            SELECT id, client_name FROM hydra_client 
            WHERE id = ANY(%s)
        """
        result = self._execute_internal('hydra', sql, (client_ids,), fetch=True)
        return {row[0]: row[1] for row in result}

    def get_authorized_clients(self, uid_str: str) -> list[dict]:
        sql = f"""
            SELECT
                client_id,
                granted_scope,
                EXTRACT(EPOCH FROM expires_at)::BIGINT as expires_at_ts,
                subject,
                active
            FROM {{table}}
            WHERE
                subject = %s
                AND expires_at > NOW() AT TIME ZONE 'UTC'
                AND active = TRUE
            ORDER BY expires_at DESC
            LIMIT 100
        """
        access_result = self._execute_internal(
            'hydra', sql.format(table='hydra_oauth2_access'), (uid_str,), fetch=True)
        refresh_result = self._execute_internal(
            'hydra', sql.format(table='hydra_oauth2_refresh'), (uid_str,), fetch=True)
        client_map = {}
        for row in access_result:
            client_id = row[0]
            granted_scope = row[1]
            expires_at = row[2]
            if client_id not in client_map:
                client_map[client_id] = {
                    "granted_scope": set(),
                    "expires_at": expires_at
                }
            if granted_scope:
                client_map[client_id]["granted_scope"].update(granted_scope.split('|'))
            if expires_at > client_map[client_id]["expires_at"]:
                client_map[client_id]["expires_at"] = expires_at
        for row in refresh_result:
            client_id = row[0]
            granted_scope = row[1]
            if client_id not in client_map:
                client_map[client_id] = {
                    "granted_scope": set(),
                    "expires_at": 0
                }
            if granted_scope:
                client_map[client_id]["granted_scope"].update(granted_scope.split('|'))
            client_map[client_id]["expires_at"] = 0
        r = [
            {
                "client_id": cid,
                "granted_scope": list(d['granted_scope']),
                "expires_at": d['expires_at'],
                "uid": uid_str
            }
            for cid, d in client_map.items()
        ]
        r.sort(key=lambda x: (x['expires_at'] != 0, x['expires_at']), reverse=False)
        return r

    def log_change(self, uid: int | str, username: str, target_type: str, target_id: str, action_name: str,
                   old_value: str = None, new_value: str = None, action_reason: str = None):
        action_code = ACTION_CODES.get(action_name.lower(), 0)
        target_type_code = TARGET_TYPES.get(target_type.lower(), 0)
        sql = """
            INSERT INTO change_log (target_type, target_id, action_code, operator_uid, operator_username, 
                reason, old_value, new_value)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        self._execute_internal('oauth', sql,
                               (target_type_code, target_id, action_code, uid, username, action_reason, old_value,
                                new_value))

    def set_sys_config(self, key: str, value: str) -> None:
        sql = """
            INSERT INTO sys_config (key, value) VALUES (%s, %s)
            ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
        """
        self._execute_internal('oauth', sql, (key, value))

    def get_sys_config(self) -> dict:
        sql = """
            SELECT key, value FROM sys_config
        """
        result = self._execute_internal('oauth', sql, fetch=True)
        return {row[0]: row[1] for row in result}

    def get_change_logs(self, filters: dict = None, page: int = 1) -> list[dict]:
        if page < 1:
            page = 1
        offset = (page - 1) * self.page_size
        where_clauses = []
        params_list = []
        if filters:
            if filters.get('target_type', '') != '':
                where_clauses.append("target_type = %s")
                params_list.append(int(filters['target_type']))
            if filters.get('action_code', '') != '':
                where_clauses.append("action_code = %s")
                params_list.append(int(filters['action_code']))
            if filters.get('target_id', ''):
                where_clauses.append("target_id LIKE %s")
                params_list.append(f"%{filters['target_id']}%")
            if filters.get('old_value', ''):
                where_clauses.append("old_value LIKE %s")
                params_list.append(f"%{filters['old_value']}%")
            if filters.get('new_value', ''):
                where_clauses.append("new_value LIKE %s")
                params_list.append(f"%{filters['new_value']}%")
            if filters.get('time_start', ''):
                where_clauses.append("EXTRACT(EPOCH FROM action_time)::BIGINT >= %s")
                params_list.append(int(filters['time_start']))
            if filters.get('time_end', ''):
                where_clauses.append("EXTRACT(EPOCH FROM action_time)::BIGINT <= %s")
                params_list.append(int(filters['time_end']))
            if filters.get('operator_uid', ''):
                where_clauses.append("operator_uid = %s")
                params_list.append(int(filters['operator_uid']))
            if filters.get('operator_username', ''):
                where_clauses.append("operator_username LIKE %s")
                params_list.append(f"%{filters['operator_username']}%")
            if filters.get('reason', ''):
                where_clauses.append("reason LIKE %s")
                params_list.append(f"%{filters['reason']}%")
        where_sql = ('WHERE ' + " AND ".join(where_clauses)) if where_clauses else ''
        sql = f"""
            SELECT
                record_id,
                target_type,
                target_id,
                EXTRACT(EPOCH FROM action_time)::BIGINT as action_time_ts,
                action_code,
                operator_uid,
                operator_username,
                old_value,
                new_value,
                reason
            FROM change_log
            {where_sql}
            ORDER BY action_time DESC
            LIMIT %s OFFSET %s
        """
        params_list.extend([self.page_size, offset])
        result = self._execute_internal('oauth', sql, tuple(params_list), fetch=True)
        return [
            {
                "record_id": row[0],
                "target_type": row[1],
                "target_id": row[2],
                "action_time": row[3],
                "action_code": row[4],
                "operator_uid": row[5],
                "operator_username": row[6],
                "old_value": row[7],
                "new_value": row[8],
                "reason": row[9]
            }
            for row in result
        ]
