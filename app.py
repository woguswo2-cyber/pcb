import io
import json
import re
import urllib.request
import numpy as np
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="PCB Assy 자재 소요량 & 구매금액 트래커",
    page_icon="📊",
    layout="wide",
)

st.title("📊 PCB Assembly 하위 자재 소요량 & 구매금액 트래커")
st.caption(
    "효성전기 양산 모터 PCB Assy 자재 집계 | 사업계획/실시간 환율 연동 및 제조사 표준화 클렌징"
)

# --- 1. 제조사명 정규화 (클렌징 엔진) ---
def normalize_vendor_name(vendor_raw):
    """
    제조사 오탈자, 다국어 문자(움라우트), 법인격 표기(INC, LTD 등)를 단일 대표명으로 통일
    """
    if pd.isna(vendor_raw) or not str(vendor_raw).strip():
        return "-"
    
    name = str(vendor_raw).strip().upper()
    
    # 1) 특수 외래어 알파벳 치환
    accent_map = {
        'Ü': 'U', 'Ö': 'O', 'Ä': 'A', 'É': 'E', 'È': 'E', 'Ê': 'E',
        'Ç': 'C', 'Å': 'A', 'Ø': 'O', 'ß': 'SS'
    }
    for orig, repl in accent_map.items():
        name = name.replace(orig, repl)
        
    # 2) 기호 정제 (마침표, 쉼표, 괄호 등 정리)
    name = re.sub(r'[,()\/]', ' ', name)
    name = re.sub(r'\s+', ' ', name).strip()
    
    # 3) 실무 대표 제조사 Alias 사전
    alias_dict = {
        "DIODES": ["DIODES", "DIODES INC", "DIODES INC.", "DIODES INCORPORATED"],
        "STMICROELECTRONICS": ["ST", "STM", "ST MICRO", "ST MICROELECTRONIC", "ST MICROELECTRONICS", "STMICROELECTRONICS", "STMICRO"],
        "ISABELLENHUTTE": ["ISABELLENHUTTE", "ISABELLENHUETTE", "ISA"],
        "INFINEON": ["INFINEON", "INFINEON TECH", "INFINEON TECHNOLOGIES", "IFX"],
        "MURATA": ["MURATA", "MURATA MFG", "MURATA ELECTRONICS"],
        "YAGEO": ["YAGEO", "YAGEO CORP", "YAGEO CORPORATION"],
        "AVX": ["AVX", "AVX CORP", "KYOCERA AVX"],
        "KEMET": ["KEMET", "KEMET ELECTRONICS", "YAGEO KEMET"],
        "TAIYO YUDEN": ["TAIYO", "TAIYO YUDEN", "TAIYOYUDEN"],
        "TDK": ["TDK", "TDK CORP", "TDK CORPORATION"],
        "VISHAY": ["VISHAY", "VISHAY INTERTECHNOLOGY", "VISHAY DALE"],
        "ROHM": ["ROHM", "ROHM SEMICONDUCTOR"],
        "NXP": ["NXP", "NXP SEMICONDUCTORS"],
        "TI": ["TI", "TEXAS INSTRUMENTS", "TEXAS INSTRUMENT"],
        "ON SEMI": ["ON", "ON SEMI", "ONSEMI", "ON SEMICONDUCTOR"],
        "LELON": ["LELON", "LELON ELECTRONICS"],
        "RUBYCON": ["RUBYCON", "RUBYCON CORP"],
        "SAMWHA": ["SAMWHA", "삼화", "삼화전기", "삼화콘덴서"],
        "SAMYOUNG": ["SAMYOUNG", "삼영", "삼영전자"],
        "JND": ["제이앤디", "제이앤디써키트", "JND CIRCUITS", "JND"],
        "KCE": ["KCE", "KCE PCB"],
        "USI": ["USI", "USI PCB"]
    }
    
    # 딕셔너리 완전/포함 일치 매핑
    for master, aliases in alias_dict.items():
        if name in aliases:
            return master
        for a in aliases:
            # 단어 단위 일치 검사
            if re.search(rf'\b{re.escape(a)}\b', name):
                return master

    # 4) 일반 법인격 접미사 제거 (사전에 없는 신규 벤더 대응)
    name = re.sub(r'\b(INC\.?|CORP\.?|CORPORATION|LTD\.?|LIMITED|CO\.?|LLC|GMBH)\b', '', name).strip()
    name = re.sub(r'\s+', ' ', name).strip()
    
    return name if name else "-"

# --- 2. 환율 관리 (사이드바) ---
st.sidebar.header("💱 통화별 환율 설정")

if "fx_rates" not in st.session_state:
    st.session_state.fx_rates = {
        "USD": 1450.0,
        "JPY": 950.0,  # 100엔 기준
        "EUR": 1550.0,
        "CNY": 200.0,
        "KRW": 1.0,
    }


def fetch_realtime_fx():
    """당일 실시간 환율 발췌 (Open Exchange API)"""
    try:
        url = "https://open.er-api.com/v6/latest/USD"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5) as res:
            data = json.loads(res.read().decode())
            rates = data.get("rates", {})
            krw_per_usd = rates.get("KRW", 1450.0)
            jpy_per_usd = rates.get("JPY", 150.0)
            eur_per_usd = rates.get("EUR", 0.92)
            cny_per_usd = rates.get("CNY", 7.2)

            return {
                "USD": round(krw_per_usd, 2),
                "JPY": round((krw_per_usd / jpy_per_usd) * 100, 2),
                "EUR": round(krw_per_usd / eur_per_usd, 2),
                "CNY": round(krw_per_usd / cny_per_usd, 2),
                "KRW": 1.0,
            }
    except Exception as e:
        st.sidebar.error(f"실시간 환율 조회 실패: {e}")
        return None


col_fx_btn1, col_fx_btn2 = st.sidebar.columns(2)
with col_fx_btn1:
    if st.button("🌐 당일 실환율 발췌"):
        real_rates = fetch_realtime_fx()
        if real_rates:
            st.session_state.fx_rates.update(real_rates)
            st.sidebar.success("당일 환율 적용 완료!")
            st.rerun()

with col_fx_btn2:
    if st.button("🔄 기본 사경환율 리셋"):
        st.session_state.fx_rates = {
            "USD": 1450.0,
            "JPY": 950.0,
            "EUR": 1550.0,
            "CNY": 200.0,
            "KRW": 1.0,
        }
        st.rerun()

st.sidebar.caption("※ 매년 사내 사업계획 환율 배포 시 아래 값을 직접 수정하세요.")
usd_rate = st.sidebar.number_input(
    "USD 환율 (원/$)",
    value=float(st.session_state.fx_rates["USD"]),
    step=10.0,
    format="%.2f",
)
jpy_rate = st.sidebar.number_input(
    "JPY 환율 (원/100엔)",
    value=float(st.session_state.fx_rates["JPY"]),
    step=10.0,
    format="%.2f",
)
eur_rate = st.sidebar.number_input(
    "EUR 환율 (원/€)",
    value=float(st.session_state.fx_rates["EUR"]),
    step=10.0,
    format="%.2f",
)
cny_rate = st.sidebar.number_input(
    "CNY 환율 (원/¥)",
    value=float(st.session_state.fx_rates["CNY"]),
    step=5.0,
    format="%.2f",
)

current_fx = {
    "USD": usd_rate,
    "JPY": jpy_rate,
    "EUR": eur_rate,
    "CNY": cny_rate,
    "KRW": 1.0,
}

# --- 3. 기본 생산 계획 템플릿 관리 ---
def init_yearly_plan():
    return pd.DataFrame({
        "ASSY PART NO": ["THS0143301", "E0280014C01"],
        "ASSY PART NAME": ["MX5 CCW", "J9 CW"],
        "2026년": [120000, 150000],
        "2027년": [150000, 180000],
        "2028년": [165000, 190000],
        "2029년": [170000, 200000],
        "2030년": [175000, 210000],
    })

def init_monthly_plan():
    months = [f"{m}월" for m in range(1, 13)]
    init_data = {
        "ASSY PART NO": ["THS0143301", "E0280014C01"],
        "ASSY PART NAME": ["MX5 CCW", "J9 CW"],
    }
    for m in months:
        init_data[m] = [12500, 15000]
    return pd.DataFrame(init_data)

if "manual_yearly_plan" not in st.session_state or "ASSY PART NAME" not in st.session_state.manual_yearly_plan.columns:
    st.session_state.manual_yearly_plan = init_yearly_plan()

if "manual_monthly_plan" not in st.session_state or "ASSY PART NAME" not in st.session_state.manual_monthly_plan.columns:
    st.session_state.manual_monthly_plan = init_monthly_plan()

# --- 4. 영역 1: BOM 입력 ---
st.subheader("1. PCB Assy 하위 BOM 입력")
tab_bom_paste, tab_bom_file = st.tabs(
    ["📋 BOM 텍스트 붙여넣기", "📂 BOM 엑셀 업로드 (.xlsx)"]
)
raw_df_bom = None

with tab_bom_paste:
    sample_text = (
        "PART NO\tPART NAME\tEMS PN\tMPN\tManufacturer\tper unit\t통화\tprice\n"
        "THS0143301\tMX5 CCW\tE6197-701-01\tLeiterplatte BLDC\t제이앤디써키트\t1\tKRW\t1900\n"
        "THS0143301\tMX5 CCW\tE0424-847-00\tAC0402FR-07100KL\tYAGEO\t10\tUSD\t0.00052\n"
        "THS0143301\tMX5 CCW\tF0483-185-00\tIPC100N04S5-2R8\tINFINEON\t7\tUSD\t0.21000\n"
        "E0280014C01\tJ9 CW\tE0424-847-00\tAC0402FR-07100KL\tYageo\t10\tUSD\t0.00052\n"
        "E0280014C01\tJ9 CW\tF0483-185-00\tIPC100N04S5-2R8\tInfineon\t7\tUSD\t0.21000\n"
        "THS0143301\tMX5 CCW\tD0101-001-00\tBAT54WS\tDIODES INC.\t2\tUSD\t0.01500\n"
        "E0280014C01\tJ9 CW\tD0101-001-00\tBAT54WS\tDIODES\t2\tUSD\t0.01500\n"
        "THS0143301\tMX5 CCW\tM0101-002-00\tSTM32F405\tST MICROELECTRONICS\t1\tUSD\t1.50000\n"
        "E0280014C01\tJ9 CW\tM0101-002-00\tSTM32F405\tST MICROELECTRONIC\t1\tUSD\t1.50000\n"
        "THS0143301\tMX5 CCW\tR0101-003-00\tBVS-I-R001\tISABELLENHÜTTE\t1\tEUR\t0.45000\n"
        "E0280014C01\tJ9 CW\tR0101-003-00\tBVS-I-R001\tISABELLENHUTTE\t1\tEUR\t0.45000"
    )
    bom_input_text = st.text_area(
        "엑셀에서 복사한 BOM을 붙여넣으세요 (제목 행 포함 또는 내용만 붙여넣어도 자동 감지)",
        value=sample_text,
        height=180,
    )
    if bom_input_text.strip():
        try:
            raw_df_bom = pd.read_csv(io.StringIO(bom_input_text), sep="\t", header=None, dtype=str)
        except Exception:
            raw_df_bom = pd.read_csv(io.StringIO(bom_input_text), sep=r"\s+", header=None, dtype=str)

with tab_bom_file:
    bom_file = st.file_uploader(
        "BOM 엑셀 파일 (.xlsx)", type=["xlsx"], key="bom_file_up"
    )
    if bom_file:
        try:
            raw_df_bom = pd.read_excel(bom_file, header=None, dtype=str)
        except Exception as e:
            st.error(f"엑셀 로드 실패: {e}")

# --- 5. BOM 스마트 컬럼 감지 & 제조사 표준화 클렌징 적용 ---
df_bom = None
detected_assys = []

if raw_df_bom is not None and not raw_df_bom.empty:
    first_row = [str(x).strip().upper() for x in raw_df_bom.iloc[0].tolist()]
    header_keywords = ["PART NO", "ASSY", "모품번", "EMS PN", "PART NUMBER", "USAGE", "소요량", "PRICE", "단가"]
    is_header_present = any(any(kw in cell for kw in header_keywords) for cell in first_row)

    if is_header_present:
        headers = [str(x).strip() for x in raw_df_bom.iloc[0].tolist()]
        data_df = raw_df_bom.iloc[1:].copy()
        data_df.columns = headers
    else:
        data_df = raw_df_bom.copy()
        default_headers = [
            "ASSY PART NO", "ASSY PART NAME", "EMS PN", "MPN",
            "제조사", "소요량", "통화", "단가", "원화단가"
        ]
        assigned_cols = default_headers[:len(data_df.columns)]
        for i in range(len(assigned_cols), len(data_df.columns)):
            assigned_cols.append(f"기타열_{i+1}")
        data_df.columns = assigned_cols

    df_bom = data_df.copy()
    df_bom.columns = [str(c).strip() for c in df_bom.columns]

    bom_col_map = {
        "PART NO": "ASSY PART NO", "PART_NO": "ASSY PART NO", "ASSY_PN": "ASSY PART NO", "모품번": "ASSY PART NO",
        "PART NAME": "ASSY PART NAME", "PART_NAME": "ASSY PART NAME", "모품명": "ASSY PART NAME",
        "Part Number": "EMS PN", "part number": "EMS PN", "자재번호": "EMS PN", "하위품번": "EMS PN",
        "EMS PN": "EMS PN", "EMS_PN": "EMS PN", "PART NUMBER": "EMS PN",
        "manufacturer part no.": "MPN", "manufacturer part no": "MPN", "제조사 PART NO": "MPN",
        "MPN": "MPN", "규격": "MPN", "제조사 PART NUMBER": "MPN",
        "Manufacturer": "제조사", "MANUFACTURER": "제조사", "제조원": "제조사", "Vendor": "제조사",
        "per unit": "소요량", "per_unit": "소요량", "usage": "소요량", "Usage": "소요량", "소요량": "소요량",
        "price": "단가", "단가": "단가", "단가(외화)": "단가",
        "통화": "통화", "CURRENCY": "통화", "원화": "원화단가", "원화단가": "원화단가"
    }

    for col in list(df_bom.columns):
        for k, v in bom_col_map.items():
            if col.lower() == k.lower():
                df_bom.rename(columns={col: v}, inplace=True)
                break

    if "ASSY PART NO" not in df_bom.columns:
        df_bom["ASSY PART NO"] = df_bom.iloc[:, 0].astype(str)
    if "ASSY PART NAME" not in df_bom.columns:
        if len(df_bom.columns) > 1:
            df_bom["ASSY PART NAME"] = df_bom.iloc[:, 1].astype(str)
        else:
            df_bom["ASSY PART NAME"] = df_bom["ASSY PART NO"]
    if "EMS PN" not in df_bom.columns:
        if len(df_bom.columns) > 2:
            df_bom["EMS PN"] = df_bom.iloc[:, 2].astype(str)
        else:
            df_bom["EMS PN"] = df_bom["ASSY PART NO"]
    if "MPN" not in df_bom.columns:
        if len(df_bom.columns) > 3:
            df_bom["MPN"] = df_bom.iloc[:, 3].astype(str)
        else:
            df_bom["MPN"] = df_bom["EMS PN"]
    if "제조사" not in df_bom.columns:
        df_bom["제조사"] = "-"
    if "소요량" not in df_bom.columns:
        df_bom["소요량"] = 1.0
    if "통화" not in df_bom.columns:
        df_bom["통화"] = "KRW"
    if "단가" not in df_bom.columns:
        df_bom["단가"] = 0.0

    # 🔥 [핵심]: 제조사 정규화 클렌징 엔진 적용
    df_bom["제조사"] = df_bom["제조사"].apply(normalize_vendor_name)

    df_bom["소요량"] = pd.to_numeric(df_bom["소요량"].astype(str).str.replace(",", "").str.strip(), errors="coerce").fillna(1.0)
    df_bom["단가"] = pd.to_numeric(df_bom["단가"].astype(str).str.replace(",", "").str.strip(), errors="coerce").fillna(0.0)
    df_bom["통화"] = df_bom["통화"].astype(str).str.strip().str.upper().fillna("KRW")

    def calc_krw_unit_price(row):
        curr = str(row["통화"]).upper()
        p = float(row["단가"])
        if curr == "USD":
            return p * current_fx["USD"]
        elif curr == "JPY":
            return p * (current_fx["JPY"] / 100.0)
        elif curr == "EUR":
            return p * current_fx["EUR"]
        elif curr == "CNY":
            return p * current_fx["CNY"]
        else:
            return p

    df_bom["원화단가"] = df_bom.apply(calc_krw_unit_price, axis=1)

    detected_assys = (
        df_bom[["ASSY PART NO", "ASSY PART NAME"]]
        .drop_duplicates()
        .to_dict(orient="records")
    )

# --- 6. 영역 2: 생산계획 ---
st.markdown("---")
st.subheader("2. 생산 계획 관리 (품번/품명 분리 및 수기 입력 / 엑셀 업로드)")

plan_input_type = st.radio(
    "생산계획 입력 방식 선택",
    ["✍️ 화면에서 수기 직접 입력 (스프레드시트)", "📂 생산계획 엑셀 파일 업로드"],
    horizontal=True,
)

plan_unpivoted = None

if plan_input_type == "✍️ 화면에서 수기 직접 입력 (스프레드시트)":
    plan_mode = st.radio(
        "계획 주기 구분",
        ["연도별 중장기 (2026~2030+)", "월별 생산 계획 (1월~12월)"],
        horizontal=True,
    )

    if plan_mode == "연도별 중장기 (2026~2030+)":
        curr_df = st.session_state.manual_yearly_plan.copy()
        if "ASSY PART NAME" not in curr_df.columns:
            curr_df.insert(1, "ASSY PART NAME", curr_df["ASSY PART NO"])

        if detected_assys:
            for item in detected_assys:
                a_pn = str(item["ASSY PART NO"])
                a_name = str(item["ASSY PART NAME"])
                if a_pn not in curr_df["ASSY PART NO"].astype(str).values:
                    new_row = {
                        col: 0
                        for col in curr_df.columns
                        if col not in ["ASSY PART NO", "ASSY PART NAME"]
                    }
                    new_row["ASSY PART NO"] = a_pn
                    new_row["ASSY PART NAME"] = a_name
                    curr_df = pd.concat([curr_df, pd.DataFrame([new_row])], ignore_index=True)

        st.caption("💡 수량을 자유롭게 수정한 뒤 아래 [🚀 변경사항 저장 및 연산 반영] 버튼을 누르면 렉 없이 즉시 반영됩니다.")
        with st.form("form_yearly_plan"):
            edited_plan = st.data_editor(
                curr_df,
                num_rows="dynamic",
                use_container_width=True,
                key="editor_yearly_v6",
            )
            submit_plan = st.form_submit_button("🚀 변경사항 저장 및 소요량 연산 반영")

        if submit_plan:
            st.session_state.manual_yearly_plan = edited_plan

        active_plan = st.session_state.manual_yearly_plan
        id_vars = [c for c in ["ASSY PART NO", "ASSY PART NAME"] if c in active_plan.columns]
        val_vars = [c for c in active_plan.columns if c not in id_vars]

        plan_unpivoted = pd.melt(
            active_plan,
            id_vars=id_vars,
            value_vars=val_vars,
            var_name="Period",
            value_name="Plan_Qty",
        )

    else:
        curr_df = st.session_state.manual_monthly_plan.copy()
        if "ASSY PART NAME" not in curr_df.columns:
            curr_df.insert(1, "ASSY PART NAME", curr_df["ASSY PART NO"])

        if detected_assys:
            for item in detected_assys:
                a_pn = str(item["ASSY PART NO"])
                a_name = str(item["ASSY PART NAME"])
                if a_pn not in curr_df["ASSY PART NO"].astype(str).values:
                    new_row = {
                        col: 0
                        for col in curr_df.columns
                        if col not in ["ASSY PART NO", "ASSY PART NAME"]
                    }
                    new_row["ASSY PART NO"] = a_pn
                    new_row["ASSY PART NAME"] = a_name
                    curr_df = pd.concat([curr_df, pd.DataFrame([new_row])], ignore_index=True)

        st.caption("💡 1월~12월 수량을 수정한 뒤 아래 [🚀 변경사항 저장 및 연산 반영] 버튼을 누르세요.")
        with st.form("form_monthly_plan"):
            edited_plan = st.data_editor(
                curr_df,
                num_rows="dynamic",
                use_container_width=True,
                key="editor_monthly_v6",
            )
            submit_plan = st.form_submit_button("🚀 변경사항 저장 및 소요량 연산 반영")

        if submit_plan:
            st.session_state.manual_monthly_plan = edited_plan

        active_plan = st.session_state.manual_monthly_plan
        id_vars = [c for c in ["ASSY PART NO", "ASSY PART NAME"] if c in active_plan.columns]
        val_vars = [c for c in active_plan.columns if c not in id_vars]

        plan_unpivoted = pd.melt(
            active_plan,
            id_vars=id_vars,
            value_vars=val_vars,
            var_name="Period",
            value_name="Plan_Qty",
        )

else:
    plan_file = st.file_uploader(
        "생산계획 엑셀 파일 업로드 (.xlsx)", type=["xlsx"], key="plan_file_up"
    )
    if plan_file:
        try:
            excel_p = pd.read_excel(plan_file)
            excel_p.columns = [str(c).strip() for c in excel_p.columns]

            if "ASSY PART NO" not in excel_p.columns:
                excel_p.rename(columns={excel_p.columns[0]: "ASSY PART NO"}, inplace=True)
            if len(excel_p.columns) > 1 and "ASSY PART NAME" not in excel_p.columns and not any(char.isdigit() for char in str(excel_p.columns[1])):
                excel_p.rename(columns={excel_p.columns[1]: "ASSY PART NAME"}, inplace=True)
            else:
                if "ASSY PART NAME" not in excel_p.columns:
                    excel_p["ASSY PART NAME"] = excel_p["ASSY PART NO"]

            id_vars = [c for c in ["ASSY PART NO", "ASSY PART NAME"] if c in excel_p.columns]
            qty_cols = [c for c in excel_p.columns if c not in id_vars]

            plan_unpivoted = pd.melt(
                excel_p,
                id_vars=id_vars,
                value_vars=qty_cols,
                var_name="Period",
                value_name="Plan_Qty",
            )
            st.success("생산계획 엑셀 로드 성공")
        except Exception as e:
            st.error(f"생산계획 처리 에러: {e}")

# --- 7. 결과 연산 및 제조사 필터링 분석 ---
if df_bom is not None and plan_unpivoted is not None and not plan_unpivoted.empty:
    plan_unpivoted["Plan_Qty"] = pd.to_numeric(
        plan_unpivoted["Plan_Qty"].astype(str).str.replace(",", ""), errors="coerce"
    ).fillna(0)

    bom_match = df_bom.drop(columns=["ASSY PART NAME"], errors="ignore")
    merged = pd.merge(plan_unpivoted, bom_match, on="ASSY PART NO", how="inner")

    if "ASSY PART NAME" not in merged.columns:
        merged["ASSY PART NAME"] = merged["ASSY PART NO"]

    if merged.empty:
        st.warning("⚠️ 생산계획의 'ASSY PART NO'와 BOM의 'ASSY PART NO'가 일치하지 않습니다.")
    else:
        merged["필요수량"] = merged["Plan_Qty"] * merged["소요량"]
        merged["원화_총금액"] = merged["필요수량"] * merged["원화단가"]

        st.markdown("---")
        st.subheader("3. 하위 자재 소요 및 구매금액 분석 결과")

        periods = sorted(merged["Period"].unique().tolist())
        # 정제된 고유 제조사 목록
        all_vendors = sorted(list(set(v for v in merged["제조사"].dropna() if v != "-")))

        col_f1, col_f2, col_f3, col_f4 = st.columns([1.5, 2.5, 1.8, 2.2])

        with col_f1:
            sel_period = st.selectbox("📅 분석 대상 주기", periods)

        with col_f2:
            sel_vendors = st.multiselect(
                "🏭 제조사(Vendor) 선택 (표준화 통합 완료)",
                options=all_vendors,
                default=[],
                placeholder="전체 제조사 보기"
            )

        with col_f3:
            part_type_filter = st.selectbox(
                "🏷️ 부품 구분",
                ["전체 품목 보기", "🟢 공용 부품만", "⚪ 전용 부품만"]
            )

        with col_f4:
            view_opt = st.radio(
                "보기 모드",
                ["소자(EMS PN)별 공용품 집계", "상위 Assy별 상세 전개"],
                horizontal=True,
            )

        curr_view = merged[merged["Period"] == sel_period].copy()

        if sel_vendors:
            curr_view = curr_view[curr_view["제조사"].isin(sel_vendors)]

        col_m1, col_m2, col_m3, col_m4 = st.columns(4)
        col_m1.metric("선택 주기", sel_period)
        col_m2.metric("조회 품목 수", f"{curr_view['EMS PN'].nunique():,} 종")
        col_m3.metric("총 필요 소요 수량", f"{int(curr_view['필요수량'].sum()):,} EA")
        col_m4.metric("원화 환산 총 구매금액", f"{int(curr_view['원화_총금액'].sum()):,} 원")

        if view_opt == "소자(EMS PN)별 공용품 집계":
            summary_rows = []
            for ems_pn, group in curr_view.groupby("EMS PN"):
                g_assy = (
                    group.groupby(["ASSY PART NO", "ASSY PART NAME"])
                    .agg({
                        "소요량": "first",
                        "필요수량": "sum",
                    })
                    .reset_index()
                )

                total_qty = int(group["필요수량"].sum())
                total_krw = int(group["원화_총금액"].sum())
                is_common = "🟢 공용 부품" if len(g_assy) > 1 else "⚪ 전용 부품"

                if part_type_filter == "🟢 공용 부품만" and len(g_assy) <= 1:
                    continue
                if part_type_filter == "⚪ 전용 부품만" and len(g_assy) > 1:
                    continue

                html_assy_pn = "<br>".join([
                    f"<span style='background-color: #2b2d30; padding: 2px 8px; border-radius: 4px; display: inline-block; margin: 2px 0;'>{a}</span>"
                    for a in g_assy["ASSY PART NO"]
                ])
                html_assy_name = "<br>".join([
                    f"<span style='background-color: #242629; color: #a8b2bd; padding: 2px 8px; border-radius: 4px; display: inline-block; margin: 2px 0;'>{n}</span>"
                    for n in g_assy["ASSY PART NAME"]
                ])
                html_usage = "<br>".join([
                    f"<span style='background-color: #2b2d30; padding: 2px 8px; border-radius: 4px; display: inline-block; margin: 2px 0;'>{u:g}</span>"
                    for u in g_assy["소요량"]
                ])
                html_qty = "<br>".join([
                    f"<span style='background-color: #2b2d30; padding: 2px 8px; border-radius: 4px; display: inline-block; margin: 2px 0;'>{int(q):,}</span>"
                    for q in g_assy["필요수량"]
                ])

                raw_assy_pn = "\n".join(g_assy["ASSY PART NO"].astype(str))
                raw_assy_name = "\n".join(g_assy["ASSY PART NAME"].astype(str))
                raw_usage = "\n".join(g_assy["소요량"].apply(lambda x: f"{x:g}"))
                raw_qty = "\n".join(g_assy["필요수량"].apply(lambda x: f"{int(x):,}"))

                summary_rows.append({
                    "EMS PN": ems_pn,
                    "MPN": group["MPN"].iloc[0],
                    "제조사": group["제조사"].iloc[0],
                    "구분": is_common,
                    "적용 ASSY 품번": html_assy_pn,
                    "적용 ASSY 품명": html_assy_name,
                    "단위소요량(Usage)": html_usage,
                    "ASSY별 소요물량": html_qty,
                    f"총 필요 수량 ({sel_period})": f"<b>{total_qty:,} EA</b>",
                    "통화": group["통화"].iloc[0],
                    "외화단가": f"{group['단가'].iloc[0]:.5f}",
                    "원화단가(환율적용)": f"{group['원화단가'].iloc[0]:,.2f}원",
                    "총 소요금액 (원화)": f"<b>{total_krw:,}원</b>",
                    "_total_qty_num": total_qty,
                    "_raw_assy_pn": raw_assy_pn,
                    "_raw_assy_name": raw_assy_name,
                    "_raw_usage": raw_usage,
                    "_raw_qty": raw_qty,
                    "_raw_krw": total_krw,
                })

            df_summary = pd.DataFrame(summary_rows)
            if not df_summary.empty:
                df_summary = df_summary.sort_values(by="_total_qty_num", ascending=False)

                table_cols = [
                    "EMS PN", "MPN", "제조사", "구분",
                    "적용 ASSY 품번", "적용 ASSY 품명", "단위소요량(Usage)", "ASSY별 소요물량",
                    f"총 필요 수량 ({sel_period})", "통화", "외화단가", "원화단가(환율적용)", "총 소요금액 (원화)"
                ]

                html_table = """
                <style>
                    .custom-table { width: 100%; border-collapse: collapse; font-family: sans-serif; font-size: 13.5px; }
                    .custom-table th { background-color: #1e1e1e; color: #a0a0a0; font-weight: 600; padding: 10px 8px; border-bottom: 2px solid #333; text-align: left; }
                    .custom-table td { padding: 10px 8px; border-bottom: 1px solid #2d2d2d; vertical-align: middle; color: #e0e0e0; }
                    .custom-table tr:hover { background-color: #262626; }
                </style>
                <table class="custom-table"><thead><tr>
                """
                for col in table_cols:
                    html_table += f"<th>{col}</th>"
                html_table += "</tr></thead><tbody>"

                for _, r in df_summary.iterrows():
                    html_table += "<tr>"
                    for col in table_cols:
                        align = "right" if ("금액" in col or "수량" in col or "단가" in col) else "left"
                        html_table += f"<td style='text-align: {align};'>{r[col]}</td>"
                    html_table += "</tr>"
                html_table += "</tbody></table>"

                st.markdown(html_table, unsafe_allow_html=True)

                excel_df = df_summary[[
                    "EMS PN", "MPN", "제조사", "구분",
                    "_raw_assy_pn", "_raw_assy_name", "_raw_usage", "_raw_qty",
                    "_total_qty_num", "통화", "외화단가", "원화단가(환율적용)", "_raw_krw"
                ]].rename(columns={
                    "_raw_assy_pn": "적용 ASSY 품번",
                    "_raw_assy_name": "적용 ASSY 품명",
                    "_raw_usage": "단위소요량(Usage)",
                    "_raw_qty": "ASSY별 소요물량",
                    "_total_qty_num": f"총 필요 수량 ({sel_period})",
                    "_raw_krw": "총 소요금액 (원화)"
                })
            else:
                st.info("선택한 필터 조건에 해당하는 부품이 없습니다.")
                excel_df = pd.DataFrame()

        else:
            final_cols = [
                "ASSY PART NO", "ASSY PART NAME", "EMS PN", "MPN", "제조사",
                "소요량", "필요수량", "통화", "단가", "원화단가", "원화_총금액"
            ]
            curr_view["필요수량"] = curr_view["필요수량"].apply(np.ceil).astype(int)
            curr_view["원화_총금액"] = curr_view["원화_총금액"].apply(np.ceil).astype(int)
            excel_df = curr_view[final_cols].rename(columns={
                "소요량": "단위소요량(Usage)",
                "필요수량": f"필요 수량 ({sel_period})",
                "단가": "외화단가",
                "원화단가": "원화단가(환율적용)",
                "원화_총금액": "총 소요금액 (원화)"
            }).sort_values(by=f"필요 수량 ({sel_period})", ascending=False)

            st.dataframe(
                excel_df.style.format({
                    "단위소요량(Usage)": "{:g}",
                    "외화단가": "{:.5f}",
                    "원화단가(환율적용)": "{:,.2f}원",
                    "총 소요금액 (원화)": "{:,.0f}원",
                    f"필요 수량 ({sel_period})": "{:,} EA",
                }),
                use_container_width=True,
                hide_index=True,
            )

        # 전체 기간 가로 매트릭스
        with st.expander("📈 [전체 주기별 소요량 매트릭스] EMS PN별 추이"):
            pivot_matrix = (
                pd.pivot_table(
                    merged if not sel_vendors else merged[merged["제조사"].isin(sel_vendors)],
                    index=["EMS PN", "MPN", "제조사", "통화", "원화단가"],
                    columns="Period",
                    values="필요수량",
                    aggfunc="sum",
                    fill_value=0,
                )
                .round(0)
                .astype(int)
                .reset_index()
            )
            st.dataframe(pivot_matrix, use_container_width=True)

        # 엑셀 다운로드
        if not excel_df.empty:
            out_buf = io.BytesIO()
            with pd.ExcelWriter(out_buf, engine="openpyxl") as writer:
                excel_df.to_excel(writer, sheet_name=f"요약_{sel_period}", index=False)
                pivot_matrix.to_excel(writer, sheet_name="주기별_전체매트릭스", index=False)

            st.download_button(
                label=f"📥 [{sel_period}] 필터링 결과 엑셀 다운로드",
                data=out_buf.getvalue(),
                file_name=f"PCB_자재소요량_{sel_period}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
