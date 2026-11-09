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
