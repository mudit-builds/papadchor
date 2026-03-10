"""
Authentication module for SLA Calculator
Validates user credentials against Oracle database
"""
import cx_Oracle
import keyring


def validate_user(user_name, pwd):
    """
    Validate user credentials against the database
    
    Args:
        user_name (str): Username to validate
        pwd (str): Password to validate
        
    Returns:
        bool: True if credentials are valid, False otherwise
    """
    connection = None
    cursor = None
    try:
        conn = cx_Oracle.makedsn("SCAN_RTQ_PROD01_APP.internal.colt.net", "1977", service_name="RTQ_PROD01_APP")
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
        cursor.execute(query, {"usernm": user_name, "pwd": pwd})
        result = cursor.fetchone()
        
        return result is not None
    except Exception as e:
        print(f"Authentication error: {str(e)}")
        return False
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()
