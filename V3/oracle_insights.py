import cx_Oracle
import keyring
import pandas as pd
import warnings

warnings.filterwarnings("ignore")


def update_sql(sql, data=None):
    """Execute SQL query and return results."""
    conn = cx_Oracle.makedsn(
        "SCAN_RTQ_PROD01_APP.internal.colt.net",
        "1977",
        service_name="RTQ_PROD01_APP"
    )
    user_cred = keyring.get_credential('ORACLE_INSIGHTS', 'INSIGHTS')
    connection = cx_Oracle.connect(
        user=user_cred.username,
        password=user_cred.password,
        dsn=conn,
        encoding='UTF-8',
        nencoding='UTF-8'
    )
    cursor = cx_Oracle.Cursor(connection)
    try:
        if data is not None:
            df = cursor.executemany(sql, data)
        elif sql.upper().startswith(('TRUNCATE', 'MERGE', 'INSERT', 'UPDATE')):
            df = cursor.execute(sql)
        elif sql.upper().startswith(('EXEC', 'BEGIN')):
            sql = 'BEGIN ' + sql.split(" ")[1] + '; END;'
            df = cursor.execute(sql)
        else:
            df = pd.read_sql(sql, con=connection)
        return df
    except Exception as err:
        return err
    finally:
        connection.commit()
        cursor.close()
        connection.close()
