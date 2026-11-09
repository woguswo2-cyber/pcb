import io
import numpy as np
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="PCB Assy 자재 소요량 트래커", page_icon="📊", layout="wide"
)

st.title("📊 PCB Assembly 하위 자재 월별 소요량 트래커")
st.caption("Assy별 월 생산계획 및 단위 Usage 기반 하위 소자 종합 소요량 집계")

# --- 1. 기본 생산 계획 셋업 ---
DEFAULT_ASSYS = ["B100-PCB", "EPS-65A-PCB", "L-VENT-PCB"]
MONTHS = [f"{m}월" for m in range(1, 13)]

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

SAMPLE_BOM = """Assy_PN\tPart_No\t품명\t제조사\tUsage\t로스율(%)
B100-PCB\tBB-4L-001\tBare Board 4L\t제이앤디\t1\t0
B100-PCB\tCAP-100N-0603\tMLCC 100nF 0603\tMurata\t8\t1.0
B100-PCB\tRES-SH-001\tShunt 저항 1mR\tVishay\t1\t0.5
B100-PCB\tFET-40V-100A\tPower MOSFET\tInfineon\t6\t0.5
B100-PCB\tCON-4P\tHeader Conn 4P\tMolex\t1\t0
EPS-65A-PCB\tBB-6L-002\tBare Board 6L\tKCE\t1\t0
EPS-65A-PCB\tCAP-100N-0603\tMLCC 100nF 0603\tMurata\t14\t1.0
EPS-65A-PCB\tRES-SH-001\tShunt 저항 1mR\tVishay\t3\t0.5
EPS-65A-PCB\tFET-40V-100A\tPower MOSFET\tInfineon\t6\t0.5
EPS-65A-PCB\tMCU-32B\t32bit MCU\tNXP\t1\t0
L-VENT-PCB\tBB-2L-003\tBare Board 2L\tUSI\t1\t0
L-VENT-PCB\tCAP-100N-0603\tMLCC 100nF 0603\tMurata\t4\t1.0
L-VENT-PCB\tRES-SH-001\tShunt 저항 1mR\tVishay\t1\t0.5"""

# --- 2. 상단: 월별 생산 계획 에디터 ---
st.subheader("1. 상위 PCB Assy 월별 생산 계획 (수량 직접 수정 가능)")
st.caption("표 안의 셀을 더블 클릭해 직접 수량을 변경하거나 새로운 Assy 품목을 추가할 수 있습니다.")

edited_plan = st.data_editor(
    st.session_state.prod_plan,
    num_rows="dynamic",
    use_container_width=True,
    key="plan_editor",
)

# --- 3. 중단: 하위 BOM 입력 ---
st.markdown("---")
st.subheader("2. PCB Assy별 하위 자재(BOM) 목록 입력")

tab_paste, tab_upload = st.tabs(["📋 엑셀 복사/붙여넣기", "📁 엑셀 파일 업로드"])
raw_df_bom = None

with tab_paste:
    st.markdown(
        "**[권장 헤더 순서]**: `Assy_PN` | `Part_No` | `품명` | `제조사` | `Usage` | `로스율(%)`"
    )
    bom_raw = st.text_area(
        "BOM 텍스트 붙여넣기 (맨 첫 줄에 컬럼명을 포함해 주세요)",
        value=SAMPLE_BOM,
        height=180,
    )
    if bom_raw.strip():
        try:
            # 공백/탭 구분자 유연 처리
            raw_df_bom = pd.read_csv(io.StringIO(bom_raw), sep=r"\s+|\t", engine="python")
        except Exception as e:
            st.error(f"데이터 파싱 에러: {e}")

with tab_upload:
    uploaded = st.file_uploader("BOM 엑셀 파일(.xlsx) 선택", type=["xlsx"])
    if uploaded is not None:
        try:
            raw_df_bom = pd.read_excel(uploaded)
        except Exception as e:
            st.error(f"엑셀 파일 로드 실패: {e}")

# --- 4. 데이터 정제 및 스마트 컬럼 매핑 (KeyError 완전 방어) ---
if raw_df_bom is not None and not raw_df_bom.empty and edited_plan is not None:
    df_bom = raw_df_bom.copy()
    df_bom.columns = [str(c).strip() for c in df_bom.columns]

    # 표준 컬럼 매핑 사전
    synonyms = {
        "Assy_PN": ["assy_pn", "assy", "assypn", "모품번", "상위품목", "상위품번", "완제품", "모모델"],
        "Part_No": ["part_no", "partno", "part_pn", "partpn", "자재번호", "부품번호", "소자품번", "하위품번", "품번"],
        "품명": ["품명", "품명/규격", "규격", "item", "description", "part_name", "소자명"],
        "제조사": ["제조사", "제조원", "maker", "vendor", "공급사", "업체명", "maker명"],
        "Usage": ["usage", "useage", "소요량", "단위소요량", "qty", "수량", "q'ty"],
        "로스율(%)": ["로스율(%)", "로스율", "loss", "loss_rate", "loss(%)", "불량률", "scrap"]
    }

    matched_cols = {}
    for standard_col, syn_list in synonyms.items():
        for col in df_bom.columns:
            if col.lower() in syn_list or col in syn_list:
                matched_cols[col] = standard_col
                break

    df_bom = df_bom.rename(columns=matched_cols)

    # 헤더가 누락되어 컬럼 매핑이 안 된 경우 (위치 기반 Fallback 매핑)
    if "Part_No" not in df_bom.columns:
        if len(df_bom.columns) >= 3:
            st.warning("⚠️ 컬럼명이 감지되지 않아 입력 순서대로 [Assy_PN, Part_No, 품명...] 으로 자동 할당했습니다. 정확한 분석을 위해 엑셀의 첫 줄(제목 행)을 함께 복사해 주세요.")
            col_order = ["Assy_PN", "Part_No", "품명", "제조사", "Usage", "로스율(%)"]
            for idx, cname in enumerate(col_order[:len(df_bom.columns)]):
                df_bom.rename(columns={df_bom.columns[idx]: cname}, inplace=True)
        else:
            st.error("입력된 데이터의 열(Column) 수가 부족합니다. [상위Assy, Part_No, 품명, Usage] 순으로 최소 3개 이상의 열이 필요합니다.")
            st.stop()

    # 필수 컬럼 기본값 처리
    if "Assy_PN" not in df_bom.columns:
        df_bom["Assy_PN"] = DEFAULT_ASSYS[0]
    if "품명" not in df_bom.columns:
        df_bom["품명"] = df_bom["Part_No"]
    if "제조사" not in df_bom.columns:
        df_bom["제조사"] = "-"
    if "Usage" not in df_bom.columns:
        df_bom["Usage"] = 1.0
    if "로스율(%)" not in df_bom.columns:
        df_bom["로스율(%)"] = 0.0

    df_bom["Usage"] = pd.to_numeric(df_bom["Usage"], errors="coerce").fillna(1.0)
    df_bom["로스율(%)"] = pd.to_numeric(df_bom["로스율(%)"], errors="coerce").fillna(0.0)

    # 생산계획 테이블 Melt
    plan_cols = [c for c in edited_plan.columns if c != "Assy_PN"]
    plan_melted = pd.melt(
        edited_plan,
        id_vars=["Assy_PN"],
        value_vars=plan_cols,
        var_name="Month",
        value_name="Plan_Qty"
    )
    plan_melted["Plan_Qty"] = pd.to_numeric(plan_melted["Plan_Qty"], errors="coerce").fillna(0)

    # 병합 및 계산
    merged = pd.merge(plan_melted, df_bom, on="Assy_PN", how="inner")

    if merged.empty:
        st.warning(f"생산 계획의 Assy_PN {edited_plan['Assy_PN'].unique().tolist()} 과 BOM의 Assy_PN {df_bom['Assy_PN'].unique().tolist()} 일치하는 품목이 없습니다. 품번을 일치시켜 주십시오.")
    else:
        merged["필요수량_산출"] = merged["Plan_Qty"] * merged["Usage"] * (1 + (merged["로스율(%)"] / 100.0))

        # --- 5. 결과 집계 렌더링 ---
        st.markdown("---")
        st.subheader("3. 하위 자재 소요 결과 분석")

        select_opts = ["연간 전체 합계"] + plan_cols
        target_period = st.radio("집계 기준 선택", select_opts, horizontal=True)

        if target_period == "연간 전체 합계":
            active_df = merged.copy()
        else:
            active_df = merged[merged["Month"] == target_period].copy()

        summary = active_df.groupby("Part_No").agg(
            품명=("품명", "first"),
            제조사=("제조사", "first"),
            적용Assy_수=("Assy_PN", "nunique"),
            적용Assy_목록=("Assy_PN", lambda x: ", ".join(sorted(set(str(v) for v in x)))),
            총_필요수량=("필요수량_산출", "sum")
        ).reset_index()

        summary["총_필요수량"] = summary["총_필요수량"].apply(np.ceil).astype(int)
        summary["구분"] = summary["적용Assy_수"].apply(lambda x: "🟢 공용 부품" if x > 1 else "⚪ 전용 부품")

        # 메트릭 카드
        col_m1, col_m2, col_m3 = st.columns(3)
        col_m1.metric("선택 주기", target_period)
        col_m2.metric("총 투입 소자 품번 수", f"{len(summary):,} 종")
        col_m3.metric("총 필요 소요 수량", f"{summary['총_필요수량'].sum():,} EA")

        # 결과 테이블
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

        # 전체 월별 매트릭스
        with st.expander("📅 [전체 월별 소요량 매트릭스 펼치기] Part No별 월별 필요수량 추이"):
            monthly_matrix = pd.pivot_table(
                merged,
                index=["Part_No", "품명", "제조사"],
                columns="Month",
                values="필요수량_산출",
                aggfunc="sum",
                fill_value=0
            ).round(0).astype(int).reset_index()
            st.dataframe(monthly_matrix, use_container_width=True)

        # 엑셀 다운로드
        out_buf = io.BytesIO()
        with pd.ExcelWriter(out_buf, engine="openpyxl") as writer:
            summary.to_excel(writer, sheet_name="요약_소요량", index=False)
            monthly_matrix.to_excel(writer, sheet_name="월별_상세매트릭스", index=False)
            edited_plan.to_excel(writer, sheet_name="적용_생산계획", index=False)

        st.download_button(
            label="📥 결과 엑셀 다운로드",
            data=out_buf.getvalue(),
            file_name=f"PCB_자재소요량_{target_period}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
