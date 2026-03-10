import io
import os
import zipfile
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from flask import Flask, request, session, render_template, redirect, url_for, send_file, flash
import pandas as pd

from oracle_insights import update_sql
from ID1558_SLA_auth_db import validate_user

png_path = "E:\\Python\\scripts\\templates\\SLA_logo.png"

app = Flask(__name__)
app.secret_key = 'a_really_long_and_unique_secret_key_for_session_data'

def query_search(sr_num,inc_num):
    try:
        df = update_sql("""select "SR","INC Number", "Created"
                ,"Resolved_Time","Updated_Resolved_Time","Network","Product","Acc Name" ,"Acc Num", "Circ",
                "OLO Tier", "Resilience" , MRC, CURRENCY,"SLA%","SLA Amnt",
                "Amnt in Euro", "Targeted Time To Resolution (Min)" , "Fault Duration (Min)" , "COLT SLA Metrics (Min)",
                "Cust Delay (Min)" ,REMARKS
                            from (
                SELECT  DISTINCT
            SR_NUM AS "SR",
            INCIDENT_ID AS "INC Number"
            ,to_char(TO_TIMESTAMP(SUBSTR(created,1,18), 'DD-MON-RR HH24.MI.SS', 'NLS_DATE_LANGUAGE=ENGLISH'),'DD-MM-yy hh24:mi:ss') as "Created"
            ,to_char(CASE
                   WHEN (LAST_RESTORED IS NOT NULL AND LAST_RESOLVED IS NOT NULL )
                            OR  (LAST_RESOLVED IS NULL AND LAST_RESTORED IS NOT NULL)
                                THEN TO_TIMESTAMP(SUBSTR(LAST_RESTORED,1,18), 'DD-MON-RR HH24.MI.SS', 'NLS_DATE_LANGUAGE=ENGLISH')
                    WHEN LAST_RESOLVED IS NOT NULL AND LAST_RESTORED IS  NULL 
                                THEN TO_TIMESTAMP(SUBSTR(LAST_RESOLVED,1,18), 'DD-MON-RR HH24.MI.SS', 'NLS_DATE_LANGUAGE=ENGLISH')
                   ELSE
                          TO_TIMESTAMP(SUBSTR(CLOSED,1,18), 'DD-MON-RR HH24.MI.SS', 'NLS_DATE_LANGUAGE=ENGLISH')
                   END,'DD-MM-yy hh24:mi:ss') AS "Resolved_Time"
                   ,TO_CHAR(
    CASE
        WHEN (LAST_RESTORED IS NOT NULL AND LAST_RESOLVED IS NOT NULL)
             OR (LAST_RESOLVED IS NULL AND LAST_RESTORED IS NOT NULL)
        THEN TO_TIMESTAMP(SUBSTR(LAST_RESTORED,1,18), 'DD-MON-RR HH24.MI.SS', 'NLS_DATE_LANGUAGE=ENGLISH')
        WHEN LAST_RESOLVED IS NOT NULL AND LAST_RESTORED IS NULL
        THEN TO_TIMESTAMP(SUBSTR(LAST_RESOLVED,1,18), 'DD-MON-RR HH24.MI.SS', 'NLS_DATE_LANGUAGE=ENGLISH')
        ELSE TO_TIMESTAMP(SUBSTR(CLOSED,1,18), 'DD-MON-RR HH24.MI.SS', 'NLS_DATE_LANGUAGE=ENGLISH')
    END,
    'YYYY-MM-DD"T"HH24:MI'
) AS "Updated_Resolved_Time"
            ,T.REGION || ' : ' ||ON_OFF_NET AS "Network",
            CASE 
                WHEN INSTR(UPPER(T.ASSET_DESCRIPTION), UPPER(C.PRODUCT)) > 0 THEN C.PRODUCT
                ELSE 'NA' 
            END AS "Product",
            ACCOUNT_NAME as "Acc Name" ,ACCOUNT_NUMBER as  "Acc Num", SERVICE_ID as "Circ",
            OLO_TIER AS "OLO Tier",
            RESILIENCE_OPTION AS "Resilience" ,
            MRC, CURRENCY,
            SLA_PERCENTAGE AS "SLA%",
             SLA_AMNT as "SLA Amnt",
            MRC_EUR  as "Amnt in Euro",
            TTTR_MINS AS "Targeted Time To Resolution (Min)" -- SLA Missed By (Min)	
            ,MTTR_MINS AS "Fault Duration (Min)" ---MTTR (Min)
              ,T.SLA_TARGET AS "COLT SLA Metrics (Min)",
            NVL(CUSTOMER_DELAY_TOTAL_MIN,0) AS "Cust Delay (Min)"
            ,REMARKS
            ,row_number() over (partition by SR_NUM,INCIDENT_ID order by length(C.Product) desc) rnk
            ,APPROVED_STATUS as "Approval"
              FROM OI_RTQM_L1.ID1558_SLA_COMPENSATION_CALCULATOR T 
              LEFT JOIN  OI_RTQM.SLA_COMPENSATION_CALCULATOR C ON INSTR(UPPER(T.ASSET_DESCRIPTION), UPPER(C.PRODUCT)) > 0
              WHERE (INCIDENT_ID in (""" + inc_num + """)  or  SR_NUM in (""" + sr_num + """) )
              AND T.INCIDENT_ID not in ('New Record_Done', 'New Record')
              ) where rnk = 1
              order by 2""")

        return df
    except Exception as e:
        return str(e)

def query_search_up(sr_num,inc_num):
    try:
        df = update_sql("""select "SR","INC Number", "Created"
                ,"Resolved_Time","Updated_Resolved_Time","Network","Product","Acc Name" ,"Acc Num", "Circ",
                "OLO Tier", "Resilience" , MRC, CURRENCY,"SLA%","SLA Amnt",
                "Amnt in Euro", "Targeted Time To Resolution (Min)" , "Fault Duration (Min)" , "COLT SLA Metrics (Min)",
                "Cust Delay (Min)" ,REMARKS
                            from (
                SELECT  DISTINCT
            SR_NUM AS "SR",
            INCIDENT_ID AS "INC Number"
            ,to_char(TO_TIMESTAMP(SUBSTR(created,1,18), 'DD-MON-RR HH24.MI.SS', 'NLS_DATE_LANGUAGE=ENGLISH'),'DD-MM-yy hh24:mi:ss') as "Created"
            ,NVL(U_Resolved_Time ,to_char(CASE
                    WHEN (LAST_RESTORED IS NOT NULL AND LAST_RESOLVED IS NOT NULL )
                             OR  (LAST_RESOLVED IS NULL AND LAST_RESTORED IS NOT NULL)
                                 THEN TO_TIMESTAMP(SUBSTR(LAST_RESTORED,1,18), 'DD-MON-RR HH24.MI.SS', 'NLS_DATE_LANGUAGE=ENGLISH')
                     WHEN LAST_RESOLVED IS NOT NULL AND LAST_RESTORED IS  NULL 
                                 THEN TO_TIMESTAMP(SUBSTR(LAST_RESOLVED,1,18), 'DD-MON-RR HH24.MI.SS', 'NLS_DATE_LANGUAGE=ENGLISH')
                     ELSE
                           TO_TIMESTAMP(SUBSTR(CLOSED,1,18), 'DD-MON-RR HH24.MI.SS', 'NLS_DATE_LANGUAGE=ENGLISH')
                     END,'DD-MM-yy hh24:mi:ss') )
                     AS "Resolved_Time"
                     ,TO_CHAR(
    CASE
        WHEN (LAST_RESTORED IS NOT NULL AND LAST_RESOLVED IS NOT NULL)
             OR (LAST_RESOLVED IS NULL AND LAST_RESTORED IS NOT NULL)
        THEN TO_TIMESTAMP(SUBSTR(LAST_RESTORED,1,18), 'DD-MON-RR HH24.MI.SS', 'NLS_DATE_LANGUAGE=ENGLISH')
        WHEN LAST_RESOLVED IS NOT NULL AND LAST_RESTORED IS NULL
        THEN TO_TIMESTAMP(SUBSTR(LAST_RESOLVED,1,18), 'DD-MON-RR HH24.MI.SS', 'NLS_DATE_LANGUAGE=ENGLISH')
        ELSE TO_TIMESTAMP(SUBSTR(CLOSED,1,18), 'DD-MON-RR HH24.MI.SS', 'NLS_DATE_LANGUAGE=ENGLISH')
    END,
    'YYYY-MM-DD"T"HH24:MI'
) AS "Updated_Resolved_Time"
            ,T.REGION || ' : ' ||ON_OFF_NET AS "Network",
            CASE 
                WHEN INSTR(UPPER(T.ASSET_DESCRIPTION), UPPER(C.PRODUCT)) > 0 THEN C.PRODUCT
                ELSE 'NA' 
            END AS "Product",
            ACCOUNT_NAME as "Acc Name" ,ACCOUNT_NUMBER as  "Acc Num", SERVICE_ID as "Circ",
            OLO_TIER AS "OLO Tier",
            RESILIENCE_OPTION AS "Resilience" ,
            U_MRC as MRC, NVL(U_CURRENCY,CURRENCY) AS CURRENCY,
            U_SLA_PERCENTAGE AS "SLA%",
            U_SLA_AMNT as "SLA Amnt"    ,   
            U_SLA_AMNT_EUR  as "Amnt in Euro",
            U_TTTR_MINS AS "Targeted Time To Resolution (Min)" -- SLA Missed By (Min)
            ,U_MTTR_MINS AS "Fault Duration (Min)" ---MTTR (Min)
              ,T.U_SLA_TARGET AS "COLT SLA Metrics (Min)",
            NVL(U_CUSTOMER_DELAY_TOTAL_MIN,0) AS "Cust Delay (Min)"
            ,REMARKS
            ,row_number() over (partition by SR_NUM,INCIDENT_ID order by length(C.Product) desc) rnk
            ,APPROVED_STATUS as "Approval"
              FROM OI_RTQM_L1.ID1558_SLA_COMPENSATION_CALCULATOR T 
              LEFT JOIN  OI_RTQM.SLA_COMPENSATION_CALCULATOR C ON INSTR(UPPER(T.ASSET_DESCRIPTION), UPPER(C.PRODUCT)) > 0
              WHERE (INCIDENT_ID in (""" + inc_num + """)  or  SR_NUM in (""" + sr_num + """) )
              AND T.INCIDENT_ID not in ('New Record_Done', 'New Record')
              ) where rnk = 1
              order by 2""")

        return df
    except Exception as e:
        return str(e)

def u_query_search(all_inc):
    try:
        df = update_sql("""select "SR","INC Number", "Created"
                ,"Resolved_Time","Network","Product","Acc Name" ,"Acc Num", "Circ",
                "OLO Tier", "Resilience" , MRC, CURRENCY,"SLA%","SLA Amnt",
                "Amnt in Euro", "Targeted Time To Resolution (Min)" , "Fault Duration (Min)" , "COLT SLA Metrics (Min)",
                "Cust Delay (Min)" ,REMARKS
                            from (
                SELECT  DISTINCT
            SR_NUM AS "SR",
            INCIDENT_ID AS "INC Number"
            ,to_char(TO_TIMESTAMP(SUBSTR(created,1,18), 'DD-MON-RR HH24.MI.SS', 'NLS_DATE_LANGUAGE=ENGLISH'),'DD-MM-yy hh24:mi:ss') as "Created"
         ,NVL(U_Resolved_Time ,to_char(CASE
                    WHEN (LAST_RESTORED IS NOT NULL AND LAST_RESOLVED IS NOT NULL )
                             OR  (LAST_RESOLVED IS NULL AND LAST_RESTORED IS NOT NULL)
                                 THEN TO_TIMESTAMP(SUBSTR(LAST_RESTORED,1,18), 'DD-MON-RR HH24.MI.SS', 'NLS_DATE_LANGUAGE=ENGLISH')
                     WHEN LAST_RESOLVED IS NOT NULL AND LAST_RESTORED IS  NULL 
                                 THEN TO_TIMESTAMP(SUBSTR(LAST_RESOLVED,1,18), 'DD-MON-RR HH24.MI.SS', 'NLS_DATE_LANGUAGE=ENGLISH')
                     ELSE
                           TO_TIMESTAMP(SUBSTR(CLOSED,1,18), 'DD-MON-RR HH24.MI.SS', 'NLS_DATE_LANGUAGE=ENGLISH')
                     END,'DD-MM-yy hh24:mi:ss') )
                     AS "Resolved_Time"
            ,T.REGION || ' : ' ||ON_OFF_NET AS "Network",
            CASE 
                WHEN INSTR(UPPER(T.ASSET_DESCRIPTION), UPPER(C.PRODUCT)) > 0 THEN C.PRODUCT
                ELSE 'NA' 
            END AS "Product",
            ACCOUNT_NAME as "Acc Name" ,ACCOUNT_NUMBER as  "Acc Num", SERVICE_ID as "Circ",
            OLO_TIER AS "OLO Tier",
            RESILIENCE_OPTION AS "Resilience" ,
            U_MRC as MRC, NVL(U_CURRENCY,CURRENCY) AS CURRENCY,
            U_SLA_PERCENTAGE AS "SLA%",
            U_SLA_AMNT as "SLA Amnt"    ,   
            U_SLA_AMNT_EUR  as "Amnt in Euro",
            U_TTTR_MINS AS "Targeted Time To Resolution (Min)" -- SLA Missed By (Min)
            ,U_MTTR_MINS AS "Fault Duration (Min)" ---MTTR (Min)
              ,T.U_SLA_TARGET AS "COLT SLA Metrics (Min)",
            NVL(U_CUSTOMER_DELAY_TOTAL_MIN,0) AS "Cust Delay (Min)"
            ,REMARKS
            ,row_number() over (partition by SR_NUM,INCIDENT_ID order by length(C.Product) desc) rnk
            ,APPROVED_STATUS as "Approval"
              FROM OI_RTQM_L1.ID1558_SLA_COMPENSATION_CALCULATOR T 
              LEFT JOIN  OI_RTQM.SLA_COMPENSATION_CALCULATOR C ON INSTR(UPPER(T.ASSET_DESCRIPTION), UPPER(C.PRODUCT)) > 0
              WHERE SR_NUM IN ("""+ all_inc +""") 
          AND T.INCIDENT_ID not in ('New Record_Done', 'New Record')
              ) where rnk = 1
              order by 2""")

        return df
    except Exception as e:
        return str(e)

def report_query(frm_dt,to_dt):
    try:
        df = update_sql("""select UPDATED_BY, "SR","INC Number", "Created" ,RECALCULATED_TIME
        ,"Resolved_Time","Network","Product","Acc Name" ,"Acc Num", "Circ",
        "OLO Tier", "Resilience" , CURRENCY, 
        MRC, "SLA%", "SLA Amnt",  "Amnt in Euro", "Targeted Time To Resolution (Min)"   , "Fault Duration (Min)" ,
         "COLT SLA Metrics (Min)"  ,  "Cust Delay (Min)",                
        U_MRC ,"U_SLA%","U_SLA Amnt"  ,"U_Targeted Time To Resolution (Min)", "U_Fault Duration (Min)" ,
        "U_COLT SLA Metrics (Min)",  "U_Cust Delay (Min)" ,REMARKS
from (
                SELECT  DISTINCT UPDATED_BY, 
            SR_NUM AS "SR", RECALCULATED_TIME,
            INCIDENT_ID AS "INC Number"
            ,to_char(TO_TIMESTAMP(SUBSTR(created,1,18), 'DD-MON-RR HH24.MI.SS', 'NLS_DATE_LANGUAGE=ENGLISH'),'DD-MM-yy hh24:mi:ss') as "Created"
            ,to_char(CASE
                   WHEN (LAST_RESTORED IS NOT NULL AND LAST_RESOLVED IS NOT NULL )
                            OR  (LAST_RESOLVED IS NULL AND LAST_RESTORED IS NOT NULL)
                                THEN TO_TIMESTAMP(SUBSTR(LAST_RESTORED,1,18), 'DD-MON-RR HH24.MI.SS', 'NLS_DATE_LANGUAGE=ENGLISH')
                    WHEN LAST_RESOLVED IS NOT NULL AND LAST_RESTORED IS  NULL 
                                THEN TO_TIMESTAMP(SUBSTR(LAST_RESOLVED,1,18), 'DD-MON-RR HH24.MI.SS', 'NLS_DATE_LANGUAGE=ENGLISH')
                   ELSE
                          TO_TIMESTAMP(SUBSTR(CLOSED,1,18), 'DD-MON-RR HH24.MI.SS', 'NLS_DATE_LANGUAGE=ENGLISH')
                   END,'DD-MM-yy hh24:mi:ss') AS "Resolved_Time"
            ,T.REGION || ' : ' ||ON_OFF_NET AS "Network",
            CASE 
                WHEN INSTR(UPPER(T.ASSET_DESCRIPTION), UPPER(C.PRODUCT)) > 0 THEN C.PRODUCT
                ELSE 'NA' 
            END AS "Product",
            ACCOUNT_NAME as "Acc Name" ,ACCOUNT_NUMBER as  "Acc Num", SERVICE_ID as "Circ",
            OLO_TIER AS "OLO Tier",
            RESILIENCE_OPTION AS "Resilience" ,
            
            MRC, U_MRC , CURRENCY,
            SLA_PERCENTAGE AS "SLA%", U_SLA_PERCENTAGE AS "U_SLA%",
             SLA_AMNT as "SLA Amnt",   U_SLA_AMNT as "U_SLA Amnt"    ,   
            MRC_EUR  as "Amnt in Euro",
            TTTR_MINS AS "Targeted Time To Resolution (Min)" -- SLA Missed By (Min)	
           , U_TTTR_MINS AS "U_Targeted Time To Resolution (Min)" -- SLA Missed By (Min)
            ,MTTR_MINS AS "Fault Duration (Min)" ---MTTR (Min)
            ,U_MTTR_MINS AS "U_Fault Duration (Min)" ---MTTR (Min)
              ,T.SLA_TARGET AS "COLT SLA Metrics (Min)"
                ,T.U_SLA_TARGET AS "U_COLT SLA Metrics (Min)",
            NVL(CUSTOMER_DELAY_TOTAL_MIN,0) AS "Cust Delay (Min)",
            NVL(U_CUSTOMER_DELAY_TOTAL_MIN,0) AS "U_Cust Delay (Min)"
            ,REMARKS
            ,row_number() over (partition by SR_NUM,INCIDENT_ID order by length(C.Product) desc) rnk
            ,APPROVED_STATUS as "Approval"
            FROM OI_RTQM_L1.ID1558_SLA_COMPENSATION_CALCULATOR T 
              LEFT JOIN  OI_RTQM.SLA_COMPENSATION_CALCULATOR C ON INSTR(UPPER(T.ASSET_DESCRIPTION), UPPER(C.PRODUCT)) > 0
              WHERE to_char(cast(RECALCULATED_TIME as date),'YYYY-MM-DD') >='"""+frm_dt+"""'
               AND  to_char(cast(RECALCULATED_TIME as date),'YYYY-MM-DD') <='"""+to_dt+"""'
                            AND T.INCIDENT_ID not in ('New Record_Done', 'New Record')
              ) where rnk = 1
              order by 2""")
        return df
    except Exception as e:
        return str(e)


@app.route("/download", methods=["GET", "POST"])
def download_pdf():
    saved_value = session.get("user_value")
    # print(saved_value)
    if len(str(saved_value)) <= 6 :
        saved_value = session["user_value_inc"]
        # print(saved_value)
    pdf_df = update_sql("""SELECT DISTINCT
             INCIDENT_ID AS "Incident Ticket"
            ,SR_NUM AS "SLA compensation Request"
            ,SERVICE_ID as "Circuit Reference"
            ,U_SLA_TARGET as "SLA Minutes"
            ,to_char(TO_TIMESTAMP(created, 'DD-MON-RR HH24.MI.SS.FF6', 'NLS_DATE_LANGUAGE=ENGLISH'),'DD-MM-yy hh24:mi:ss') || ' GMT' as "Ticket Created Date"
            ,U_MTTR_MINS as "Colt Ticket Duration (min)"
            ,U_TTTR_MINS as "SLA Minutes Breach Time"
            ,SUBSTR(ORDER_NUMBER, 1, INSTR(ORDER_NUMBER, '/') - 1) as "Order Number"
            ,ACCOUNT_NAME as "Customer Name"
            ,U_MRC || ' ' || NVL(U_CURRENCY,currency) as  "Charge"
            ,U_SLA_PERCENTAGE as "Penalty % entitled"
            ,NVL(REPLACE(TRIM(U_SLA_AMNT),NVL(U_CURRENCY,currency),''),'0') || ' ' || currency  as "Penalty to be paid"
            ,'Approved' as "Status"
            FROM OI_RTQM_L1.ID1558_SLA_COMPENSATION_CALCULATOR T 
            WHERE (INCIDENT_ID in (""" + saved_value + """)  or  SR_NUM in (""" + saved_value + """) )
            AND T.INCIDENT_ID not in ('New Record_Done', 'New Record') 
            order by INCIDENT_ID
            """)
    # print(pdf_df)
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
        download_name="SR"+saved_value.replace("'","_")+".zip",
        mimetype="application/zip"
    )

def create_pdf(record):
    """Generate a single PDF for one record with aligned headings and values."""
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    # Title
    if os.path.exists(png_path):
        c.drawImage(png_path, x=50, y=height - 120, width=120, height=60,
                    preserveAspectRatio=True, mask='auto')

    # Start position
    y = height - 150
    c.setFont("Helvetica", 11)

    # Fixed spacing for alignment
    heading_x = 50
    value_x = 250   # adjust this for spacing between heading and value

    for col, val in record.items():
        c.drawString(heading_x, y, f"{col}:")
        c.drawString(value_x, y, str(val))
        y -= 20

    c.save()
    buffer.seek(0)
    return buffer

@app.route("/report", methods=["GET", "POST"])
def report():
    """Display report generation form."""
    return render_template("ID1558_SLA.HTML")


@app.route("/generate_report", methods=["GET", "POST"])
def generate_report():
    """Generate and download Excel report."""
    frm_dt = request.form.get('start_date')
    to_dt = request.form.get('end_date')
    df = report_query(frm_dt, to_dt)
    
    file_path = os.path.join(os.path.expanduser("~"), "Downloads", "SLA_Report.xlsx")
    df.to_excel(file_path, index=False)

    return send_file(file_path, as_attachment=True)


@app.route("/search", methods=["GET", "POST"])
def search_form():
    sr_num = request.form.get('name')
    sr_num = "'" + (sr_num).replace(',',"','").replace(' ','')+"'"
    session["user_value"] = sr_num
    # print('popo' + sr_num)
    inc_num = request.form.get('inc_name')
    inc_num = "'" + (inc_num).replace(',', "','") + "'"
    session["user_value_inc"] = inc_num
    chk_u_red = request.form.get('chk_u_red')
    form = 'search'
    if chk_u_red  == 'Y':
        search_df = query_search_up(sr_num,inc_num)
    else:
        search_df = query_search(sr_num,inc_num)
    if search_df.empty:
        update_sql("""INSERT INTO  OI_RTQM_L1.ID1558_SLA_COMPENSATION_CALCULATOR (SR_NUM,INCIDENT_ID)
                 VALUES("""+ sr_num +""" ,'New Record')""")
        update_sql("execute OI_RTQM_L1.ID1558_SLA_COMPENSATION_CALCULATOR_PROC")
        search_df = query_search(sr_num,inc_num)
    records = search_df.to_dict(orient="records")
    columns = search_df.columns.tolist()
    return render_template("input_value.html", form = form, sr_num= sr_num, records=records, columns=columns)


@app.route("/")
def index():
    """Redirect to login if user not in session."""
    if "user" not in session:
        return redirect(url_for("login"))
    return redirect(url_for("base_form"))


@app.route("/login", methods=["GET", "POST"])
def login():
    """Handle user login."""
    if request.method == "POST":
        user_name = request.form.get("username")
        pwd = request.form.get("password")
        user_name = user_name.lower()
        if validate_user(user_name, pwd):
            session["user"] = user_name
            return redirect(url_for("base_form"))
        else:
            flash("Invalid Username/Password")
    return render_template("ID1558_SLA_login.html")


@app.route("/logout")
def logout():
    """Clear session and redirect to login."""
    session.clear()
    response = redirect(url_for("login"))
    response.set_cookie("session", "", expires=0)
    return response



@app.route("/base_form", methods=["GET", "POST"])
def base_form():
    """Render the base form for SLA calculations."""
    return render_template("base.html", records='', columns='')


def read_data(form_data):
    COLUMNS = ["SR", "INC Number", "Created","Resolved_Time","Updated_Resolved_Time","Network",  "Product", "Acc Name", "Acc Num" , "Circ" ,"OLO Tier",
               "Resilience","MRC", "CURRENCY","SLA%", "SLA Amnt", "Amnt in Euro", "Targeted Time To Resolution (Min)",
               "Fault Duration (Min)","COLT SLA Metrics (Min)","Cust Delay (Min)", "REMARKS"]
    # Collect all values for each column
    col_values = {col: form_data.getlist(f"{col}_{i}") for i, col in enumerate(COLUMNS)}
    # Number of rows
    n_rows = max(len(v) for v in col_values.values())
    # Step 3: Pad shorter lists (if any) with empty string
    for col in COLUMNS:
        values = col_values[col]
        if len(values) < n_rows:
            values.extend([""] * (n_rows - len(values)))
        col_values[col] = values
# Step 4: Build DataFrame
    df = pd.DataFrame({col: col_values[col] for col in COLUMNS})
    df = df.fillna('')
    # print(df)
    all_inc=[]
    for inc in df["INC Number"]:
        row = df[df["INC Number"] == inc].iloc[0]
        all_inc.append(row['SR'])

        update_sql("""
            UPDATE OI_RTQM_L1.ID1558_SLA_COMPENSATION_CALCULATOR
               SET
                U_MRC = '"""+row['MRC'].replace('None','')+"""',
                 CURRENCY = '"""+row['CURRENCY'].replace('None','')+"""',
                 U_SLA_PERCENTAGE = '"""+row['SLA%'].replace('None','')+"""',
                  U_SLA_AMNT = '"""+row['SLA Amnt'].replace('None','')+"""',
                    U_SLA_AMNT_EUR = '"""+row['Amnt in Euro'].replace('None','')+"""',
                    U_TTTR_MINS = '"""+row['Targeted Time To Resolution (Min)'].replace('None','')+"""',
                    U_MTTR_MINS = '"""+row['Fault Duration (Min)'].replace('None','')+"""',
                     U_SLA_TARGET = '"""+row['COLT SLA Metrics (Min)'].replace('None','')+"""',
                   U_CUSTOMER_DELAY_TOTAL_MIN = '"""+row['Cust Delay (Min)'].replace('None','') + """',
                   U_RESOLVED_TIME = '"""+row['Resolved_Time'].replace('None','') + """',
                   REMARKS = '"""+row['REMARKS'].replace("'"," ").replace('None','')+"""',
                   RECALCULATE = 'Y',RECALCULATED_TIME = systimestamp,
                   UPDATED_BY = ' """ + session["user"] + """'
             WHERE INCIDENT_ID = '"""+ row['INC Number'] + """'""" )
    update_sql("EXECUTE OI_RTQM_L1.ID1558_SLA_COMPENSATION_CALCULATOR_PROC")
    all_inc = "'" + "','".join(all_inc) + "'"
    # print(all_inc)
    select_df = u_query_search(all_inc)
    records_re = select_df.to_dict(orient="records")
    columns_re = select_df.columns.tolist()
    search_df = u_query_search(all_inc)
    # print(search_df)
    records_se = search_df.to_dict(orient="records")
    columns_se = search_df.columns.tolist()

    return search_df,all_inc,records_re,columns_re,records_se,columns_se



@app.route("/recalculate", methods=["POST"])
def recalculate():
    """Recalculate SLA values and display results."""
    form_data = request.form
    search_df, all_inc, records_re, columns_re, records_se, columns_se = read_data(form_data)
    form = 'search'
    form1 = 'show'
    return render_template(
        "input_value.html",
        all_inc=str(all_inc),
        form=form,
        form1=form1,
        records=records_se,
        columns=columns_se,
        records1=records_re,
        columns1=columns_re
    )


if __name__ == "__main__":
    app.run(debug=True, port=5007)



