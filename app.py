import io
import numpy as np
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="PCB Assy 자재 소요량 트래커",
    page_icon="📊",
    layout="wide",
)

st.title("📊 PCB Assembly 하위 자재 소요량 & 구매금액 트래커")
st.caption(
    "효성전기 양산 모터 PCB Assy 자재 집계 | BOM 붙여넣기/업로드 ➔ 수기 생산계획 or 엑셀 업로드 연동"
)

# --- 1. 기본 생산 계획 템플릿 세션 관리 ---
if "plan_mode" not in st.session_state:
    st.session_state.plan_mode = "연도별 중장기 (2026~2030+)"

# 기본 생산 계획 데이터프레임 초기화
DEFAULT_ASSYS = ["THS0143301", "E0280014C01"]

if "manual_yearly_plan" not in st.session_state:
    st.session_state.manual_yearly_plan = pd.DataFrame({
        "ASSY PART NO": DEFAULT_ASSYS,
        "2026년": [120000, 150000],
        "2027년": [150000, 180000],
        "2028년": [165000, 190000],
        "2029년": [170000, 200000],
        "2030년": [175000, 210000],
    })

if "manual_monthly_plan" not in st.session_state:
    months = [f"{m}월" for m in range(1, 13)]
    init_data = {"ASSY PART NO": DEFAULT_ASSYS}
    for m in months:
        init_data[m] = [12500, 15000]
    st.session_state.manual_monthly_plan = pd.DataFrame(init_data)

# --- 2. 영역 1: BOM 입력 (붙여넣기 or 엑셀 업로드) ---
st.subheader("1. PCB Assy 하위 BOM 입력")

tab_bom_paste, tab_bom_file = st.tabs(["📋 BOM 텍스트 붙여넣기", "📂 BOM 엑셀 업로드 (.xlsx)"])
raw_df_bom = None

with tab_bom_paste:
    sample_text = (
        "PART NO\tPART NAME\tPart Number\tmanufacturer part no.\tManufacturer\tper unit\t통화\tprice\t원화\n"
        "THS0143301\tMX5 PCB\tE0401-149-00\tHBY331M1ETR-1010KEGA\tLelon\t4\tUSD\t0.24000\t348.84\n"
        "THS0143301\tMX5 PCB\tE0405-009-00\t06031C103K4Z4A\tAVX\t4\tUSD\t0.00650\t9.45\n"
        "THS0143301\tMX5 PCB\tE0405-125-00\tGCJ21BR72A104KA01L\tMURATA\t6\tJPY\t1.55000\t14.58\n"
        "THS0143301\tMX5 PCB\tE0405-135-00\t06035C332K4T2A\tAVX\t6\tUSD\t0.00540\t7.85\n"
        "THS0143301\tMX5 PCB\tE0405-271-00\tC0402C104K4RACAUTO\tKEMET\t2\tUSD\t0.00650\t9.45"
    )
    bom_input_text = st.text_area(
        "엑셀에서 복사한 BOM을 그대로 붙여넣으세요 (제목 행 포함)",
        value=sample_text,
        height=180,
    )
    if bom_input_text.strip():
        try:
            raw_df_bom = pd.read_csv(io.StringIO(bom_input_text), sep=r"\t", engine="python")
        except Exception:
            raw_df_bom = pd.read_csv(io.StringIO(bom_input_text), sep=r"\s+", engine="python")

with tab_bom_file:
    bom_file = st.file_uploader("BOM 엑셀 파일 (.xlsx)", type=["xlsx"], key="bom_file_up")
    if bom_file:
        try:
            raw_df_bom = pd.read_excel(bom_file)
        except Exception as e:
            st.error(f"엑셀 로드 실패: {e}")

# --- 3. BOM 컬럼 자동 매핑 ---
df_bom = None
detected_assys = []

if raw_df_bom is not None and not raw_df_bom.empty:
    df_bom = raw_df_bom.copy()
    df_bom.columns = [str(c).strip() for c in df_bom.columns]

    # 실무 컬럼 매핑 사전
    bom_col_map = {
        "PART NO": "ASSY PART NO", "PART_NO": "ASSY PART NO", "ASSY_PN": "ASSY PART NO", "모품번": "ASSY PART NO",
        "PART NAME": "ASSY PART NAME", "PART_NAME": "ASSY PART NAME", "모품명": "ASSY PART NAME",
        "Part Number": "PART NUMBER", "part number": "PART NUMBER", "자재번호": "PART NUMBER", "하위품번": "PART NUMBER",
        "manufacturer part no.": "제조사 PART NO", "manufacturer part no": "제조사 PART NO", "MPN": "제조사 PART NO", "규격": "제조사 PART NO",
        "Manufacturer": "제조사", "MANUFACTURER": "제조사", "제조원": "제조사", "Vendor": "제조사",
        "per unit": "소요량", "per_unit": "소요량", "usage": "소요량", "Usage": "소요량", "소요량": "소요량",
        "price": "단가", "단가": "단가", "단가(외화)": "단가",
        "원화": "원화단가", "원화단가": "원화단가", "KRW": "원화단가"
    }

    for col in list(df_bom.columns):
        if col in bom_col_map:
            df_bom.rename(columns={col: bom_col_map[col]}, inplace=True)
        elif col.lower() in [k.lower() for k in bom_col_map.keys()]:
            for k, v in bom_col_map.items():
                if col.lower() == k.lower():
                    df_bom.rename(columns={col: v}, inplace=True)
                    break

    # 기본값 보정
    if "소요량" in df_bom.columns:
        df_bom["소요량"] = pd.to_numeric(df_bom["소요량"], errors="coerce").fillna(1.0)
    else:
        df_bom["소요량"] = 1.0

    if "단가" in df_bom.columns:
        df_bom["단가"] = pd.to_numeric(df_bom["단가"], errors="coerce").fillna(0.0)
    else:
        df_bom["단가"] = 0.0

    if "원화단가" in df_bom.columns:
        df_bom["원화단가"] = pd.to_numeric(df_bom["원화단가"], errors="coerce").fillna(df_bom["단가"])
    else:
        df_bom["원화단가"] = df_bom["단가"]

    if "통화" not in df_bom.columns:
        df_bom["통화"] = "KRW"
    if "제조사" not in df_bom.columns:
        df_bom["제조사"] = "-"
    if "제조사 PART NO" not in df_bom.columns:
        df_bom["제조사 PART NO"] = df_bom.get("PART NUMBER", "-")
    if "ASSY PART NAME" not in df_bom.columns:
        df_bom["ASSY PART NAME"] = df_bom.get("ASSY PART NO", "-")

    detected_assys = sorted(df_bom["ASSY PART NO"].dropna().astype(str).unique().tolist())

# --- 4. 영역 2: 생산계획 (수기 편집 표 vs 엑셀 업로드) ---
st.markdown("---")
st.subheader("2. 생산 계획 관리 (수기 입력 또는 엑셀 업로드)")

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
        # BOM에 새로운 Assy가 감지되면 자동으로 행 추가
        curr_df = st.session_state.manual_yearly_plan.copy()
        if detected_assys:
            for assy in detected_assys:
                if assy not in curr_df["ASSY PART NO"].values:
                    new_row = {col: 0 for col in curr_df.columns}
                    new_row["ASSY PART NO"] = assy
                    curr_df = pd.concat([curr_df, pd.DataFrame([new_row])], ignore_index=True)

        st.caption("💡 각 연도별 수량을 엑셀처럼 더블 클릭하여 바로 수정할 수 있습니다.")
        edited_plan = st.data_editor(
            curr_df,
            num_rows="dynamic",
            use_container_width=True,
            key="editor_yearly",
        )
        st.session_state.manual_yearly_plan = edited_plan

        # Unpivot 변환
        plan_unpivoted = pd.melt(
            edited_plan,
            id_vars=["ASSY PART NO"],
            value_vars=[c for c in edited_plan.columns if c != "ASSY PART NO"],
            var_name="Period",
            value_name="Plan_Qty"
        )

    else:
        curr_df = st.session_state.manual_monthly_plan.copy()
        if detected_assys:
            for assy in detected_assys:
                if assy not in curr_df["ASSY PART NO"].values:
                    new_row = {col: 0 for col in curr_df.columns}
                    new_row["ASSY PART NO"] = assy
                    curr_df = pd.concat([curr_df, pd.DataFrame([new_row])], ignore_index=True)

        st.caption("💡 1월~12월 수량을 엑셀처럼 직접 수정할 수 있습니다.")
        edited_plan = st.data_editor(
            curr_df,
            num_rows="dynamic",
            use_container_width=True,
            key="editor_monthly",
        )
        st.session_state.manual_monthly_plan = edited_plan

        plan_unpivoted = pd.melt(
            edited_plan,
            id_vars=["ASSY PART NO"],
            value_vars=[c for c in edited_plan.columns if c != "ASSY PART NO"],
            var_name="Period",
            value_name="Plan_Qty"
        )

else:
    plan_file = st.file_uploader(
        "생산계획 엑셀 파일 업로드 (.xlsx)", type=["xlsx"], key="plan_file_up"
    )
    if plan_file:
        try:
            excel_p = pd.read_excel(plan_file)
            excel_p.columns = [str(c).strip() for c in excel_p.columns]
            # 만약 첫 번째 열이 품번이고 나머지가 연도/월인 경우 자동 Unpivot
            first_col = excel_p.columns[0]
            excel_p.rename(columns={first_col: "ASSY PART NO"}, inplace=True)
            plan_unpivoted = pd.melt(
                excel_p,
                id_vars=["ASSY PART NO"],
                value_vars=[c for c in excel_p.columns if c != "ASSY PART NO"],
                var_name="Period",
                value_name="Plan_Qty"
            )
            st.success("생산계획 엑셀이 정상적으로 로드되었습니다.")
        except Exception as e:
            st.error(f"생산계획 파일 처리 오류: {e}")

# --- 5. 연산 및 최종 분석 출력 ---
if df_bom is not None and plan_unpivoted is not None and not plan_unpivoted.empty:
    plan_unpivoted["Plan_Qty"] = pd.to_numeric(plan_unpivoted["Plan_Qty"], errors="coerce").fillna(0)
    
    # 조인 (BOM + 생산계획)
    merged = pd.merge(plan_unpivoted, df_bom, on="ASSY PART NO", how="inner")
    
    if merged.empty:
        st.warning("⚠️ 입력된 생산계획의 'ASSY PART NO'와 BOM의 'ASSY PART NO'가 일치하는 품목이 없습니다.")
    else:
        # 필요수량 및 금액 계산
        merged["필요수량"] = merged["Plan_Qty"] * merged["소요량"]
        merged["외화_총금액"] = merged["필요수량"] * merged["단가"]
        merged["원화_총금액"] = merged["필요수량"] * merged["원화단가"]

        st.markdown("---")
        st.subheader("3. 하위 자재 소요 결과 분석")

        # 드롭다운 필터
        periods = sorted(merged["Period"].unique().tolist())
        col_f1, col_f2 = st.columns([2, 4])
        with col_f1:
            sel_period = st.selectbox("📅 분석 대상 주기 선택 (드롭다운)", periods)
        with col_f2:
            view_opt = st.radio("보기 모드", ["소자(Part Number)별 공용품 집계", "상위 Assy별 상세 전개"], horizontal=True)

        curr_view = merged[merged["Period"] == sel_period].copy()

        # 상단 요약 메트릭
        col_m1, col_m2, col_m3, col_m4 = st.columns(4)
        col_m1.metric("선택 주기", sel_period)
        col_m2.metric("투입 소자 품목 수", f"{curr_view['PART NUMBER'].nunique():,} 종")
        col_m3.metric("총 필요 소요 수량", f"{int(curr_view['필요수량'].sum()):,} EA")
        col_m4.metric("원화 환산 총 금액", f"{int(curr_view['원화_총금액'].sum()):,} 원")

        # 테이블 열 구성
        if view_opt == "소자(Part Number)별 공용품 집계":
            summary = curr_view.groupby("PART NUMBER").agg(
                ASSY_PART_NO=("ASSY PART NO", lambda x: ", ".join(sorted(set(str(v) for v in x)))),
                ASSY_PART_NAME=("ASSY PART NAME", lambda x: ", ".join(sorted(set(str(v) for v in x)))),
                제조사_PART_NO=("제조사 PART NO", "first"),
                제조사=("제조사", "first"),
                소요량=("소요량", "sum"),
                필요수량=("필요수량", "sum"),
                통화=("통화", "first"),
                단가=("단가", "first"),
                원화단가=("원화단가", "first"),
                원화_총금액=("원화_총금액", "sum"),
                적용모델수=("ASSY PART NO", "nunique")
            ).reset_index()

            summary["구분"] = summary["적용모델수"].apply(lambda x: "🟢 공용 부품" if x > 1 else "⚪ 전용 부품")
            summary["필요수량"] = summary["필요수량"].apply(np.ceil).astype(int)
            summary["원화_총금액"] = summary["원화_총금액"].apply(np.ceil).astype(int)

            final_cols = [
                "ASSY_PART_NO", "ASSY_PART_NAME", "PART NUMBER", "제조사_PART_NO",
                "제조사", "구분", "소요량", "필요수량", "통화", "단가", "원화단가", "원화_총금액"
            ]
            display_df = summary[final_cols].rename(columns={
                "ASSY_PART_NO": "ASSY PART NO",
                "ASSY_PART_NAME": "ASSY PART NAME",
                "제조사_PART_NO": "제조사 PART NO",
                "필요수량": f"필요 수량 ({sel_period})",
                "원화_총금액": "총 소요금액 (원화)"
            }).sort_values(by=f"필요 수량 ({sel_period})", ascending=False)

        else:
            final_cols = [
                "ASSY PART NO", "ASSY PART NAME", "PART NUMBER", "제조사 PART NO",
                "제조사", "소요량", "필요수량", "통화", "단가", "원화단가", "원화_총금액"
            ]
            curr_view["필요수량"] = curr_view["필요수량"].apply(np.ceil).astype(int)
            curr_view["원화_총금액"] = curr_view["원화_총금액"].apply(np.ceil).astype(int)
            display_df = curr_view[final_cols].rename(columns={
                "필요수량": f"필요 수량 ({sel_period})",
                "원화_총금액": "총 소요금액 (원화)"
            }).sort_values(by=f"필요 수량 ({sel_period})", ascending=False)

        st.dataframe(display_df, use_container_width=True, hide_index=True)

        # 전체 주기 가로 매트릭스 (2026~2030 or 1~12월 추이)
        with st.expander("📈 [전체 주기별 소요량 매트릭스] Part Number별 추이 펼쳐보기"):
            pivot_matrix = pd.pivot_table(
                merged,
                index=["PART NUMBER", "제조사 PART NO", "제조사", "통화", "원화단가"],
                columns="Period",
                values="필요수량",
                aggfunc="sum",
                fill_value=0
            ).round(0).astype(int).reset_index()
            st.dataframe(pivot_matrix, use_container_width=True)

        # 엑셀 다운로드
        out_buf = io.BytesIO()
        with pd.ExcelWriter(out_buf, engine="openpyxl") as writer:
            display_df.to_excel(writer, sheet_name=f"요약_{sel_period}", index=False)
            pivot_matrix.to_excel(writer, sheet_name="주기별_전체매트릭스", index=False)

        st.download_button(
            label=f"📥 [{sel_period}] 결과 엑셀 다운로드",
            data=out_buf.getvalue(),
            file_name=f"PCB_하위자재_소요량_{sel_period}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
