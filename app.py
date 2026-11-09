import io
import math
import numpy as np
import pandas as pd
import streamlit as st

# --- 페이지 기본 설정 ---
st.set_page_config(
    page_title="PCB Assy BOM & 소요량 MRP 트래커",
    page_icon="🧩",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("🧩 PCB Assembly 하위 자재 종합 소요량 트래커")
st.caption(
    "효성전기 양산 모터 PCB Assy 자재 집계 | 공용 소자 식별 및 주/월/년 발주 소요량 자동 산출"
)

# --- 1. 샘플 데이터 생성 헬퍼 ---


def get_sample_bom():
    data = [
        # Assy 1: Blower Motor Driver Board (B100-PCB)
        {
            "Assy_PN": "B100-PCB",
            "Part_PN": "BB-4L-001",
            "Part_Name": "Bare Board 4-Layer (FR-4 2oz)",
            "Usage": 1,
            "Loss_Rate": 0.0,
            "MOQ": 500,
            "SPQ": 100,
            "Vendor": "USI",
        },
        {
            "Assy_PN": "B100-PCB",
            "Part_PN": "CAP-100N-0603",
            "Part_Name": "MLCC 100nF 50V 0603",
            "Usage": 8,
            "Loss_Rate": 1.0,
            "MOQ": 4000,
            "SPQ": 4000,
            "Vendor": "Murata",
        },
        {
            "Assy_PN": "B100-PCB",
            "Part_PN": "RES-SH-001",
            "Part_Name": "Shunt Resistor 1mR 3W 2512",
            "Usage": 1,
            "Loss_Rate": 0.5,
            "MOQ": 1000,
            "SPQ": 1000,
            "Vendor": "Vishay",
        },
        {
            "Assy_PN": "B100-PCB",
            "Part_PN": "FET-N-40V",
            "Part_Name": "Power MOSFET 40V 100A",
            "Usage": 6,
            "Loss_Rate": 0.5,
            "MOQ": 2500,
            "SPQ": 500,
            "Vendor": "Infineon",
        },
        {
            "Assy_PN": "B100-PCB",
            "Part_PN": "CON-PWR-04P",
            "Part_Name": "Header Connector 4-Pin",
            "Usage": 1,
            "Loss_Rate": 0.0,
            "MOQ": 600,
            "SPQ": 150,
            "Vendor": "Molex",
        },
        # Assy 2: EPS 65A Control Board (EPS-65A-PCB)
        {
            "Assy_PN": "EPS-65A-PCB",
            "Part_PN": "BB-6L-002",
            "Part_Name": "Bare Board 6-Layer (FR-4 2oz)",
            "Usage": 1,
            "Loss_Rate": 0.0,
            "MOQ": 300,
            "SPQ": 50,
            "Vendor": "KCE",
        },
        {
            "Assy_PN": "EPS-65A-PCB",
            "Part_PN": "CAP-100N-0603",
            "Part_Name": "MLCC 100nF 50V 0603",
            "Usage": 14,
            "Loss_Rate": 1.0,
            "MOQ": 4000,
            "SPQ": 4000,
            "Vendor": "Murata",
        },  # 공용품
        {
            "Assy_PN": "EPS-65A-PCB",
            "Part_PN": "RES-SH-001",
            "Part_Name": "Shunt Resistor 1mR 3W 2512",
            "Usage": 3,
            "Loss_Rate": 0.5,
            "MOQ": 1000,
            "SPQ": 1000,
            "Vendor": "Vishay",
        },  # 공용품
        {
            "Assy_PN": "EPS-65A-PCB",
            "Part_PN": "FET-N-40V",
            "Part_Name": "Power MOSFET 40V 100A",
            "Usage": 6,
            "Loss_Rate": 0.5,
            "MOQ": 2500,
            "SPQ": 500,
            "Vendor": "Infineon",
        },  # 공용품
        {
            "Assy_PN": "EPS-65A-PCB",
            "Part_PN": "MCU-32B-100P",
            "Part_Name": "Automotive 32-bit MCU LQFP100",
            "Usage": 1,
            "Loss_Rate": 0.0,
            "MOQ": 500,
            "SPQ": 250,
            "Vendor": "NXP",
        },
    ]
    return pd.DataFrame(data)


def get_sample_plan():
    data = [
        {"Period": "2027-W01", "Assy_PN": "B100-PCB", "Plan_Qty": 2500},
        {"Period": "2027-W01", "Assy_PN": "EPS-65A-PCB", "Plan_Qty": 1800},
        {"Period": "2027-W02", "Assy_PN": "B100-PCB", "Plan_Qty": 3000},
        {"Period": "2027-W02", "Assy_PN": "EPS-65A-PCB", "Plan_Qty": 2000},
        {"Period": "2027-W03", "Assy_PN": "B100-PCB", "Plan_Qty": 2800},
        {"Period": "2027-W03", "Assy_PN": "EPS-65A-PCB", "Plan_Qty": 2200},
        {"Period": "2027-W04", "Assy_PN": "B100-PCB", "Plan_Qty": 3200},
        {"Period": "2027-W04", "Assy_PN": "EPS-65A-PCB", "Plan_Qty": 2500},
        {"Period": "2027-02", "Assy_PN": "B100-PCB", "Plan_Qty": 12000},
        {"Period": "2027-02", "Assy_PN": "EPS-65A-PCB", "Plan_Qty": 9500},
        {"Period": "2027-Year", "Assy_PN": "B100-PCB", "Plan_Qty": 150000},
        {"Period": "2027-Year", "Assy_PN": "EPS-65A-PCB", "Plan_Qty": 120000},
    ]
    return pd.DataFrame(data)


# --- 2. 사이드바: 데이터 업로드 및 모드 설정 ---
st.sidebar.header("⚙️ 데이터 입력 설정")
input_method = st.sidebar.radio(
    "데이터 입력 방식 선택",
    ["샘플 데이터로 확인", "엑셀 파일 업로드 (.xlsx)", "엑셀 복사/붙여넣기"],
)

df_bom = None
df_plan = None

if input_method == "샘플 데이터로 확인":
    df_bom = get_sample_bom()
    df_plan = get_sample_plan()
    st.sidebar.info("기본 내장된 모터 제어보드 샘플 데이터를 사용 중입니다.")

elif input_method == "엑셀 파일 업로드 (.xlsx)":
    uploaded_file = st.sidebar.file_uploader(
        "BOM 및 계획 엑셀 파일 업로드", type=["xlsx"]
    )
    if uploaded_file is not None:
        try:
            excel = pd.ExcelFile(uploaded_file)
            sheet_names = excel.sheet_names
            bom_sheet = st.sidebar.selectbox("BOM 시트 선택", sheet_names, index=0)
            plan_sheet = st.sidebar.selectbox(
                "생산계획 시트 선택",
                sheet_names,
                index=1 if len(sheet_names) > 1 else 0,
            )
            df_bom = pd.read_excel(uploaded_file, sheet_name=bom_sheet)
            df_plan = pd.read_excel(uploaded_file, sheet_name=plan_sheet)
        except Exception as e:
            st.error(f"파일을 읽는 중 에러가 발생했습니다: {e}")

elif input_method == "엑셀 복사/붙여넣기":
    st.sidebar.markdown(
        "**[BOM 컬럼 순서]**: Assy_PN, Part_PN, Part_Name, Usage, Loss_Rate, MOQ, SPQ, Vendor"
    )
    bom_raw = st.text_area(
        "1. BOM 테이블 복사 붙여넣기 (Tab 구분)", height=150
    )
    st.sidebar.markdown(
        "**[생산계획 컬럼 순서]**: Period (주차/월/년), Assy_PN, Plan_Qty"
    )
    plan_raw = st.text_area("2. 생산계획 테이블 복사 붙여넣기", height=150)

    if bom_raw and plan_raw:
        try:
            df_bom = pd.read_csv(io.StringIO(bom_raw), sep="\t")
            df_plan = pd.read_csv(io.StringIO(plan_raw), sep="\t")
        except Exception as e:
            st.error(f"텍스트 파싱 에러: {e}")

# --- 3. 데이터 검증 및 연산 파이프라인 ---
if df_bom is not None and df_plan is not None:
    # 컬럼 공백 제거
    df_bom.columns = [c.strip() for c in df_bom.columns]
    df_plan.columns = [c.strip() for c in df_plan.columns]

    # 기본 필수 컬럼 기본값 처리
    if "Loss_Rate" not in df_bom.columns:
        df_bom["Loss_Rate"] = 0.0
    if "MOQ" not in df_bom.columns:
        df_bom["MOQ"] = 1
    if "SPQ" not in df_bom.columns:
        df_bom["SPQ"] = 1
    if "Vendor" not in df_bom.columns:
        df_bom["Vendor"] = "-"
    if "Part_Name" not in df_bom.columns:
        df_bom["Part_Name"] = df_bom["Part_PN"]

    # 숫자 타입 강제 변환
    df_bom["Usage"] = pd.to_numeric(df_bom["Usage"], errors="coerce").fillna(0)
    df_bom["Loss_Rate"] = pd.to_numeric(
        df_bom["Loss_Rate"], errors="coerce"
    ).fillna(0)
    df_bom["MOQ"] = pd.to_numeric(df_bom["MOQ"], errors="coerce").fillna(1)
    df_bom["SPQ"] = pd.to_numeric(df_bom["SPQ"], errors="coerce").fillna(1)
    df_plan["Plan_Qty"] = pd.to_numeric(
        df_plan["Plan_Qty"], errors="coerce"
    ).fillna(0)

    # 상위 Assy와 하위 BOM 매핑 (Inner Join)
    merged = pd.merge(df_plan, df_bom, on="Assy_PN", how="inner")

    # 이론 소요량 = 계획수량 * Usage * (1 + Loss/100)
    merged["Net_Required_Qty"] = (
        merged["Plan_Qty"]
        * merged["Usage"]
        * (1 + (merged["Loss_Rate"] / 100.0))
    )

    # 기간(Period) 선택 필터링
    periods = df_plan["Period"].unique().tolist()
    st.sidebar.markdown("---")
    st.sidebar.subheader("📅 분석 주기 선택")
    selected_period = st.sidebar.selectbox("트래킹 대상 기간(주/월/년)", periods)

    filtered = merged[merged["Period"] == selected_period]

    # --- 4. 하위 부품 단위 종합 집계 (Aggregation) ---
    def calc_po_qty(net_qty, moq, spq):
        if net_qty <= 0:
            return 0
        moq_applied = max(net_qty, moq)
        if spq > 1:
            return math.ceil(moq_applied / spq) * spq
        return math.ceil(moq_applied)

    summary = (
        filtered.groupby("Part_PN")
        .agg(
            Part_Name=("Part_Name", "first"),
            Vendor=("Vendor", "first"),
            MOQ=("MOQ", "first"),
            SPQ=("SPQ", "first"),
            Loss_Rate_Avg=("Loss_Rate", "mean"),
            Applied_Assy_Count=("Assy_PN", "nunique"),
            Assy_List=("Assy_PN", lambda x: ", ".join(sorted(set(x)))),
            Total_Net_Qty=("Net_Required_Qty", "sum"),
        )
        .reset_index()
    )

    # 발주 단위 올림(PO 수량) 계산
    summary["Total_Net_Qty_Ceil"] = summary["Total_Net_Qty"].apply(np.ceil)
    summary["Order_PO_Qty"] = summary.apply(
        lambda r: calc_po_qty(r["Total_Net_Qty"], r["MOQ"], r["SPQ"]), axis=1
    )
    summary["Common_Type"] = summary["Applied_Assy_Count"].apply(
        lambda x: "🟢 공용 소자" if x > 1 else "⚪ 단독 전용"
    )

    # --- 5. UI 대시보드 렌더링 ---
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("대상 기간", selected_period)
    with col2:
        st.metric("투입 하위 소자 총 수", f"{len(summary):,} 종")
    with col3:
        common_count = (summary["Applied_Assy_Count"] > 1).sum()
        st.metric("공용 부품(Common Parts)", f"{common_count} 종")
    with col4:
        total_parts_qty = summary["Total_Net_Qty_Ceil"].sum()
        st.metric("총 순소요량(Net Pcs)", f"{int(total_parts_qty):,} EA")

    st.markdown("---")

    # 필터 옵션
    view_filter = st.radio(
        "부품 구분 필터",
        ["전체 보기", "공용 소자만 보기 (다품종 중복)", "단독 부품만 보기"],
        horizontal=True,
    )
    display_df = summary.copy()
    if view_filter == "공용 소자만 보기 (다품종 중복)":
        display_df = display_df[display_df["Applied_Assy_Count"] > 1]
    elif view_filter == "단독 부품만 보기":
        display_df = display_df[display_df["Applied_Assy_Count"] == 1]

    # 정렬: 소요 수량 내림차순
    display_df = display_df.sort_values(by="Total_Net_Qty", ascending=False)

    st.subheader(f"📊 [{selected_period}] 하위 부품 소요 집계 현황")
    st.dataframe(
        display_df[[
            "Part_PN",
            "Part_Name",
            "Common_Type",
            "Assy_List",
            "Vendor",
            "Total_Net_Qty_Ceil",
            "MOQ",
            "SPQ",
            "Order_PO_Qty",
        ]].rename(
            columns={
                "Part_PN": "자재 P/N",
                "Part_Name": "품명/규격",
                "Common_Type": "구분",
                "Assy_List": "적용 PCB Assy",
                "Vendor": "공급사",
                "Total_Net_Qty_Ceil": "순소요량 (EA)",
                "MOQ": "MOQ",
                "SPQ": "SPQ",
                "Order_PO_Qty": "발주 소요량 (MOQ/SPQ반영)",
            }
        ),
        use_container_width=True,
        hide_index=True,
    )

    # --- 6. 피벗 테이블: 전체 기간 종합 비교 (Assy별 / 주·월·년 기간별 소요량 매트릭스) ---
    with st.expander("📈 [전 기간 매트릭스] 부품 P/N별 기간 추이 보기"):
        matrix = pd.pivot_table(
            merged,
            index=["Part_PN", "Part_Name", "Vendor"],
            columns="Period",
            values="Net_Required_Qty",
            aggfunc="sum",
            fill_value=0,
        ).reset_index()
        st.dataframe(matrix, use_container_width=True)

    # --- 7. 결과 엑셀 다운로드 (XLSX Export) ---
    excel_buffer = io.BytesIO()
    with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
        display_df.to_excel(
            writer, sheet_name=f"Summary_{selected_period}", index=False
        )
        merged.to_excel(writer, sheet_name="Full_Exploded_BOM", index=False)
        matrix.to_excel(writer, sheet_name="Period_Pivot_Matrix", index=False)

    st.download_button(
        label="📥 현재 집계 결과 및 전체 매트릭스 엑셀 다운로드",
        data=excel_buffer.getvalue(),
        file_name=f"PCB_Parts_Requirement_{selected_period}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

else:
    st.warning(
        "좌측 사이드바에서 데이터를 업로드하거나 붙여넣어 주십시오."
    )
