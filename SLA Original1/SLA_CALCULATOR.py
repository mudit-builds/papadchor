import io
import os
import re
import zipfile

import pandas as pd
from flask import Flask, flash, redirect, render_template, request, send_file, session, url_for
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from ID1558_SLA_auth_db import validate_user
from oracle_insights import update_sql

png_path = "E:\\Python\\scripts\\templates\\SLA_logo.png"

app = Flask(__name__)
app.secret_key = "a_really_long_and_unique_secret_key_for_session_data"

EDITABLE_DATETIME_COLS = ["Resolved_Time"]
EDITABLE_NUMBER_COLS = [
    "MRC",
    "Targeted Time To Resolution (Min)",
    "Fault Duration (Min)",
    "COLT SLA Metrics (Min)",
    "Amnt in Euro",
    "Cust Delay (Min)",
]
EDITABLE_TEXT_COLS = ["CURRENCY", "SLA%", "SLA Amnt", "REMARKS"]
EDITABLE_COLS = EDITABLE_DATETIME_COLS + EDITABLE_NUMBER_COLS + EDITABLE_TEXT_COLS

COLUMNS = [
    "SR",
    "INC Number",
    "Created",
    "Resolved_Time",
    "Network",
    "Product",
    "Acc Name",
    "Acc Num",
    "Circ",
    "OLO Tier",
    "Resilience",
    "MRC",
    "CURRENCY",
    "SLA%",
    "SLA Amnt",
    "Amnt in Euro",
    "Targeted Time To Resolution (Min)",
    "Fault Duration (Min)",
    "COLT SLA Metrics (Min)",
    "Cust Delay (Min)",
    "REMARKS",
]


def esc_sql(value):
    return str(value).replace("'", "''")


def to_input_datetime(value):
    if value is None:
        return ""
    text = str(value).strip()
    if not text or text.lower() == "none":
        return ""
    if "T" in text and len(text) >= 16:
        return text[:19]
    try:
        dt = pd.to_datetime(text, format="%d-%m-%y %H:%M:%S", errors="raise")
        return dt.strftime("%Y-%m-%dT%H:%M:%S")
    except Exception:
        return ""


def to_db_datetime(value):
    if value is None:
        return ""
    text = str(value).strip()
    if not text or text.lower() == "none":
        return ""
    try:
        dt = pd.to_datetime(text, errors="raise")
        return dt.strftime("%d-%m-%y %H:%M:%S")
    except Exception:
        return text


def to_input_number(value):
    if value is None:
        return ""
    text = str(value).strip()
    if not text or text.lower() == "none":
        return ""
    text = text.replace(",", "")
    try:
        num = float(text)
        if num.is_integer():
            return str(int(num))
        return str(num)
    except Exception:
        return ""


def normalize_records_for_inputs(records):
    for row in records:
        if "Resolved_Time" in row:
            row["Resolved_Time"] = to_input_datetime(row.get("Resolved_Time"))
        for col in EDITABLE_NUMBER_COLS:
            if col in row:
                row[col] = to_input_number(row.get(col))
    return records


def build_in_clause(raw_value):
    values = [x.strip() for x in str(raw_value or "").split(",") if x.strip()]
    if not values:
        return "''"
    safe = [esc_sql(v) for v in values]
    return "'" + "','".join(safe) + "'"


def ensure_dataframe(result):
    if isinstance(result, pd.DataFrame):
        return result
    return pd.DataFrame(columns=COLUMNS)


def query_search(sr_num, inc_num):
    try:
        return update_sql(
            """select "SR","INC Number", "Created"
                ,"Resolved_Time","Network","Product","Acc Name" ,"Acc Num", "Circ",
                "OLO Tier", "Resilience" , MRC, CURRENCY,"SLA%","SLA Amnt",
                "Amnt in Euro", "Targeted Time To Resolution (Min)" , "Fault Duration (Min)" , "COLT SLA Metrics (Min)",
                "Cust Delay (Min)" ,REMARKS
            from (
                SELECT DISTINCT
                    SR_NUM AS "SR",
                    INCIDENT_ID AS "INC Number",
                    to_char(TO_TIMESTAMP(SUBSTR(created,1,18), 'DD-MON-RR HH24.MI.SS', 'NLS_DATE_LANGUAGE=ENGLISH'),'DD-MM-yy hh24:mi:ss') as "Created",
                    to_char(CASE
                        WHEN (LAST_RESTORED IS NOT NULL AND LAST_RESOLVED IS NOT NULL)
                          OR (LAST_RESOLVED IS NULL AND LAST_RESTORED IS NOT NULL)
                          THEN TO_TIMESTAMP(SUBSTR(LAST_RESTORED,1,18), 'DD-MON-RR HH24.MI.SS', 'NLS_DATE_LANGUAGE=ENGLISH')
                        WHEN LAST_RESOLVED IS NOT NULL AND LAST_RESTORED IS NULL
                          THEN TO_TIMESTAMP(SUBSTR(LAST_RESOLVED,1,18), 'DD-MON-RR HH24.MI.SS', 'NLS_DATE_LANGUAGE=ENGLISH')
                        ELSE TO_TIMESTAMP(SUBSTR(CLOSED,1,18), 'DD-MON-RR HH24.MI.SS', 'NLS_DATE_LANGUAGE=ENGLISH')
                    END,'DD-MM-yy hh24:mi:ss') AS "Resolved_Time",
                    T.REGION || ' : ' || ON_OFF_NET AS "Network",
                    CASE
                        WHEN INSTR(UPPER(T.ASSET_DESCRIPTION), UPPER(C.PRODUCT)) > 0 THEN C.PRODUCT
                        ELSE 'NA'
                    END AS "Product",
                    ACCOUNT_NAME as "Acc Name",
                    ACCOUNT_NUMBER as "Acc Num",
                    SERVICE_ID as "Circ",
                    OLO_TIER AS "OLO Tier",
                    RESILIENCE_OPTION AS "Resilience",
                    MRC,
                    CURRENCY,
                    SLA_PERCENTAGE AS "SLA%",
                    SLA_AMNT as "SLA Amnt",
                    MRC_EUR as "Amnt in Euro",
                    TTTR_MINS AS "Targeted Time To Resolution (Min)",
                    MTTR_MINS AS "Fault Duration (Min)",
                    T.SLA_TARGET AS "COLT SLA Metrics (Min)",
                    NVL(CUSTOMER_DELAY_TOTAL_MIN,0) AS "Cust Delay (Min)",
                    REMARKS,
                    row_number() over (partition by SR_NUM, INCIDENT_ID order by length(C.Product) desc) rnk
                FROM OI_RTQM_L1.ID1558_SLA_COMPENSATION_CALCULATOR T
                LEFT JOIN OI_RTQM.SLA_COMPENSATION_CALCULATOR C ON INSTR(UPPER(T.ASSET_DESCRIPTION), UPPER(C.PRODUCT)) > 0
                WHERE (INCIDENT_ID in ("""
            + inc_num
            + """) OR SR_NUM in ("""
            + sr_num
            + """))
                  AND T.INCIDENT_ID not in ('New Record_Done', 'New Record')
            ) where rnk = 1
            order by 2"""
        )
    except Exception:
        return pd.DataFrame(columns=COLUMNS)


def query_search_up(sr_num, inc_num):
    try:
        return update_sql(
            """select "SR","INC Number", "Created"
                ,"Resolved_Time","Network","Product","Acc Name" ,"Acc Num", "Circ",
                "OLO Tier", "Resilience" , MRC, CURRENCY,"SLA%","SLA Amnt",
                "Amnt in Euro", "Targeted Time To Resolution (Min)" , "Fault Duration (Min)" , "COLT SLA Metrics (Min)",
                "Cust Delay (Min)" ,REMARKS
            from (
                SELECT DISTINCT
                    SR_NUM AS "SR",
                    INCIDENT_ID AS "INC Number",
                    to_char(TO_TIMESTAMP(SUBSTR(created,1,18), 'DD-MON-RR HH24.MI.SS', 'NLS_DATE_LANGUAGE=ENGLISH'),'DD-MM-yy hh24:mi:ss') as "Created",
                    NVL(U_Resolved_Time, to_char(CASE
                        WHEN (LAST_RESTORED IS NOT NULL AND LAST_RESOLVED IS NOT NULL)
                          OR (LAST_RESOLVED IS NULL AND LAST_RESTORED IS NOT NULL)
                          THEN TO_TIMESTAMP(SUBSTR(LAST_RESTORED,1,18), 'DD-MON-RR HH24.MI.SS', 'NLS_DATE_LANGUAGE=ENGLISH')
                        WHEN LAST_RESOLVED IS NOT NULL AND LAST_RESTORED IS NULL
                          THEN TO_TIMESTAMP(SUBSTR(LAST_RESOLVED,1,18), 'DD-MON-RR HH24.MI.SS', 'NLS_DATE_LANGUAGE=ENGLISH')
                        ELSE TO_TIMESTAMP(SUBSTR(CLOSED,1,18), 'DD-MON-RR HH24.MI.SS', 'NLS_DATE_LANGUAGE=ENGLISH')
                    END,'DD-MM-yy hh24:mi:ss')) AS "Resolved_Time",
                    T.REGION || ' : ' || ON_OFF_NET AS "Network",
                    CASE
                        WHEN INSTR(UPPER(T.ASSET_DESCRIPTION), UPPER(C.PRODUCT)) > 0 THEN C.PRODUCT
                        ELSE 'NA'
                    END AS "Product",
                    ACCOUNT_NAME as "Acc Name",
                    ACCOUNT_NUMBER as "Acc Num",
                    SERVICE_ID as "Circ",
                    OLO_TIER AS "OLO Tier",
                    RESILIENCE_OPTION AS "Resilience",
                    U_MRC as MRC,
                    NVL(U_CURRENCY, CURRENCY) AS CURRENCY,
                    U_SLA_PERCENTAGE AS "SLA%",
                    U_SLA_AMNT as "SLA Amnt",
                    U_SLA_AMNT_EUR as "Amnt in Euro",
                    U_TTTR_MINS AS "Targeted Time To Resolution (Min)",
                    U_MTTR_MINS AS "Fault Duration (Min)",
                    T.U_SLA_TARGET AS "COLT SLA Metrics (Min)",
                    NVL(U_CUSTOMER_DELAY_TOTAL_MIN,0) AS "Cust Delay (Min)",
                    REMARKS,
                    row_number() over (partition by SR_NUM, INCIDENT_ID order by length(C.Product) desc) rnk
                FROM OI_RTQM_L1.ID1558_SLA_COMPENSATION_CALCULATOR T
                LEFT JOIN OI_RTQM.SLA_COMPENSATION_CALCULATOR C ON INSTR(UPPER(T.ASSET_DESCRIPTION), UPPER(C.PRODUCT)) > 0
                WHERE (INCIDENT_ID in ("""
            + inc_num
            + """) OR SR_NUM in ("""
            + sr_num
            + """))
                  AND T.INCIDENT_ID not in ('New Record_Done', 'New Record')
            ) where rnk = 1
            order by 2"""
        )
    except Exception:
        return pd.DataFrame(columns=COLUMNS)


def u_query_search(all_inc):
    try:
        return update_sql(
            """select "SR","INC Number", "Created"
                ,"Resolved_Time","Network","Product","Acc Name" ,"Acc Num", "Circ",
                "OLO Tier", "Resilience" , MRC, CURRENCY,"SLA%","SLA Amnt",
                "Amnt in Euro", "Targeted Time To Resolution (Min)" , "Fault Duration (Min)" , "COLT SLA Metrics (Min)",
                "Cust Delay (Min)" ,REMARKS
            from (
                SELECT DISTINCT
                    SR_NUM AS "SR",
                    INCIDENT_ID AS "INC Number",
                    to_char(TO_TIMESTAMP(SUBSTR(created,1,18), 'DD-MON-RR HH24.MI.SS', 'NLS_DATE_LANGUAGE=ENGLISH'),'DD-MM-yy hh24:mi:ss') as "Created",
                    NVL(U_Resolved_Time, to_char(CASE
                        WHEN (LAST_RESTORED IS NOT NULL AND LAST_RESOLVED IS NOT NULL)
                          OR (LAST_RESOLVED IS NULL AND LAST_RESTORED IS NOT NULL)
                          THEN TO_TIMESTAMP(SUBSTR(LAST_RESTORED,1,18), 'DD-MON-RR HH24.MI.SS', 'NLS_DATE_LANGUAGE=ENGLISH')
                        WHEN LAST_RESOLVED IS NOT NULL AND LAST_RESTORED IS NULL
                          THEN TO_TIMESTAMP(SUBSTR(LAST_RESOLVED,1,18), 'DD-MON-RR HH24.MI.SS', 'NLS_DATE_LANGUAGE=ENGLISH')
                        ELSE TO_TIMESTAMP(SUBSTR(CLOSED,1,18), 'DD-MON-RR HH24.MI.SS', 'NLS_DATE_LANGUAGE=ENGLISH')
                    END,'DD-MM-yy hh24:mi:ss')) AS "Resolved_Time",
                    T.REGION || ' : ' || ON_OFF_NET AS "Network",
                    CASE
                        WHEN INSTR(UPPER(T.ASSET_DESCRIPTION), UPPER(C.PRODUCT)) > 0 THEN C.PRODUCT
                        ELSE 'NA'
                    END AS "Product",
                    ACCOUNT_NAME as "Acc Name",
                    ACCOUNT_NUMBER as "Acc Num",
                    SERVICE_ID as "Circ",
                    OLO_TIER AS "OLO Tier",
                    RESILIENCE_OPTION AS "Resilience",
                    U_MRC as MRC,
                    NVL(U_CURRENCY, CURRENCY) AS CURRENCY,
                    U_SLA_PERCENTAGE AS "SLA%",
                    U_SLA_AMNT as "SLA Amnt",
                    U_SLA_AMNT_EUR as "Amnt in Euro",
                    U_TTTR_MINS AS "Targeted Time To Resolution (Min)",
                    U_MTTR_MINS AS "Fault Duration (Min)",
                    T.U_SLA_TARGET AS "COLT SLA Metrics (Min)",
                    NVL(U_CUSTOMER_DELAY_TOTAL_MIN,0) AS "Cust Delay (Min)",
                    REMARKS,
                    row_number() over (partition by SR_NUM, INCIDENT_ID order by length(C.Product) desc) rnk
                FROM OI_RTQM_L1.ID1558_SLA_COMPENSATION_CALCULATOR T
                LEFT JOIN OI_RTQM.SLA_COMPENSATION_CALCULATOR C ON INSTR(UPPER(T.ASSET_DESCRIPTION), UPPER(C.PRODUCT)) > 0
                WHERE SR_NUM IN ("""
            + all_inc
            + """)
                  AND T.INCIDENT_ID not in ('New Record_Done', 'New Record')
            ) where rnk = 1
            order by 2"""
        )
    except Exception:
        return pd.DataFrame(columns=COLUMNS)


def report_query(frm_dt, to_dt):
    try:
        return update_sql(
            """select UPDATED_BY, "SR","INC Number", "Created" ,RECALCULATED_TIME
            ,"Resolved_Time","Network","Product","Acc Name" ,"Acc Num", "Circ",
            "OLO Tier", "Resilience" , CURRENCY,
            MRC, "SLA%", "SLA Amnt", "Amnt in Euro", "Targeted Time To Resolution (Min)", "Fault Duration (Min)",
            "COLT SLA Metrics (Min)", "Cust Delay (Min)",
            U_MRC ,"U_SLA%","U_SLA Amnt","U_Targeted Time To Resolution (Min)", "U_Fault Duration (Min)",
            "U_COLT SLA Metrics (Min)", "U_Cust Delay (Min)", REMARKS
            from (
                SELECT DISTINCT UPDATED_BY,
                    SR_NUM AS "SR", RECALCULATED_TIME,
                    INCIDENT_ID AS "INC Number",
                    to_char(TO_TIMESTAMP(SUBSTR(created,1,18), 'DD-MON-RR HH24.MI.SS', 'NLS_DATE_LANGUAGE=ENGLISH'),'DD-MM-yy hh24:mi:ss') as "Created",
                    to_char(CASE
                        WHEN (LAST_RESTORED IS NOT NULL AND LAST_RESOLVED IS NOT NULL)
                          OR (LAST_RESOLVED IS NULL AND LAST_RESTORED IS NOT NULL)
                          THEN TO_TIMESTAMP(SUBSTR(LAST_RESTORED,1,18), 'DD-MON-RR HH24.MI.SS', 'NLS_DATE_LANGUAGE=ENGLISH')
                        WHEN LAST_RESOLVED IS NOT NULL AND LAST_RESTORED IS NULL
                          THEN TO_TIMESTAMP(SUBSTR(LAST_RESOLVED,1,18), 'DD-MON-RR HH24.MI.SS', 'NLS_DATE_LANGUAGE=ENGLISH')
                        ELSE TO_TIMESTAMP(SUBSTR(CLOSED,1,18), 'DD-MON-RR HH24.MI.SS', 'NLS_DATE_LANGUAGE=ENGLISH')
                    END,'DD-MM-yy hh24:mi:ss') AS "Resolved_Time",
                    T.REGION || ' : ' || ON_OFF_NET AS "Network",
                    CASE
                        WHEN INSTR(UPPER(T.ASSET_DESCRIPTION), UPPER(C.PRODUCT)) > 0 THEN C.PRODUCT
                        ELSE 'NA'
                    END AS "Product",
                    ACCOUNT_NAME as "Acc Name", ACCOUNT_NUMBER as "Acc Num", SERVICE_ID as "Circ",
                    OLO_TIER AS "OLO Tier", RESILIENCE_OPTION AS "Resilience",
                    MRC, U_MRC, CURRENCY,
                    SLA_PERCENTAGE AS "SLA%", U_SLA_PERCENTAGE AS "U_SLA%",
                    SLA_AMNT as "SLA Amnt", U_SLA_AMNT as "U_SLA Amnt",
                    MRC_EUR as "Amnt in Euro",
                    TTTR_MINS AS "Targeted Time To Resolution (Min)",
                    U_TTTR_MINS AS "U_Targeted Time To Resolution (Min)",
                    MTTR_MINS AS "Fault Duration (Min)",
                    U_MTTR_MINS AS "U_Fault Duration (Min)",
                    T.SLA_TARGET AS "COLT SLA Metrics (Min)",
                    T.U_SLA_TARGET AS "U_COLT SLA Metrics (Min)",
                    NVL(CUSTOMER_DELAY_TOTAL_MIN,0) AS "Cust Delay (Min)",
                    NVL(U_CUSTOMER_DELAY_TOTAL_MIN,0) AS "U_Cust Delay (Min)",
                    REMARKS,
                    row_number() over (partition by SR_NUM, INCIDENT_ID order by length(C.Product) desc) rnk
                FROM OI_RTQM_L1.ID1558_SLA_COMPENSATION_CALCULATOR T
                LEFT JOIN OI_RTQM.SLA_COMPENSATION_CALCULATOR C ON INSTR(UPPER(T.ASSET_DESCRIPTION), UPPER(C.PRODUCT)) > 0
                WHERE to_char(cast(RECALCULATED_TIME as date),'YYYY-MM-DD') >='"""
            + frm_dt
            + """'
                  AND to_char(cast(RECALCULATED_TIME as date),'YYYY-MM-DD') <='"""
            + to_dt
            + """'
                  AND T.INCIDENT_ID not in ('New Record_Done', 'New Record')
            ) where rnk = 1
            order by 2"""
        )
    except Exception:
        return pd.DataFrame()


def create_pdf(record):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    if os.path.exists(png_path):
        c.drawImage(
            png_path,
            x=50,
            y=height - 120,
            width=120,
            height=60,
            preserveAspectRatio=True,
            mask="auto",
        )

    y = height - 150
    c.setFont("Helvetica", 11)
    heading_x = 50
    value_x = 250

    for col, val in record.items():
        c.drawString(heading_x, y, f"{col}:")
        c.drawString(value_x, y, str(val))
        y -= 20

    c.save()
    buffer.seek(0)
    return buffer


def read_data(form_data):
    row_ids = form_data.getlist("row_id")
    if not row_ids:
        row_ids = sorted(
            {m.group(1) for k in form_data.keys() for m in [re.match(r"^.+_(\\d+)$", k)] if m},
            key=lambda x: int(x),
        )

    selected_rows = set(form_data.getlist("selected_rows"))
    has_multi_select = form_data.get("has_multi_select") == "Y"

    rows = []
    for row_id in row_ids:
        row_data = {}
        for col in COLUMNS:
            value = form_data.get(f"{col}_{row_id}", "")
            if col in EDITABLE_COLS and (value is None or str(value).strip() == ""):
                value = form_data.get(f"orig_{col}_{row_id}", "")

            if col in EDITABLE_DATETIME_COLS:
                value = to_db_datetime(value)
            elif col in EDITABLE_NUMBER_COLS:
                value = to_input_number(value)

            row_data[col] = value
        row_data["row_id"] = row_id
        rows.append(row_data)

    rows_to_update = [r for r in rows if r["row_id"] in selected_rows] if has_multi_select else rows

    if not rows_to_update:
        return pd.DataFrame(columns=COLUMNS), "", [], [], [], []

    df = pd.DataFrame(rows_to_update).fillna("")
    all_inc = df["SR"].astype(str).tolist()

    for _, row in df.iterrows():
        update_sql(
            f"""
            UPDATE OI_RTQM_L1.ID1558_SLA_COMPENSATION_CALCULATOR
               SET
                U_MRC = '{esc_sql(row['MRC']).replace('None', '')}',
                U_CURRENCY = '{esc_sql(row['CURRENCY']).replace('None', '')}',
                U_SLA_PERCENTAGE = '{esc_sql(row['SLA%']).replace('None', '')}',
                U_SLA_AMNT = '{esc_sql(row['SLA Amnt']).replace('None', '')}',
                U_SLA_AMNT_EUR = '{esc_sql(row['Amnt in Euro']).replace('None', '')}',
                U_TTTR_MINS = '{esc_sql(row['Targeted Time To Resolution (Min)']).replace('None', '')}',
                U_MTTR_MINS = '{esc_sql(row['Fault Duration (Min)']).replace('None', '')}',
                U_SLA_TARGET = '{esc_sql(row['COLT SLA Metrics (Min)']).replace('None', '')}',
                U_CUSTOMER_DELAY_TOTAL_MIN = '{esc_sql(row['Cust Delay (Min)']).replace('None', '')}',
                U_RESOLVED_TIME = '{esc_sql(row['Resolved_Time']).replace('None', '')}',
                REMARKS = '{esc_sql(row['REMARKS']).replace('None', '')}',
                RECALCULATE = 'Y',
                RECALCULATED_TIME = systimestamp,
                UPDATED_BY = '{esc_sql(session.get('user', ''))}'
             WHERE INCIDENT_ID = '{esc_sql(row['INC Number'])}'
            """
        )

    update_sql("EXECUTE OI_RTQM_L1.ID1558_SLA_COMPENSATION_CALCULATOR_PROC")

    all_inc_sql = "'" + "','".join([esc_sql(x) for x in all_inc]) + "'"
    select_df = ensure_dataframe(u_query_search(all_inc_sql))
    records_re = select_df.to_dict(orient="records")
    columns_re = select_df.columns.tolist()

    search_df = ensure_dataframe(u_query_search(all_inc_sql))
    records_se = search_df.to_dict(orient="records")
    columns_se = search_df.columns.tolist()

    return search_df, all_inc_sql, records_re, columns_re, records_se, columns_se


@app.route("/")
def index():
    if "user" not in session:
        return redirect(url_for("login"))
    return redirect(url_for("base_form"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user_name = request.form.get("username", "").strip().lower()
        pwd = request.form.get("password", "")
        if validate_user(user_name, pwd):
            session["user"] = user_name
            return redirect(url_for("base_form"))
        flash("Invalid Username/Password")
    return render_template("ID1558_SLA_login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/base_form")
def base_form():
    if "user" not in session:
        return redirect(url_for("login"))
    return render_template("base.html")


@app.route("/search", methods=["POST"])
def search():
    sr_num = build_in_clause(request.form.get("name", ""))
    inc_num = build_in_clause(request.form.get("inc_name", ""))
    session["user_value"] = sr_num
    session["user_value_inc"] = inc_num

    chk_u_red = request.form.get("chk_u_red")
    if chk_u_red == "Y":
        search_df = ensure_dataframe(query_search_up(sr_num, inc_num))
    else:
        search_df = ensure_dataframe(query_search(sr_num, inc_num))

    if search_df.empty:
        update_sql(
            f"""INSERT INTO OI_RTQM_L1.ID1558_SLA_COMPENSATION_CALCULATOR (SR_NUM, INCIDENT_ID)
                 VALUES({sr_num}, 'New Record')"""
        )
        update_sql("EXECUTE OI_RTQM_L1.ID1558_SLA_COMPENSATION_CALCULATOR_PROC")
        search_df = ensure_dataframe(query_search(sr_num, inc_num))

    records = normalize_records_for_inputs(search_df.to_dict(orient="records"))
    columns = search_df.columns.tolist()
    return render_template("input_value.html", form="search", records=records, columns=columns, sr_num=sr_num)


@app.route("/recalculate", methods=["POST"])
def recalculate():
    search_df, all_inc, records_re, columns_re, records_se, columns_se = read_data(request.form)
    records_se = normalize_records_for_inputs(records_se)
    return render_template(
        "input_value.html",
        all_inc=str(all_inc),
        form="search",
        form1="show",
        records=records_se,
        columns=columns_se,
        records1=records_re,
        columns1=columns_re,
    )


@app.route("/report", methods=["GET", "POST"])
def report():
    return render_template("ID1558_SLA.html")


@app.route("/generate_report", methods=["GET", "POST"])
def generate_report():
    try:
        frm_dt = request.form.get("start_date", "")
        to_dt = request.form.get("end_date", "")
        df = ensure_dataframe(report_query(frm_dt, to_dt))
        file_path = os.path.join(os.path.expanduser("~"), "Downloads", "SLA_Report.xlsx")
        df.to_excel(file_path, index=False)
        return send_file(file_path, as_attachment=True)
    except Exception as e:
        return f"Error generating report: {str(e)}"


@app.route("/download_pdf")
def download_pdf():
    saved_value = session.get("user_value", "''")
    if len(str(saved_value)) <= 6:
        saved_value = session.get("user_value_inc", "''")

    pdf_df = update_sql(
        """SELECT DISTINCT
             INCIDENT_ID AS "Incident Ticket"
            ,SR_NUM AS "SLA compensation Request"
            ,SERVICE_ID as "Circuit Reference"
            ,U_SLA_TARGET as "SLA Minutes"
            ,to_char(TO_TIMESTAMP(created, 'DD-MON-RR HH24.MI.SS.FF6', 'NLS_DATE_LANGUAGE=ENGLISH'),'DD-MM-yy hh24:mi:ss') || ' GMT' as "Ticket Created Date"
            ,U_MTTR_MINS as "Colt Ticket Duration (min)"
            ,U_TTTR_MINS as "SLA Minutes Breach Time"
            ,SUBSTR(ORDER_NUMBER, 1, INSTR(ORDER_NUMBER, '/') - 1) as "Order Number"
            ,ACCOUNT_NAME as "Customer Name"
            ,U_MRC || ' ' || NVL(U_CURRENCY,currency) as "Charge"
            ,U_SLA_PERCENTAGE as "Penalty % entitled"
            ,NVL(REPLACE(TRIM(U_SLA_AMNT),NVL(U_CURRENCY,currency),''),'0') || ' ' || currency as "Penalty to be paid"
            ,'Approved' as "Status"
        FROM OI_RTQM_L1.ID1558_SLA_COMPENSATION_CALCULATOR T
        WHERE (INCIDENT_ID in ("""
        + saved_value
        + """) or SR_NUM in ("""
        + saved_value
        + """))
              AND T.INCIDENT_ID not in ('New Record_Done', 'New Record')
        order by INCIDENT_ID"""
    )
    pdf_df = ensure_dataframe(pdf_df)

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zipf:
        for i in range(len(pdf_df)):
            record = pdf_df.iloc[i].to_dict()
            inc_num = pdf_df.iloc[i, 0]
            pdf_buffer = create_pdf(record)
            pdf_buffer.seek(0)
            zipf.writestr(f"Inc_{inc_num}.pdf", pdf_buffer.read())

    zip_buffer.seek(0)
    return send_file(
        zip_buffer,
        as_attachment=True,
        download_name="SR" + str(saved_value).replace("'", "_") + ".zip",
        mimetype="application/zip",
    )


if __name__ == "__main__":
    app.run(debug=True, port=5007)



