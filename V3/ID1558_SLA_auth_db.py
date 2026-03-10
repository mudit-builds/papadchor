import cx_Oracle
import keyring


def validate_user(user_name, pwd):
    """Validate user credentials against Oracle database."""
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
    cursor = connection.cursor()
    user_name = user_name.lower()
    query = """
        SELECT * FROM OI_RTQM.ID1558_SLA_CALCULATOR_TOOL
        WHERE LOWER(USER_NAME) = :usernm
        AND PASSWORD = :pwd
    """
    cursor.execute(query, {
        "usernm": user_name,
        "pwd": pwd
    })

    result = cursor.fetchone()
    cursor.close()
    connection.close()

    return result is not None
