import io
import json
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
    "효성전기 양산 모터 PCB Assy 자재 집계 | 사업계획/실시간 환율 연동 및 중장기 구매금액 자동 산출"
)

# --- 1. 환율 관리 (사이드바) ---
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
                "JPY": round((krw_per_usd / jpy_per_usd) * 100, 2),  # 100엔 기준
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

# --- 2. 기본 생산 계획 템플릿 세션 관리 (KeyError 방어 로직) ---
def init_yearly_plan():
    return pd.DataFrame({
        "ASSY PART NO": ["THS0143301", "E0280014C01"],
        "ASSY PART NAME": ["MX5 PCB", "Blower Board"],
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
        "ASSY PART NAME": ["MX5 PCB", "Blower Board"],
    }
    for m in months:
        init_data[m] = [12500, 15000]
    return pd.DataFrame(init_data)

# 기존 세션에 ASSY PART NAME이 없으면 강제 재설정
if "manual_yearly_plan" not in st.session_state or "ASSY PART NAME" not in st.session_state.manual_yearly_plan.columns:
    st.session_state.manual_yearly_plan = init_yearly_plan()

if "manual_monthly_plan" not in st.session_state or "ASSY PART NAME" not in st.session_state.manual_monthly_plan.columns:
    st.session_state.manual_monthly_plan = init_monthly_plan()

# --- 3. 영역 1: BOM 입력 ---
st.subheader("1. PCB Assy 하위 BOM 입력")
tab_bom_paste, tab_bom_file = st.tabs(
    ["📋 BOM 텍스트 붙여넣기", "📂 BOM 엑셀 업로드 (.xlsx)"]
)
raw_df_bom = None

with tab_bom_paste:
    sample_text = (
        "PART NO\tPART NAME\tEMS PN\tMPN\tManufacturer\tper unit\t통화\tprice\n"
        "THS0143301\tMX5 PCB\tE0424-847-00\tAC0402FR-07100KL\tYAGEO\t10\tUSD\t0.00052\n"
        "E0280014C01\tBlower Board\tE0424-847-00\tAC0402FR-07100KL\tYAGEO\t10\tUSD\t0.00052\n"
        "THS0143301\tMX5 PCB\tF0483-185-00\tIPC100N04S5-2R8\tINFINEON\t7\tUSD\t0.21000\n"
        "E0280014C01\tBlower Board\tF0483-185-00\tIPC100N04S5-2R8\tINFINEON\t7\tUSD\t0.21000\n"
        "THS0143301\tMX5 PCB\tE0401-149-00\tHBY331M1ETR-1010KEGA\tLelon\t4\tUSD\t0.24000\n"
        "THS0143301\tMX5 PCB\tE0405-009-00\t06031C103K4Z4A\tAVX\t4\tUSD\t0.00650"
    )
    bom_input_text = st.text_area(
        "엑셀에서 복사한 BOM을 붙여넣으세요 (제목 행 포함)",
        value=sample_text,
        height=180,
    )
    if bom_input_text.strip():
        try:
            raw_df_bom = pd.read_csv(
                io.StringIO(bom_input_text), sep=r"\t", engine="python"
            )
        except Exception:
            raw_df_bom = pd.read_csv(
                io.StringIO(bom_input_text), sep=r"\s+", engine="python"
            )

with tab_bom_file:
    bom_file = st.file_uploader(
        "BOM 엑셀 파일 (.xlsx)", type=["xlsx"], key="bom_file_up"
    )
    if bom_file:
        try:
            raw_df_bom = pd.read_excel(bom_file)
        except Exception as e:
            st.error(f"엑셀 로드 실패: {e}")

# --- 4. BOM 컬럼 매핑 및 정제 ---
df_bom = None
detected_assys = []

if raw_df_bom is not None and not raw_df_bom.empty:
    df_bom = raw_df_bom.copy()
    df_bom.columns = [str(c).strip() for c in df_bom.columns]

    bom_col_map = {
        "PART NO": "ASSY PART NO",
        "PART_NO": "ASSY PART NO",
        "ASSY_PN": "ASSY PART NO",
        "모품번": "ASSY PART NO",
        "PART NAME": "ASSY PART NAME",
        "PART_NAME": "ASSY PART NAME",
        "모품명": "ASSY PART NAME",
        "Part Number": "EMS PN",
        "part number": "EMS PN",
        "자재번호": "EMS PN",
        "하위품번": "EMS PN",
        "EMS PN": "EMS PN",
        "EMS_PN": "EMS PN",
        "manufacturer part no.": "MPN",
        "manufacturer part no": "MPN",
        "제조사 PART NO": "MPN",
        "MPN": "MPN",
        "규격": "MPN",
        "Manufacturer": "제조사",
        "MANUFACTURER": "제조사",
        "제조원": "제조사",
        "Vendor": "제조사",
        "per unit": "소요량",
        "per_unit": "소요량",
        "usage": "소요량",
        "Usage": "소요량",
        "소요량": "소요량",
        "price": "단가",
        "단가": "단가",
        "단가(외화)": "단가",
    }

    for col in list(df_bom.columns):
        if col in bom_col_map:
            df_bom.rename(columns={col: bom_col_map[col]}, inplace=True)
        elif col.lower() in [k.lower() for k in bom_col_map.keys()]:
            for k, v in bom_col_map.items():
                if col.lower() == k.lower():
                    df_bom.rename(columns={col: v}, inplace=True)
                    break

    if "통화" not in df_bom.columns:
        df_bom["통화"] = "KRW"
    else:
        df_bom["통화"] = (
            df_bom["통화"].astype(str).str.strip().str.upper().fillna("KRW")
        )

    df_bom["소요량"] = pd.to_numeric(
        df_bom.get("소요량", 1.0), errors="coerce"
    ).fillna(1.0)
    df_bom["단가"] = pd.to_numeric(
        df_bom.get("단가", 0.0), errors="coerce"
    ).fillna(0.0)

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

    if "제조사" not in df_bom.columns:
        df_bom["제조사"] = "-"
    if "MPN" not in df_bom.columns:
        df_bom["MPN"] = df_bom.get("EMS PN", "-")
    if "ASSY PART NAME" not in df_bom.columns:
        df_bom["ASSY PART NAME"] = df_bom.get("ASSY PART NO", "-")

    detected_assys = (
        df_bom[["ASSY PART NO", "ASSY PART NAME"]]
        .drop_duplicates()
        .to_dict(orient="records")
    )

# --- 5. 영역 2: 생산계획 (품번/품명 칸 분리 & KeyError 방어) ---
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
                a_pn = item["ASSY PART NO"]
                a_name = item["ASSY PART NAME"]
                if a_pn not in curr_df["ASSY PART NO"].values:
                    new_row = {
                        col: 0
                        for col in curr_df.columns
                        if col not in ["ASSY PART NO", "ASSY PART NAME"]
                    }
                    new_row["ASSY PART NO"] = a_pn
                    new_row["ASSY PART NAME"] = a_name
                    curr_df = pd.concat(
                        [curr_df, pd.DataFrame([new_row])], ignore_index=True
                    )

        st.caption(
            "💡 품번 및 품명과 각 연도별 수량을 더블 클릭해 직접 수정할 수 있습니다."
        )
        edited_plan = st.data_editor(
            curr_df,
            num_rows="dynamic",
            use_container_width=True,
            key="editor_yearly_v2",
        )
        st.session_state.manual_yearly_plan = edited_plan

        id_vars = [c for c in ["ASSY PART NO", "ASSY PART NAME"] if c in edited_plan.columns]
        val_vars = [c for c in edited_plan.columns if c not in id_vars]

        plan_unpivoted = pd.melt(
            edited_plan,
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
                a_pn = item["ASSY PART NO"]
                a_name = item["ASSY PART NAME"]
                if a_pn not in curr_df["ASSY PART NO"].values:
                    new_row = {
                        col: 0
                        for col in curr_df.columns
                        if col not in ["ASSY PART NO", "ASSY PART NAME"]
                    }
                    new_row["ASSY PART NO"] = a_pn
                    new_row["ASSY PART NAME"] = a_name
                    curr_df = pd.concat(
                        [curr_df, pd.DataFrame([new_row])], ignore_index=True
                    )

        st.caption(
            "💡 품번 및 품명과 1월~12월 수량을 직접 수정할 수 있습니다."
        )
        edited_plan = st.data_editor(
            curr_df,
            num_rows="dynamic",
            use_container_width=True,
            key="editor_monthly_v2",
        )
        st.session_state.manual_monthly_plan = edited_plan

        id_vars = [c for c in ["ASSY PART NO", "ASSY PART NAME"] if c in edited_plan.columns]
        val_vars = [c for c in edited_plan.columns if c not in id_vars]

        plan_unpivoted = pd.melt(
            edited_plan,
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
                excel_p.rename(
                    columns={excel_p.columns[0]: "ASSY PART NO"}, inplace=True
                )
            if (
                len(excel_p.columns) > 1
                and "ASSY PART NAME" not in excel_p.columns
                and not any(char.isdigit() for char in str(excel_p.columns[1]))
            ):
                excel_p.rename(
                    columns={excel_p.columns[1]: "ASSY PART NAME"}, inplace=True
                )
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

# --- 6. 결과 연산 및 표시 ---
if df_bom is not None and plan_unpivoted is not None and not plan_unpivoted.empty:
    plan_unpivoted["Plan_Qty"] = pd.to_numeric(
        plan_unpivoted["Plan_Qty"], errors="coerce"
    ).fillna(0)

    # 품번 기준 Merge (생산계획 품명 우선, 없을 경우 BOM 품명)
    bom_match = df_bom.drop(columns=["ASSY PART NAME"], errors="ignore")
    merged = pd.merge(plan_unpivoted, bom_match, on="ASSY PART NO", how="inner")

    if "ASSY PART NAME" not in merged.columns:
        merged["ASSY PART NAME"] = merged["ASSY PART NO"]

    if merged.empty:
        st.warning(
            "⚠️ 생산계획의 'ASSY PART NO'와 BOM의 'ASSY PART NO'가 일치하지 않습니다."
        )
    else:
        merged["필요수량"] = merged["Plan_Qty"] * merged["소요량"]
        merged["원화_총금액"] = merged["필요수량"] * merged["원화단가"]

        st.markdown("---")
        st.subheader("3. 하위 자재 소요 및 구매금액 분석 결과")

        periods = sorted(merged["Period"].unique().tolist())
        col_f1, col_f2 = st.columns([2, 4])
        with col_f1:
            sel_period = st.selectbox("📅 분석 대상 주기 선택 (드롭다운)", periods)
        with col_f2:
            view_opt = st.radio(
                "보기 모드",
                ["소자(EMS PN)별 공용품 집계", "상위 Assy별 상세 전개"],
                horizontal=True,
            )

        curr_view = merged[merged["Period"] == sel_period].copy()

        # 메트릭 카드
        col_m1, col_m2, col_m3, col_m4 = st.columns(4)
        col_m1.metric("선택 주기", sel_period)
        col_m2.metric(
            "투입 소자 품목 수", f"{curr_view['EMS PN'].nunique():,} 종"
        )
        col_m3.metric(
            "총 필요 소요 수량", f"{int(curr_view['필요수량'].sum()):,} EA"
        )
        col_m4.metric(
            "원화 환산 총 구매금액",
            f"{int(curr_view['원화_총금액'].sum()):,} 원",
        )

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
                is_common = (
                    "🟢 공용 부품" if len(g_assy) > 1 else "⚪ 전용 부품"
                )

                # HTML 뱃지/줄바꿈 블록 생성
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

                # 엑셀 다운로드용 텍스트
                raw_assy_pn = "\n".join(g_assy["ASSY PART NO"].astype(str))
                raw_assy_name = "\n".join(g_assy["ASSY PART NAME"].astype(str))
                raw_usage = "\n".join(
                    g_assy["소요량"].apply(lambda x: f"{x:g}")
                )
                raw_qty = "\n".join(
                    g_assy["필요수량"].apply(lambda x: f"{int(x):,}")
                )

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

            df_summary = pd.DataFrame(summary_rows).sort_values(
                by="_total_qty_num", ascending=False
            )

            table_cols = [
                "EMS PN",
                "MPN",
                "제조사",
                "구분",
                "적용 ASSY 품번",
                "적용 ASSY 품명",
                "단위소요량(Usage)",
                "ASSY별 소요물량",
                f"총 필요 수량 ({sel_period})",
                "통화",
                "외화단가",
                "원화단가(환율적용)",
                "총 소요금액 (원화)",
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
                    align = (
                        "right"
                        if "금액" in col or "수량" in col or "단가" in col
                        else "left"
                    )
                    html_table += (
                        f"<td style='text-align: {align};'>{r[col]}</td>"
                    )
                html_table += "</tr>"
            html_table += "</tbody></table>"

            st.markdown(html_table, unsafe_allow_html=True)

            excel_df = df_summary[[
                "EMS PN",
                "MPN",
                "제조사",
                "구분",
                "_raw_assy_pn",
                "_raw_assy_name",
                "_raw_usage",
                "_raw_qty",
                "_total_qty_num",
                "통화",
                "외화단가",
                "원화단가(환율적용)",
                "_raw_krw",
            ]].rename(
                columns={
                    "_raw_assy_pn": "적용 ASSY 품번",
                    "_raw_assy_name": "적용 ASSY 품명",
                    "_raw_usage": "단위소요량(Usage)",
                    "_raw_qty": "ASSY별 소요물량",
                    "_total_qty_num": f"총 필요 수량 ({sel_period})",
                    "_raw_krw": "총 소요금액 (원화)",
                }
            )

        else:
            final_cols = [
                "ASSY PART NO",
                "ASSY PART NAME",
                "EMS PN",
                "MPN",
                "제조사",
                "소요량",
                "필요수량",
                "통화",
                "단가",
                "원화단가",
                "원화_총금액",
            ]
            curr_view["필요수량"] = (
                curr_view["필요수량"].apply(np.ceil).astype(int)
            )
            curr_view["원화_총금액"] = (
                curr_view["원화_총금액"].apply(np.ceil).astype(int)
            )
            excel_df = curr_view[final_cols].rename(
                columns={
                    "소요량": "단위소요량(Usage)",
                    "필요수량": f"필요 수량 ({sel_period})",
                    "단가": "외화단가",
                    "원화단가": "원화단가(환율적용)",
                    "원화_총금액": "총 소요금액 (원화)",
                }
            ).sort_values(by=f"필요 수량 ({sel_period})", ascending=False)

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
                    merged,
                    index=[
                        "EMS PN",
                        "MPN",
                        "제조사",
                        "통화",
                        "원화단가",
                    ],
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
        out_buf = io.BytesIO()
        with pd.ExcelWriter(out_buf, engine="openpyxl") as writer:
            excel_df.to_excel(
                writer, sheet_name=f"요약_{sel_period}", index=False
            )
            pivot_matrix.to_excel(
                writer, sheet_name="주기별_전체매트릭스", index=False
            )

        st.download_button(
            label=f"📥 [{sel_period}] 결과 엑셀 다운로드",
            data=out_buf.getvalue(),
            file_name=f"PCB_하위자재_소요량_{sel_period}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
