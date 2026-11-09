import io
import numpy as np
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="PCB Assy BOM & 중장기 소요량 트래커",
    page_icon="📊",
    layout="wide",
)

st.title("📊 PCB Assembly 하위 자재 소요량 & 구매금액 트래커")
st.caption(
    "2025~2030+ 중장기 사업계획 연동 | 단가·통화 기반 소요금액 및 공용 소자 자동 산출"
)

# --- 1. 기본 샘플 데이터 (초기 로딩 및 템플릿용) ---
SAMPLE_BOM = """ASSY PART NO\tASSY PART NAME\tPART NUMBER\t제조사 PART NO\t제조사\t소요량\t통화\t단가
E0280014C01\tBlower Control Board\tE0424-847-00\tAC0402FR-07100KL\tYAGEO\t8\tKRW\t2.5
E0280014C01\tBlower Control Board\tF0483-185-00\tIPC100N04S5-2R8\tINFINEON\t6\tUSD\t0.38
E0280014C01\tBlower Control Board\tE0405-321-00\tGCM155R71H102KA37J\tMURATA\t10\tKRW\t5.2
E0280014C01\tBlower Control Board\tE0401-143-00\t25ZLK390MHKST810x12.5\tRUBYCON\t2\tKRW\t45.0
THS0143301\tEPS 65A Controller\tE0424-847-00\tAC0402FR-07100KL\tYAGEO\t12\tKRW\t2.5
THS0143301\tEPS 65A Controller\tF0483-185-00\tIPC100N04S5-2R8\tINFINEON\t6\tUSD\t0.38
THS0143301\tEPS 65A Controller\tE0405-321-00\tGCM155R71H102KA37J\tMURATA\t14\tKRW\t5.2
THS0143301\tEPS 65A Controller\tE0405-111-00\t06035C104K4Z2A\tAVX\t5\tKRW\t6.8"""

SAMPLE_PLAN = """Year\tPeriod\tASSY PART NO\tPlan_Qty
2026\t연간 전체\tE0280014C01\t120000
2026\t연간 전체\tTHS0143301\t95000
2027\t연간 전체\tE0280014C01\t150000
2027\t연간 전체\tTHS0143301\t120000
2027\t1월\tE0280014C01\t12500
2027\t1월\tTHS0143301\t10000
2027\t2월\tE0280014C01\t13000
2027\t2월\tTHS0143301\t10500
2028\t연간 전체\tE0280014C01\t165000
2028\t연간 전체\tTHS0143301\t135000
2029\t연간 전체\tE0280014C01\t170000
2029\t연간 전체\tTHS0143301\t140000
2030\t연간 전체\tE0280014C01\t175000
2030\t연간 전체\tTHS0143301\t145000"""

# --- 2. 사이드바: 입력 모드 선택 (엑셀 업로드 vs 복사 붙여넣기) ---
st.sidebar.header("📁 데이터 업로드 설정")
input_mode = st.sidebar.radio(
    "데이터 입력 방식",
    ["📋 텍스트 복사/붙여넣기 (현재)", "📂 엑셀 파일 업로드 (.xlsx)"],
)

raw_df_bom = None
raw_df_plan = None

if input_mode == "📂 엑셀 파일 업로드 (.xlsx)":
    uploaded_file = st.sidebar.file_uploader(
        "BOM 및 중장기 계획 엑셀 파일", type=["xlsx"]
    )
    if uploaded_file:
        try:
            excel = pd.ExcelFile(uploaded_file)
            sheet_names = excel.sheet_names
            s_bom = st.sidebar.selectbox("1. BOM 시트", sheet_names, index=0)
            s_plan = st.sidebar.selectbox(
                "2. 생산계획 시트",
                sheet_names,
                index=1 if len(sheet_names) > 1 else 0,
            )
            raw_df_bom = pd.read_excel(uploaded_file, sheet_name=s_bom)
            raw_df_plan = pd.read_excel(uploaded_file, sheet_name=s_plan)
        except Exception as e:
            st.sidebar.error(f"엑셀 로드 에러: {e}")
else:
    st.sidebar.info("기본 샘플 또는 엑셀 복사 붙여넣기 모드입니다.")
    col_t1, col_t2 = st.columns(2)
    with col_t1:
        bom_txt = st.text_area(
            "1. BOM 붙여넣기 (ASSY PART NO, PART NUMBER, 단가 등)",
            value=SAMPLE_BOM,
            height=160,
        )
    with col_t2:
        plan_txt = st.text_area(
            "2. 생산계획 붙여넣기 (Year, Period, ASSY PART NO, Plan_Qty)",
            value=SAMPLE_PLAN,
            height=160,
        )

    if bom_txt.strip() and plan_txt.strip():
        try:
            raw_df_bom = pd.read_csv(io.StringIO(bom_txt), sep=r"\s+|\t", engine="python")
            raw_df_plan = pd.read_csv(io.StringIO(plan_txt), sep=r"\s+|\t", engine="python")
        except Exception as e:
            st.error(f"파싱 에러: {e}")

# --- 3. 데이터 표준화 및 파이프라인 ---
if raw_df_bom is not None and raw_df_plan is not None:
    df_bom = raw_df_bom.copy()
    df_plan = raw_df_plan.copy()

    # 컬럼 공백 제거
    df_bom.columns = [str(c).strip() for c in df_bom.columns]
    df_plan.columns = [str(c).strip() for c in df_plan.columns]

    # BOM 컬럼 매핑 유연화
    bom_aliases = {
        "ASSY PART NO": ["assy_pn", "assy part no", "assy partno", "모품번", "상위품번", "assy"],
        "ASSY PART NAME": ["assy part name", "assy name", "모품명", "상위품명"],
        "PART NUMBER": ["part number", "part no", "part_no", "자재번호", "품번"],
        "제조사 PART NO": ["제조사 part no", "제조사partno", "maker part no", "mpn", "품명", "규격"],
        "제조사": ["제조사", "maker", "vendor", "공급사", "업체명"],
        "소요량": ["소요량", "usage", "useage", "qty"],
        "통화": ["통화", "currency", "curr"],
        "단가": ["단가", "price", "unit price", "단가(원)"]
    }
    
    # 별칭 적용
    for std_name, alias_list in bom_aliases.items():
        for col in df_bom.columns:
            if col.lower() in alias_list or col == std_name:
                df_bom.rename(columns={col: std_name}, inplace=True)
                break

    # 생산계획 컬럼 매핑 유연화
    plan_aliases = {
        "Year": ["year", "연도", "년도"],
        "Period": ["period", "구분", "주기", "월"],
        "ASSY PART NO": ["assy part no", "assy_pn", "assy partno", "모품번", "상위품번", "assy"],
        "Plan_Qty": ["plan_qty", "plan qty", "수량", "생산계획", "계획수량", "물량"]
    }
    for std_name, alias_list in plan_aliases.items():
        for col in df_plan.columns:
            if col.lower() in alias_list or col == std_name:
                df_plan.rename(columns={col: std_name}, inplace=True)
                break

    # 누락 컬럼 기본값 보정
    if "ASSY PART NAME" not in df_bom.columns:
        df_bom["ASSY PART NAME"] = df_bom["ASSY PART NO"]
    if "제조사 PART NO" not in df_bom.columns:
        df_bom["제조사 PART NO"] = df_bom["PART NUMBER"]
    if "제조사" not in df_bom.columns:
        df_bom["제조사"] = "-"
    if "통화" not in df_bom.columns:
        df_bom["통화"] = "KRW"
    if "단가" not in df_bom.columns:
        df_bom["단가"] = 0.0
    if "Period" not in df_plan.columns:
        df_plan["Period"] = "연간 전체"

    # 수치형 변환
    df_bom["소요량"] = pd.to_numeric(df_bom["소요량"], errors="coerce").fillna(1.0)
    df_bom["단가"] = pd.to_numeric(df_bom["단가"], errors="coerce").fillna(0.0)
    df_plan["Plan_Qty"] = pd.to_numeric(df_plan["Plan_Qty"], errors="coerce").fillna(0)
    df_plan["Year"] = df_plan["Year"].astype(str)

    # 머지 (계획 + BOM)
    merged = pd.merge(df_plan, df_bom, on="ASSY PART NO", how="inner")
    merged["필요수량"] = merged["Plan_Qty"] * merged["소요량"]
    merged["총금액"] = merged["필요수량"] * merged["단가"]

    # --- 4. 필터 드롭다운 (연도 및 세부 주기 선택) ---
    st.markdown("---")
    st.subheader("🔍 분석 대상 기간 선택 (연도 & 주기 드롭다운)")

    avail_years = sorted(list(df_plan["Year"].unique()))
    col_sel1, col_sel2, col_sel3 = st.columns([1.5, 2, 2.5])
    
    with col_sel1:
        sel_year = st.selectbox("📅 분석 연도 선택", avail_years, index=len(avail_years)-1 if len(avail_years)>1 else 0)
    
    # 해당 연도 내 존재하는 주기(월별/연간 전체) 필터
    year_periods = df_plan[df_plan["Year"] == sel_year]["Period"].unique().tolist()
    if "연간 전체" in year_periods:
        default_idx = year_periods.index("연간 전체")
    else:
        default_idx = 0

    with col_sel2:
        sel_period = st.selectbox(f"📆 [{sel_year}년] 세부 주기 선택", year_periods, index=default_idx)

    with col_sel3:
        view_type = st.radio("표시 대상", ["소자별 집계 (공용품 통합)", "상위 Assy별 전개 상세"], horizontal=True)

    # 필터링 데이터
    curr_view = merged[(merged["Year"] == sel_year) & (merged["Period"] == sel_period)]

    # --- 5. 핵심 지표 메트릭 ---
    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
    with col_m1:
        st.metric("선택 기준", f"{sel_year}년 {sel_period}")
    with col_m2:
        st.metric("총 투입 소자 품목 수", f"{curr_view['PART NUMBER'].nunique():,} 종")
    with col_m3:
        st.metric("총 필요 소요 수량", f"{int(curr_view['필요수량'].sum()):,} EA")
    with col_m4:
        # 주요 통화별 금액
        curr_sums = curr_view.groupby("통화")["총금액"].sum()
        curr_str = " / ".join([f"{k}: {v:,.0f}" if k=='KRW' else f"{k}: {v:,.2f}" for k, v in curr_sums.items()])
        st.metric("총 소요 금액", curr_str if curr_str else "0")

    # --- 6. 요청하신 열(Column) 순서 테이블 렌더링 ---
    st.subheader(f"📋 하위 자재 소요 및 단가 현황 ({sel_year}년 {sel_period})")

    if view_type == "상위 Assy별 전개 상세":
        # 요청하신 열 순서 그대로 전개
        req_cols = [
            "ASSY PART NO",
            "ASSY PART NAME",
            "PART NUMBER",
            "제조사 PART NO",
            "제조사",
            "소요량",
            "필요수량",
            "통화",
            "단가",
            "총금액"
        ]
        out_df = curr_view[req_cols].copy()
        out_df.rename(columns={
            "필요수량": "필요 수량 (Plan반영)",
            "총금액": "총 소요금액"
        }, inplace=True)
        st.dataframe(out_df, use_container_width=True, hide_index=True)

    else:
        # 소자(PART NUMBER) 기준 통합 집계 (공용 소자 묶음)
        agg_summary = curr_view.groupby("PART NUMBER").agg(
            ASSY_PART_NO=("ASSY PART NO", lambda x: ", ".join(sorted(set(str(v) for v in x)))),
            ASSY_PART_NAME=("ASSY PART NAME", lambda x: ", ".join(sorted(set(str(v) for v in x)))),
            제조사_PART_NO=("제조사 PART NO", "first"),
            제조사=("제조사", "first"),
            소요량_합=("소요량", "sum"),
            필요수량=("필요수량", "sum"),
            통화=("통화", "first"),
            단가=("단가", "first"),
            총금액=("총금액", "sum"),
            적용모델수=("ASSY PART NO", "nunique")
        ).reset_index()

        agg_summary["구분"] = agg_summary["적용모델수"].apply(lambda x: "🟢 공용 부품" if x > 1 else "⚪ 전용 부품")

        display_cols = [
            "ASSY_PART_NO",
            "ASSY_PART_NAME",
            "PART NUMBER",
            "제조사_PART_NO",
            "제조사",
            "구분",
            "필요수량",
            "통화",
            "단가",
            "총금액"
        ]
        out_df = agg_summary[display_cols].rename(columns={
            "ASSY_PART_NO": "ASSY PART NO",
            "ASSY_PART_NAME": "ASSY PART NAME",
            "제조사_PART_NO": "제조사 PART NO",
            "필요수량": "필요 수량 (Plan반영)",
            "총금액": "총 소요금액"
        }).sort_values(by="필요 수량 (Plan반영)", ascending=False)

        st.dataframe(out_df, use_container_width=True, hide_index=True)

    # --- 7. 중장기 연도별 추이 매트릭스 (2025~2030+) ---
    with st.expander("📈 [중장기 연도별 소요량 추이 (2025 ~ 2030+)] 한눈에 보기"):
        # 연간 전체 계획만 피벗
        yearly_plan = merged[merged["Period"] == "연간 전체"]
        if not yearly_plan.empty:
            yearly_matrix = pd.pivot_table(
                yearly_plan,
                index=["PART NUMBER", "제조사 PART NO", "제조사", "통화", "단가"],
                columns="Year",
                values="필요수량",
                aggfunc="sum",
                fill_value=0
            ).round(0).astype(int).reset_index()
            st.dataframe(yearly_matrix, use_container_width=True)
        else:
            st.info("생산계획의 Period에 '연간 전체'로 지정된 데이터가 있으면 여기에 연도별 추이 매트릭스가 나타납니다.")

    # --- 8. 엑셀 다운로드 (XLSX) ---
    out_buf = io.BytesIO()
    with pd.ExcelWriter(out_buf, engine="openpyxl") as writer:
        out_df.to_excel(writer, sheet_name=f"{sel_year}_{sel_period}", index=False)
        curr_view.to_excel(writer, sheet_name="원천_상세매핑", index=False)
        if not yearly_plan.empty:
            yearly_matrix.to_excel(writer, sheet_name="중장기_연도별추이", index=False)

    st.download_button(
        label=f"📥 [{sel_year}년 {sel_period}] 결과 엑셀 다운로드",
        data=out_buf.getvalue(),
        file_name=f"PCB_하위자재_소요량_{sel_year}_{sel_period}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
