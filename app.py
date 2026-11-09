import io
import numpy as np
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="PCB Assy 자재 소요량 트래커", page_icon="📊", layout="wide"
)

st.title("📊 PCB Assembly 하위 자재 월별 소요량 트래커")
st.caption("Assy별 월 생산계획 및 단위 Usage 기반 하위 소자 종합 소요량 집계")

# --- 1. 기본 데이터 셋업 (초기값) ---
DEFAULT_ASSYS = ["B100-PCB", "EPS-65A-PCB", "L-VENT-PCB"]
MONTHS = [f"{m}월" for m in range(1, 13)]

# 기본 생산 계획 템플릿 (1월 ~ 12월)
if "prod_plan" not in st.session_state:
    plan_data = {
        "Assy_PN": DEFAULT_ASSYS,
        "1월": [25000, 18000, 12000],
        "2월": [27000, 20000, 13000],
        "3월": [30000, 22000, 15000],
        "4월": [30000, 22000, 15000],
        "5월": [28000, 21000, 14000],
        "6월": [28000, 21000, 14000],
        "7월": [25000, 19000, 12000],
        "8월": [22000, 17000, 10000],
        "9월": [29000, 21000, 14000],
        "10월": [31000, 23000, 16000],
        "11월": [32000, 24000, 17000],
        "12월": [26000, 19000, 13000],
    }
    st.session_state.prod_plan = pd.DataFrame(plan_data)

# 기본 BOM 샘플
SAMPLE_BOM = """Assy_PN	Part_No	품명	제조사	Usage	로스율(%)
B100-PCB	BB-4L-001	Bare Board 4L	제이앤디	1	0
B100-PCB	CAP-100N-0603	MLCC 100nF 0603	Murata	8	1.0
B100-PCB	RES-SH-001	Shunt 저항 1mR	Vishay	1	0.5
B100-PCB	FET-40V-100A	Power MOSFET	Infineon	6	0.5
B100-PCB	CON-4P	Header Conn 4P	Molex	1	0
EPS-65A-PCB	BB-6L-002	Bare Board 6L	KCE	1	0
EPS-65A-PCB	CAP-100N-0603	MLCC 100nF 0603	Murata	14	1.0
EPS-65A-PCB	RES-SH-001	Shunt 저항 1mR	Vishay	3	0.5
EPS-65A-PCB	FET-40V-100A	Power MOSFET	Infineon	6	0.5
EPS-65A-PCB	MCU-32B	32bit MCU	NXP	1	0
L-VENT-PCB	BB-2L-003	Bare Board 2L	USI	1	0
L-VENT-PCB	CAP-100N-0603	MLCC 100nF 0603	Murata	4	1.0
L-VENT-PCB	RES-SH-001	Shunt 저항 1mR	Vishay	1	0.5"""

# --- 2. 상단: 월별 생산 계획 입력 테이블 (편집 가능) ---
st.subheader("1. 상위 PCB Assy 월별 생산 계획 (수량 직접 수정 가능)")
st.caption("표 안의 셀을 더블 클릭해 직접 수량을 변경하거나 품목을 추가할 수 있습니다.")

edited_plan = st.data_editor(
    st.session_state.prod_plan,
    num_rows="dynamic",
    use_container_width=True,
    key="plan_editor",
)

# --- 3. 중단: 하위 BOM 입력 (복사 붙여넣기 / 파일 업로드) ---
st.markdown("---")
st.subheader("2. PCB Assy별 하위 자재(BOM) 목록 입력")

tab_paste, tab_upload = st.tabs(["📋 엑셀 복사/붙여넣기", "📁 엑셀 파일 업로드"])
df_bom = None

with tab_paste:
    st.markdown(
        "**[컬럼 형식]**: `Assy_PN` | `Part_No` | `품명` | `제조사` | `Usage` | `로스율(%)` *(엑셀에서 복사해 붙여넣기)*"
    )
    bom_raw = st.text_area(
        "BOM 텍스트 붙여넣기", value=SAMPLE_BOM, height=180
    )
    if bom_raw.strip():
        try:
            df_bom = pd.read_csv(io.StringIO(bom_raw), sep="\t")
        except Exception as e:
            st.error(f"BOM 파싱 실패: {e}")

with tab_upload:
    uploaded = st.file_uploader("BOM 엑셀 파일(.xlsx) 선택", type=["xlsx"])
    if uploaded is not None:
        try:
            df_bom = pd.read_excel(uploaded)
        except Exception as e:
            st.error(f"엑셀 파일 로드 실패: {e}")

# --- 4. 데이터 연산 및 소요량 산출 ---
if df_bom is not None and not df_bom.empty and edited_plan is not None:
    # 컬럼 정리
    df_bom.columns = [c.strip() for c in df_bom.columns]
    
    # 필수 컬럼 매핑 방어
    col_map = {
        "Part No": "Part_No", "part no": "Part_No", "Part_PN": "Part_No", "자재번호": "Part_No",
        "Assy": "Assy_PN", "Assy PN": "Assy_PN", "모품번": "Assy_PN", "상위품번": "Assy_PN",
        "품명/규격": "품명", "규격": "품명", "Item": "품명",
        "제조원": "제조사", "Maker": "제조사", "Vendor": "제조사",
        "useage": "Usage", "USAGE": "Usage", "소요량": "Usage", "단위소요량": "Usage",
        "Loss": "로스율(%)", "로스율": "로스율(%)", "Scrap": "로스율(%)"
    }
    df_bom = df_bom.rename(columns=col_map)
    
    if "로스율(%)" not in df_bom.columns:
        df_bom["로스율(%)"] = 0.0
    if "제조사" not in df_bom.columns:
        df_bom["제조사"] = "-"
    if "품명" not in df_bom.columns:
        df_bom["품명"] = df_bom["Part_No"]

    df_bom["Usage"] = pd.to_numeric(df_bom["Usage"], errors="coerce").fillna(0)
    df_bom["로스율(%)"] = pd.to_numeric(df_bom["로스율(%)"], errors="coerce").fillna(0)

    # 생산 계획 Unpivot (Assy_PN, Month, Plan_Qty)
    plan_melted = pd.melt(
        edited_plan,
        id_vars=["Assy_PN"],
        value_vars=[c for c in edited_plan.columns if c != "Assy_PN"],
        var_name="Month",
        value_name="Plan_Qty"
    )
    plan_melted["Plan_Qty"] = pd.to_numeric(plan_melted["Plan_Qty"], errors="coerce").fillna(0)

    # 매핑: 생산계획 + BOM
    merged = pd.merge(plan_melted, df_bom, on="Assy_PN", how="inner")
    
    # 필요 수량 계산식 = Plan_Qty * Usage * (1 + Loss/100)
    merged["필요수량_산출"] = merged["Plan_Qty"] * merged["Usage"] * (1 + (merged["로스율(%)"] / 100.0))

    # --- 5. 분석 기준 선택 (월별 or 연간 종합) ---
    st.markdown("---")
    st.subheader("3. 하위 자재 소요 결과 분석")
    
    all_months = [c for c in edited_plan.columns if c != "Assy_PN"]
    select_opts = ["연간 전체 합계"] + all_months
    
    target_period = st.radio("집계 기준 선택", select_opts, horizontal=True)

    if target_period == "연간 전체 합계":
        active_df = merged.copy()
    else:
        active_df = merged[merged["Month"] == target_period].copy()

    # 부품별 집계 (Part_No 기준)
    summary = active_df.groupby("Part_No").agg(
        품명=("품명", "first"),
        제조사=("제조사", "first"),
        적용Assy_수=("Assy_PN", "nunique"),
        적용Assy_목록=("Assy_PN", lambda x: ", ".join(sorted(set(x)))),
        총_필요수량=("필요수량_산출", "sum")
    ).reset_index()

    summary["총_필요수량"] = summary["총_필요수량"].apply(np.ceil).astype(int)
    summary["구분"] = summary["적용Assy_수"].apply(lambda x: "🟢 공용 부품" if x > 1 else "⚪ 전용 부품")

    # 요약 메트릭
    col_m1, col_m2, col_m3 = st.columns(3)
    col_m1.metric("선택 주기", target_period)
    col_m2.metric("총 투입 소자 품번 수", f"{len(summary):,} 종")
    col_m3.metric("총 필요 소요 수량", f"{summary['총_필요수량'].sum():,} EA")

    # 결과 테이블 (Part No, 품명, 제조사, 필요 수량 중심)
    display_cols = ["Part_No", "품명", "제조사", "구분", "적용Assy_목록", "총_필요수량"]
    st.dataframe(
        summary[display_cols].rename(columns={
            "Part_No": "Part No",
            "총_필요수량": f"필요 수량 ({target_period})",
            "적용Assy_목록": "적용 PCB Assy"
        }).sort_values(by=f"필요 수량 ({target_period})", ascending=False),
        use_container_width=True,
        hide_index=True
    )

    # --- 6. 전체 1~12월 월별 전개 피벗 매트릭스 ---
    with st.expander("📅 [전체 월별 소요량 매트릭스 펼치기] Part No별 1월~12월 필요수량 추이"):
        monthly_matrix = pd.pivot_table(
            merged,
            index=["Part_No", "품명", "제조사"],
            columns="Month",
            values="필요수량_산출",
            aggfunc="sum",
            fill_value=0
        ).round(0).astype(int).reset_index()
        st.dataframe(monthly_matrix, use_container_width=True)

    # --- 7. 엑셀 다운로드 ---
    out_buf = io.BytesIO()
    with pd.ExcelWriter(out_buf, engine="openpyxl") as writer:
        summary.to_excel(writer, sheet_name="요약_소요량", index=False)
        monthly_matrix.to_excel(writer, sheet_name="월별_상세매트릭스", index=False)
        edited_plan.to_excel(writer, sheet_name="적용_생산계획", index=False)
    
    st.download_button(
        label="📥 결과 엑셀 다운로드 (요약 및 월별 매트릭스)",
        data=out_buf.getvalue(),
        file_name=f"PCB_자재소요량_{target_period}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
